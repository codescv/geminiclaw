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
MAX_RESPONSE_LENGTH = 3000

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
    
    channel = bot.get_channel(channel_id)
    if not channel:
        try:
            channel = await bot.fetch_channel(channel_id)
        except Exception:
            print(f"Could not fetch channel {channel_id}")
            channel = None

    full_prompt = prompt
    if channel:
        try:
            history_msgs = [msg async for msg in channel.history(limit=20)]
            history_msgs.reverse()
            
            history_text = []
            for msg in history_msgs:
                author_name = "Gemini" if msg.author == bot.user else msg.author.name
                content = msg.clean_content.strip()
                if content:
                    history_text.append(f"{author_name}: {content}")
            
            if history_text:
                history_joined = "\n".join(history_text)
                full_prompt = f"Chat History (last 20 messages):\n{history_joined}\n\nBased on the above context, please respond to the latest request:\n{prompt}"
        except Exception as e:
            print(f"Error fetching history: {e}")

    try:
        process = await asyncio.create_subprocess_exec(
            'gemini', '-y', '-p', full_prompt,
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
        
        if channel:
            if len(final_response) > MAX_RESPONSE_LENGTH:
                truncated = final_response[:MAX_RESPONSE_LENGTH] + "\n... (truncated)"
                formatted_response = f"<@{author_id}> Here's the result (truncated):\n```markdown\n{truncated}\n```"
            else:
                formatted_response = f"<@{author_id}> Here's the result:\n```markdown\n{final_response}\n```"
            
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
