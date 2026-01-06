import os
import random
import asyncio
import logging
import time
from pyrogram import Client, filters
from motor.motor_asyncio import AsyncIOMotorClient
from groq import Groq  # <--- Gemini hataya, Groq lagaya
import aiohttp

# ─────────────────────────────
# ⚙️ INITIAL CONFIG
# ─────────────────────────────
API_ID = int(os.getenv("API_ID", "12345"))
API_HASH = os.getenv("API_HASH", "your_hash")
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token")
MONGO_URL = os.getenv("MONGO_DB_URI") 
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789")) 

# Logger ID Logic
RAW_LOGGER = os.getenv("LOGGER_ID", "-100xxxx")
try:
    LOGGER_ID = int(RAW_LOGGER)
except:
    LOGGER_ID = RAW_LOGGER

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
        new_conf = {
            "_id": "main_config",
            "api_url": "https://tera-api.herokuapp.com",
            "api_key": "default_key",
            "groq_key": "default_key" # <--- Ab Groq key save hogi
        }
        await config_col.insert_one(new_conf)
        return new_conf
    return conf

# ─────────────────────────────
# 🧠 AI & LOGIC (GROQ Llama-3 - Super Fast)
# ─────────────────────────────
async def get_unique_song():
    conf = await get_config()
    # Check for Groq Key
    if not conf or not conf.get("groq_key") or conf.get("groq_key") == "default_key":
        return None, "❌ Groq Key Missing! Use /setgroq"

    try:
        # Groq Client Setup
        client = Groq(api_key=conf["groq_key"])

        # 🇮🇳 DESI MOODS (Popular Only)
        moods = [
            "Superhit Arijit Singh", "Trending Punjabi Party", "90s Bollywood Romantic", 
            "Best of Atif Aslam", "Sidhu Moose Wala", "Yo Yo Honey Singh", 
            "Latest Bollywood Blockbuster", "Old Classic Kishore Kumar", 
            "Emraan Hashmi Hit", "Badshah Party", "Top 50 India", "Neha Kakkar Hit"
        ]
        chosen_mood = random.choice(moods)

        # Llama-3 Prompt (Strict)
        prompt = (
            f"Suggest 1 very popular Indian {chosen_mood} song.\n"
            f"Rule 1: Only give the 'Song Name - Artist Name'.\n"
            f"Rule 2: Do NOT give English songs, remixes, or book trailers.\n"
            f"Rule 3: Do NOT write 'Here is a song' or any intro.\n"
            f"Example Output: Kesariya - Arijit Singh"
        )

        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile", # Super Fast & Free Model
            temperature=0.7,
        )

        song_name = chat_completion.choices[0].message.content.strip().replace('"', "")

        # ⚡ DUPLICATE CHECK
        exists = await videos_col.find_one({"title": {"$regex": song_name, "$options": "i"}})
        if exists:
            print(f"♻️ Skipped (Exists): {song_name}")
            return None, "DUPLICATE"
        
        return song_name, None

    except Exception as e:
        return None, f"⚠️ Groq Error: {str(e)}"

# ─────────────────────────────
# 👷 MAJDORI LOOP
# ─────────────────────────────
async def start_majdori():
    global MAJDORI_MODE, TODAY_SEARCH_COUNT
    
    try:
        # Cache Refresh for Logger (Ye error fix karega)
        await app.get_chat(LOGGER_ID)
        await app.send_message(LOGGER_ID, "**👷 ᴍᴀᴊᴅᴏʀɪ (ɢʀᴏǫ) sᴛᴀʀᴛᴇᴅ...**")
    except:
        pass

    async with aiohttp.ClientSession() as session:
        while MAJDORI_MODE:
            try:
                conf = await get_config()
                if not conf:
                    await asyncio.sleep(5)
                    continue

                song, err = await get_unique_song()
                if not song:
                    if err != "DUPLICATE":
                        try:
                            await app.send_message(LOGGER_ID, f"**⚠️ AI Error:** {err}")
                        except: pass
                        await asyncio.sleep(5)
                    else:
                        await asyncio.sleep(0.5) # Groq fast hai, jaldi retry karo
                    continue

                # API HIT
                start = time.time()
                url = f"{conf['api_url']}/getvideo?query={song}&key={conf['api_key']}"
                
                async with session.get(url) as resp:
                    data = await resp.json()
                    end = time.time()
                    resp_time = f"{end-start:.2f}s"

                    if data.get("status") == 200:
                        TODAY_SEARCH_COUNT += 1
                        msg = (
                            f"**✅ ᴍᴀᴊᴅᴏʀɪ sᴜᴄᴄᴇss**\n\n"
                            f"**🎵:** {data['title']}\n"
                            f"**🚀:** {resp_time} | ⚡ Groq\n"
                            f"**🔢:** {TODAY_SEARCH_COUNT}"
                        )
                        try:
                            await app.send_message(LOGGER_ID, msg)
                        except: pass
                    else:
                        err_msg = data.get("error", "Unknown")
                        try:
                            await app.send_message(LOGGER_ID, f"**❌ API Fail:** {song}\n{err_msg}")
                        except: pass

                await asyncio.sleep(5) # Groq fast hai, par API pe load kam rakhne ke liye 5s break

            except Exception as e:
                print(f"Loop Error: {e}")
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
                    try:
                        await app.send_message(LOGGER_ID, f"**⚡ SPAM HIT:** {end-start:.2f}s")
                    except: pass
                await asyncio.sleep(3)
            except: pass

# ─────────────────────────────
# 🕹️ ADMIN COMMANDS
# ─────────────────────────────

@app.on_message(filters.command("start") & filters.user(ADMIN_ID))
async def start(client, message):
    await message.reply(
        "**⚡ GROQ ADMIN PANEL**\n\n"
        "/config - View Config\n"
        "/setgroq - Set Groq Key (New)\n"
        "/aplay on/off - Majdori\n"
        "/check 5 - Test API"
    )

@app.on_message(filters.command("config") & filters.user(ADMIN_ID))
async def set_configuration(client, message):
    conf = await get_config()
    await message.reply(f"**API Key:** `{conf.get('api_key')}`\n**Groq Key:** `{conf.get('groq_key')}`")

@app.on_message(filters.command("seturl") & filters.user(ADMIN_ID))
async def update_url(client, message):
    if len(message.command) < 2: return await message.reply("Give URL")
    url = message.text.split(None, 1)[1]
    await config_col.update_one({"_id": "main_config"}, {"$set": {"api_url": url}}, upsert=True)
    await message.reply(f"**URL Updated**")

@app.on_message(filters.command("setkey") & filters.user(ADMIN_ID))
async def update_key(client, message):
    if len(message.command) < 2: return await message.reply("Give Key")
    key = message.text.split(None, 1)[1]
    await config_col.update_one({"_id": "main_config"}, {"$set": {"api_key": key}}, upsert=True)
    await message.reply(f"**API Key Updated**")

# ✅ NEW COMMAND FOR GROQ
@app.on_message(filters.command("setgroq") & filters.user(ADMIN_ID))
async def update_groq(client, message):
    if len(message.command) < 2: return await message.reply("Give Groq Key `gsk_...`")
    key = message.text.split(None, 1)[1]
    await config_col.update_one({"_id": "main_config"}, {"$set": {"groq_key": key}}, upsert=True)
    await message.reply(f"**✅ Groq Key Updated!**\nAb Majdori fast hogi.")

@app.on_message(filters.command("aplay") & filters.user(ADMIN_ID))
async def handle_aplay(client, message):
    global MAJDORI_MODE
    cmd = message.command[1].lower() if len(message.command) > 1 else "status"
    if cmd == "on":
        if MAJDORI_MODE: return await message.reply("Already ON")
        MAJDORI_MODE = True
        asyncio.create_task(start_majdori())
        await message.reply("🚀 **Groq Majdori Started!**")
    elif cmd == "off":
        MAJDORI_MODE = False
        await message.reply("🛑 Stopped")
    else:
        await message.reply(f"Status: {MAJDORI_MODE}")

@app.on_message(filters.command("spam") & filters.user(ADMIN_ID))
async def handle_spam(client, message):
    global SPAM_MODE
    cmd = message.command[1].lower() if len(message.command) > 1 else "status"
    if cmd == "on":
        SPAM_MODE = True
        asyncio.create_task(start_spam())
        await message.reply("⚔️ Spam Started")
    elif cmd == "off":
        SPAM_MODE = False
        await message.reply("🛑 Spam Stopped")

@app.on_message(filters.command("check") & filters.user(ADMIN_ID))
async def check_cunt(client, message):
    try:
        count = int(message.command[1])
    except:
        return await message.reply("/check 5")
    
    conf = await get_config()
    await message.reply(f"Hitting {count} times...")
    
    async with aiohttp.ClientSession() as session:
        for i in range(1, count+1):
            start = time.time()
            url = f"{conf['api_url']}/getvideo?query=faded&key={conf['api_key']}"
            try:
                async with session.get(url, timeout=10) as resp:
                    end = time.time()
                    try: await app.send_message(LOGGER_ID, f"**#{i}** | {end-start:.2f}s | {resp.status}")
                    except: pass
            except: pass
            await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    print("🤖 Groq Bot Starting...")
    app.run()
