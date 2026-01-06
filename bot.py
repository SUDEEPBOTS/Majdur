import os
import random  # <--- Ye line add kar imports
import asyncio
import logging
import time
from pyrogram import Client, filters
from motor.motor_asyncio import AsyncIOMotorClient
import google.generativeai as genai
import aiohttp

# ─────────────────────────────
# ⚙️ INITIAL CONFIG
# ─────────────────────────────
API_ID = int(os.getenv("API_ID", "12345"))
API_HASH = os.getenv("API_HASH", "your_hash")
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token")
MONGO_URL = os.getenv("MONGO_DB_URI") 
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789")) 
LOGGER_ID = int(os.getenv("LOGGER_ID", "-100xxxx")) 

# ─────────────────────────────
# 🔧 SETUP
# ─────────────────────────────
app = Client("MajdoorBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

mongo = AsyncIOMotorClient(MONGO_URL)
db = mongo["MusicAPI_DB12"]
videos_col = db["videos_cacht"]
config_col = db["bot_internal_config"]

logging.basicConfig(level=logging.INFO)

# Global Flags
MAJDORI_MODE = False
SPAM_MODE = False
TODAY_SEARCH_COUNT = 0

# ─────────────────────────────
# 🧠 CONFIG MANAGER
# ─────────────────────────────
async def get_config():
    conf = await config_col.find_one({"_id": "main_config"})
    if not conf:
        await config_col.insert_one({
            "_id": "main_config",
            "api_url": "https://tera-api.herokuapp.com",
            "api_key": "default_key",
            "gemini_key": "default_key"
        })
        return None
    return conf

# ─────────────────────────────
# 🧠 AI & LOGIC (Updated with Randomizer)
# ─────────────────────────────
async def get_unique_song():
    conf = await get_config()
    if not conf or not conf.get("gemini_key"):
        return None, "NO KEY"

    genai.configure(api_key=conf["gemini_key"])
    # Temperature badha diya taki AI creative bane (0.9)
    model = genai.GenerativeModel("gemini-1.5-flash", generation_config={"temperature": 1.0})

    try:
        # 🎲 RANDOMIZERS
        moods = ["Sad", "Romantic", "Party", "High Bass", "Lo-fi", "90s Bollywood", "Punjabi Pop", "English Rap", "Arijit Singh", "Old Classic", "Item Song", "Workout"]
        alphabets = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        
        # Har baar naya combination banega
        chosen_mood = random.choice(moods)
        chosen_char = random.choice(alphabets)
        
        # Prompt: "Ek [Mood] gana bata jo [Letter] se start ho"
        prompt = (
            f"Suggest 1 unique {chosen_mood} song name that starts with letter '{chosen_char}'. "
            f"Do not give common songs like 'Shape of You'. "
            f"Just give the Song Name. No extra text."
        )

        resp = model.generate_content(prompt)
        song_name = resp.text.strip()

        # Safai (Kabhi kabhi AI "Here is your song: X" bolta hai, usko hatane ke liye)
        song_name = song_name.replace("Here is a song:", "").replace('"', "").strip()

        # ⚡ DUPLICATE CHECK (DB)
        exists = await videos_col.find_one({"title": {"$regex": song_name, "$options": "i"}})
        if exists:
            print(f"♻️ Skipped (Exists): {song_name}")
            return None, "DUPLICATE"
        
        return song_name, None
    except Exception as e:
        return None, str(e)

# ─────────────────────────────
# 👷 MAJDORI LOOP
# ─────────────────────────────
async def start_majdori():
    global MAJDORI_MODE, TODAY_SEARCH_COUNT
    async with aiohttp.ClientSession() as session:
        while MAJDORI_MODE:
            try:
                conf = await get_config()
                if not conf:
                    await asyncio.sleep(10)
                    continue

                song, err = await get_unique_song()
                if not song:
                    await asyncio.sleep(2)
                    continue

                start = time.time()
                url = f"{conf['api_url']}/getvideo?query={song}&key={conf['api_key']}"
                
                async with session.get(url) as resp:
                    data = await resp.json()
                    end = time.time()
                    resp_time = f"{end-start:.2f}s"

                    if data.get("status") == 200:
                        TODAY_SEARCH_COUNT += 1
                        msg = (
                            f"**ᴍᴀᴊᴅᴏʀɪ sᴜᴄᴄᴇss**\n\n"
                            f"**ᴛɪᴛʟᴇ:** {data['title']}\n"
                            f"**ᴛɪᴍᴇ:** {resp_time}\n"
                            f"**sᴏᴜʀᴄᴇ:** ᴀᴜᴛᴏ\n"
                            f"**ᴛᴏᴛᴀʟ:** {TODAY_SEARCH_COUNT}"
                        )
                        await app.send_message(LOGGER_ID, msg)
                    else:
                        print(f"Failed: {song}")

                await asyncio.sleep(8)

            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(5)

# ─────────────────────────────
# 🔨 SPAM LOOP
# ─────────────────────────────
async def start_spam():
    global SPAM_MODE
    async with aiohttp.ClientSession() as session:
        while SPAM_MODE:
            try:
                conf = await get_config()
                start = time.time()
                url = f"{conf['api_url']}/getvideo?query=Believer&key={conf['api_key']}"
                
                async with session.get(url) as resp:
                    end = time.time()
                    await app.send_message(LOGGER_ID, f"**sᴘᴀᴍ ʜɪᴛ**\n**sᴘᴇᴇᴅ:** {end-start:.2f}s")
                
                await asyncio.sleep(3)
            except:
                pass

# ─────────────────────────────
# 🕹️ ADMIN COMMANDS
# ─────────────────────────────

@app.on_message(filters.command("start") & filters.user(ADMIN_ID))
async def start(client, message):
    await message.reply(
        "**ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ ʀᴇᴀᴅʏ**\n\n"
        "/config - sᴇᴛ ᴋᴇʏs\n"
        "/aplay - ᴀᴜᴛᴏ ᴀᴅᴅ\n"
        "/spam - sᴛʀᴇss ᴛᴇsᴛ\n"
        "/check - ʜɪᴛ ᴄᴏᴜɴᴛ\n"
        "/stats - ᴅʙ sᴛᴀᴛs\n"
        "/stop - ᴇᴍᴇʀɢᴇɴᴄʏ"
    )

@app.on_message(filters.command("config") & filters.user(ADMIN_ID))
async def set_configuration(client, message):
    try:
        args = message.command
        if len(args) < 2:
            conf = await get_config()
            return await message.reply(
                f"**ᴄᴜʀʀᴇɴᴛ ᴄᴏɴғɪɢ**\n\n"
                f"**ᴜʀʟ:** `{conf.get('api_url')}`\n"
                f"**ᴋᴇʏ:** `{conf.get('api_key')}`\n"
                f"**ɢᴇᴍɪɴɪ:** `{conf.get('gemini_key')}`\n\n"
                "**ᴜᴘᴅᴀᴛᴇ:**\n"
                "`/seturl`\n"
                "`/setkey`\n"
                "`/setgemini`"
            )
    except Exception as e:
        await message.reply(str(e))

@app.on_message(filters.command("seturl") & filters.user(ADMIN_ID))
async def update_url(client, message):
    if len(message.command) < 2: return
    url = message.text.split(None, 1)[1]
    await config_col.update_one({"_id": "main_config"}, {"$set": {"api_url": url}}, upsert=True)
    await message.reply(f"**ᴜʀʟ ᴜᴘᴅᴀᴛᴇᴅ:**\n`{url}`")

@app.on_message(filters.command("setkey") & filters.user(ADMIN_ID))
async def update_key(client, message):
    if len(message.command) < 2: return
    key = message.text.split(None, 1)[1]
    await config_col.update_one({"_id": "main_config"}, {"$set": {"api_key": key}}, upsert=True)
    await message.reply(f"**ᴀᴘɪ ᴋᴇʏ ᴜᴘᴅᴀᴛᴇᴅ:**\n`{key}`")

@app.on_message(filters.command("setgemini") & filters.user(ADMIN_ID))
async def update_gemini(client, message):
    if len(message.command) < 2: return
    key = message.text.split(None, 1)[1]
    await config_col.update_one({"_id": "main_config"}, {"$set": {"gemini_key": key}}, upsert=True)
    await message.reply(f"**ɢᴇᴍɪɴɪ ᴋᴇʏ ᴜᴘᴅᴀᴛᴇᴅ**")

@app.on_message(filters.command("aplay") & filters.user(ADMIN_ID))
async def handle_aplay(client, message):
    global MAJDORI_MODE
    cmd = message.command[1].lower() if len(message.command) > 1 else "status"
    
    if cmd == "on":
        if MAJDORI_MODE: return await message.reply("**ᴀʟʀᴇᴀᴅʏ ʀᴜɴɴɪɴɢ**")
        MAJDORI_MODE = True
        asyncio.create_task(start_majdori())
        await message.reply("**ᴍᴀᴊᴅᴏʀɪ sᴛᴀʀᴛᴇᴅ**")
    elif cmd == "off":
        MAJDORI_MODE = False
        await message.reply("**ᴍᴀᴊᴅᴏʀɪ sᴛᴏᴘᴘᴇᴅ**")

@app.on_message(filters.command("spam") & filters.user(ADMIN_ID))
async def handle_spam(client, message):
    global SPAM_MODE
    cmd = message.command[1].lower()
    if cmd == "on":
        SPAM_MODE = True
        asyncio.create_task(start_spam())
        await message.reply("**sᴘᴀᴍ ᴀᴛᴛᴀᴄᴋ sᴛᴀʀᴛᴇᴅ**")
    else:
        SPAM_MODE = False
        await message.reply("**sᴘᴀᴍ sᴛᴏᴘᴘᴇᴅ**")

@app.on_message(filters.command("check") & filters.user(ADMIN_ID))
async def check_cunt(client, message):
    try:
        count = int(message.command[1])
    except:
        return await message.reply("`usage: /check 5`")
    
    conf = await get_config()
    await message.reply(f"**ʜɪᴛᴛɪɴɢ {count} ᴛɪᴍᴇs...**")
    
    async with aiohttp.ClientSession() as session:
        for i in range(1, count+1):
            start = time.time()
            url = f"{conf['api_url']}/getvideo?query=faded&key={conf['api_key']}"
            async with session.get(url) as resp:
                end = time.time()
                await app.send_message(LOGGER_ID, f"**ᴄʜᴇᴄᴋ #{i}** | {end-start:.2f}s")
            await asyncio.sleep(1)

@app.on_message(filters.command("stop") & filters.user(ADMIN_ID))
async def stop_all(client, message):
    global MAJDORI_MODE, SPAM_MODE
    MAJDORI_MODE = False
    SPAM_MODE = False
    await message.reply("**ᴇᴍᴇʀɢᴇɴᴄʏ sᴛᴏᴘ ᴇxᴇᴄᴜᴛᴇᴅ**")

@app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def get_stats(client, message):
    total_db = await videos_col.count_documents({})
    await message.reply(
        f"**ʙᴏᴛ sᴛᴀᴛs**\n\n"
        f"**ᴅʙ sᴏɴɢs:** {total_db}\n"
        f"**sᴇssɪᴏɴ:** {TODAY_SEARCH_COUNT}\n"
        f"**ᴍᴀᴊᴅᴏʀɪ:** {MAJDORI_MODE}\n"
        f"**sᴘᴀᴍ:** {SPAM_MODE}"
    )


if __name__ == "__main__":
    # Event Loop Fix
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    print("🤖 Admin Bot Starting...")
    app.run()
