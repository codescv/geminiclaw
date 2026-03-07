import os
import sqlite3
import asyncio
import subprocess
import discord
from discord.ext import tasks, commands
import tomllib

try:
    with open("config.toml", "rb") as f:
        config = tomllib.load(f)
except FileNotFoundError:
    print("Error: config.toml not found. Please copy config.example.toml to config.toml and configure it.")
    exit(1)

discord_config = config.get("discord", {})
gemini_config = config.get("gemini", {})

TOKEN = discord_config.get("token")
if not TOKEN:
    print("Error: discord.token not found in config.toml")
    exit(1)

DB_PATH = "claw.db"
MAX_RESPONSE_LENGTH = 1900

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

async def send_long_message(channel, content, author_id=None):
    if not content:
        return

    lines = content.splitlines(keepends=True)
    current_chunk = ""
    first_message = True

    for line in lines:
        if len(current_chunk) + len(line) <= MAX_RESPONSE_LENGTH:
            current_chunk += line
        else:
            # just to be safe, maybe there is a very long line
            if len(current_chunk) > MAX_RESPONSE_LENGTH:
                current_chunk = current_chunk[:MAX_RESPONSE_LENGTH]
            
            if current_chunk:
                if first_message and author_id:
                    await channel.send(f"<@{author_id}> {current_chunk}")
                else:
                    await channel.send(current_chunk)
                first_message = False
            
            current_chunk = line

    if current_chunk:
        if len(current_chunk) > MAX_RESPONSE_LENGTH:
            current_chunk = current_chunk[:MAX_RESPONSE_LENGTH]
        if first_message and author_id:
            await channel.send(f"<@{author_id}> {current_chunk}")
        else:
            await channel.send(current_chunk)

@tasks.loop(seconds=5)
async def process_pending_messages():
    """Polls the database for pending messages and processes them."""
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
            # TODO now using builtin session management, history is only meaningful 
            # for groupchats where there are other messages not in the history
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
                # full_prompt = f"Chat History (last 20 messages):\n{history_joined}\n\nBased on the above context, please respond to the latest request:\n{prompt}"
        except Exception as e:
            print(f"Error fetching history: {e}")

    try:
        cwd = gemini_config.get('workspace', '.')
        gemini_exec = gemini_config.get('executable_path', 'gemini')
        args = [gemini_exec]
        
        # Check if the prompt starts with "-y"
        if full_prompt.startswith('-y '):
            args.append('-y')
            # Strip the "-y" part from the prompt before sending it to Gemini
            full_prompt = full_prompt[2:]
        elif gemini_config.get('sandbox') == True:
            # only activate sandbox without -y
            args.append('--sandbox')
        session_id = gemini_config.get('session_id')
        if session_id:
            args.extend(['-r', session_id])
        args.extend(['-p', full_prompt])
        
        env = os.environ.copy()
        if 'api_key' in gemini_config:
            env['GOOGLE_API_KEY'] = gemini_config['api_key']
        if 'project' in gemini_config:
            env['GOOGLE_CLOUD_PROJECT'] = gemini_config['project']
        if 'location' in gemini_config:
            env['GOOGLE_CLOUD_LOCATION'] = gemini_config['location']

        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env
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
            # Split and send long messages
            await send_long_message(channel, final_response, author_id)
            
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
    bot.run(TOKEN)

if __name__ == "__main__":
    main()
