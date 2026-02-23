import os
import sqlite3
import asyncio
import subprocess
import discord
from discord.ext import tasks, commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
DB_PATH = "claw.db"

# Respect HTTP_PROXY/HTTPS_PROXY environment variables
proxy = os.getenv('HTTP_PROXY') or os.getenv('http_proxy') or os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, proxy=proxy)

def get_db_connection():
    # If we are in src/, we need to look one level up for claw.db?
    # Or keep it relative to CWD.
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    process_pending_messages.start()

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        prompt = message.content.replace(f'<@{bot.user.id}>', '').replace(f'<@!{bot.user.id}>', '').strip()
        if not prompt:
            return

        print(f"Received prompt: {prompt} from {message.author}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (channel_id, message_id, author_id, prompt, status) VALUES (?, ?, ?, ?, ?)",
            (str(message.channel.id), str(message.id), str(message.author.id), prompt, 'pending')
        )
        conn.commit()
        conn.close()
        
        await message.add_reaction('✅')

@tasks.loop(seconds=5)
async def process_pending_messages():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM messages WHERE status = 'pending' LIMIT 1")
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return

    msg_id_db = row['id']
    channel_id = int(row['channel_id'])
    prompt = row['prompt']
    author_id = row['author_id']

    cursor.execute("UPDATE messages SET status = 'processing' WHERE id = ?", (msg_id_db,))
    conn.commit()
    conn.close()

    print(f"Processing message {msg_id_db}: {prompt}")
    
    try:
        process = await asyncio.create_subprocess_exec(
            'gemini', '-y', '-p', prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        response = stdout.decode().strip()
        error = stderr.decode().strip()

        final_response = response
        if not final_response and error:
            final_response = f"Error: {error}"
        if not final_response:
            final_response = "Gemini completed but returned no output."

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE messages SET status = 'completed', response = ? WHERE id = ?",
            (final_response, msg_id_db)
        )
        conn.commit()
        conn.close()

        channel = bot.get_channel(channel_id)
        if not channel:
            try:
                channel = await bot.fetch_channel(channel_id)
            except:
                print(f"Could not fetch channel {channel_id}")
                channel = None
        
        if channel:
            formatted_response = f"<@{author_id}> Here's the result:\n```\n{final_response}\n```"
            if len(formatted_response) > 2000:
                truncated = final_response[:1900] + "\n... (truncated)"
                formatted_response = f"<@{author_id}> Here's the result (truncated):\n```\n{truncated}\n```"
            
            await channel.send(formatted_response)
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE messages SET status = 'delivered' WHERE id = ?", (msg_id_db,))
            conn.commit()
            conn.close()

    except Exception as e:
        print(f"Error processing message {msg_id_db}: {e}")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE messages SET status = 'failed', response = ? WHERE id = ?",
            (str(e), msg_id_db)
        )
        conn.commit()
        conn.close()

def main():
    if not TOKEN:
        print("DISCORD_TOKEN not found in .env. Please run `/claw setup` first.")
    else:
        bot.run(TOKEN)

if __name__ == "__main__":
    main()
