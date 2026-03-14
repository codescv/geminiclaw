import os
import sqlite3
import asyncio
import subprocess
import discord
from discord.ext import tasks, commands
from . import db
from .config import Config

class GeminiClawBot(commands.Bot):
    def __init__(self, gemini_config, max_response_length=1900, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gemini_config = gemini_config
        self.max_response_length = max_response_length

    async def on_ready(self):
        print(f'Logged in as {self.user.name} ({self.user.id})')
        self.process_pending_messages.start()

    async def on_message(self, message):
        if message.author == self.user:
            return

        is_thread = isinstance(message.channel, discord.Thread)
        is_dm = isinstance(message.channel, discord.DMChannel)
        is_bot_mentioned = self.user.mentioned_in(message) or is_dm

        should_reply = False

        if is_bot_mentioned:
            should_reply = True
            if is_thread:
                db.set_thread_active(message.channel.id, True)
        elif is_thread:
            if db.is_thread_active(message.channel.id):
                should_reply = True
            else:
                try:
                    starter_msg = await message.channel.parent.fetch_message(message.channel.id)
                    if self.user.mentioned_in(starter_msg):
                        db.set_thread_active(message.channel.id, True)
                        should_reply = True
                except Exception as e:
                    print(f"Error fetching starter message: {e}")

        if should_reply:
            prompt = message.content.replace(f'<@{self.user.id}>', '').replace(f'<@!{self.user.id}>', '').strip()
            if not prompt:
                return

            print(f"Received prompt: {prompt} from {message.author}")
            
            target_channel_id = message.channel.id

            if not is_thread and not is_dm:
                try:
                    thread_name = f"Thread: {prompt[:30]}" if len(prompt) > 30 else f"Thread: {prompt}"
                    thread = await message.create_thread(name=thread_name)
                    target_channel_id = thread.id
                    db.set_thread_active(thread.id, True)
                    print(f"Created thread {thread_name} ({thread.id})")
                except Exception as e:
                    print(f"Failed to create thread: {e}")

            db.insert_message(target_channel_id, message.id, message.author.id, prompt)
            await message.add_reaction('✅')

    async def send_long_message(self, channel, content, author_id=None):
        if not content:
            return

        lines = content.splitlines(keepends=True)
        current_chunk = ""
        first_message = True

        for line in lines:
            if len(current_chunk) + len(line) <= self.max_response_length:
                current_chunk += line
            else:
                if len(current_chunk) > self.max_response_length:
                    current_chunk = current_chunk[:self.max_response_length]
                
                if current_chunk:
                    if first_message and author_id:
                        await channel.send(f"<@{author_id}> {current_chunk}")
                    else:
                        await channel.send(current_chunk)
                    first_message = False
                current_chunk = line

        if current_chunk:
            if len(current_chunk) > self.max_response_length:
                current_chunk = current_chunk[:self.max_response_length]
            if first_message and author_id:
                await channel.send(f"<@{author_id}> {current_chunk}")
            else:
                await channel.send(current_chunk)

    @tasks.loop(seconds=5)
    async def process_pending_messages(self):
        """Polls the database for pending messages and processes them."""
        row = db.get_pending_message()
        if not row:
            return

        msg_id_db = row['id']
        channel_id = int(row['channel_id'])
        prompt = row['prompt']
        author_id = row['author_id']

        db.update_message_status(msg_id_db, 'processing')
        print(f"Processing message {msg_id_db}: {prompt}")
        
        channel = self.get_channel(channel_id)
        if not channel:
            try:
                channel = await self.fetch_channel(channel_id)
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
                    author_name = "Gemini" if msg.author == self.user else msg.author.name
                    content = msg.clean_content.strip()
                    if content:
                        history_text.append(f"{author_name}: {content}")
                
                if history_text:
                    history_joined = "\n".join(history_text)
            except Exception as e:
                print(f"Error fetching history: {e}")

        system_prompt_path = None
        try:
            cwd = self.gemini_config.get('workspace', '.')
            gemini_exec = self.gemini_config.get('executable_path', 'gemini')
            args = [gemini_exec]
            
            if full_prompt.startswith('-y '):
                args.append('-y')
                full_prompt = full_prompt[2:]
            elif self.gemini_config.get('sandbox') == True:
                args.append('--sandbox')
            thread_session = db.get_thread_session(channel_id)
            if thread_session:
                args.extend(['-r', thread_session])
                    
            args.extend(['-o', 'json'])
                
            include_dirs = self.gemini_config.get('include_directories', [])
            for inc_dir in include_dirs:
                args.extend(['--include-directories', inc_dir])

            args.extend(['-p', full_prompt])

            print('args:', args)
            
            if channel:
                topic = None
                if isinstance(channel, discord.Thread):
                    if hasattr(channel.parent, 'topic'):
                        topic = channel.parent.topic
                elif isinstance(channel, discord.TextChannel):
                    topic = channel.topic
                
                if topic and topic.strip():
                    system_prompt_path = f"/tmp/gemini_system_{channel_id}.md"
                    print(f"Using channel topic as system prompt: {topic.strip()}")
                    with open(system_prompt_path, "w") as f:
                        f.write(topic.strip())
            
            env = os.environ.copy()
            if system_prompt_path:
                env['GEMINI_SYSTEM_MD'] = system_prompt_path
            if 'api_key' in self.gemini_config:
                env['GOOGLE_API_KEY'] = self.gemini_config['api_key']
            if 'project' in self.gemini_config:
                env['GOOGLE_CLOUD_PROJECT'] = self.gemini_config['project']
            if 'location' in self.gemini_config:
                env['GOOGLE_CLOUD_LOCATION'] = self.gemini_config['location']

            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env
            )
            
            timeout_seconds = self.gemini_config.get('timeout', 600)
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
                response = stdout.decode().strip()
                error = stderr.decode().strip()

                final_response = response
                if response:
                    try:
                        import json
                        parsed = json.loads(response)
                        final_response = parsed.get("response", response)
                        new_session_id = parsed.get("session_id")
                        if new_session_id:
                            db.set_thread_session(channel_id, new_session_id)
                    except Exception as e:
                        print(f"Failed to parse JSON response: {e}")

                if not final_response and error:
                    final_response = f"Error: {error}"
                if not final_response:
                    final_response = "Gemini completed but returned no output."
            except asyncio.TimeoutError:
                try:
                    process.kill()
                except Exception:
                    pass
                final_response = f"Error: Gemini command timed out after {timeout_seconds} seconds."

            db.update_message_status(msg_id_db, 'completed', final_response)
            
            if channel:
                await self.send_long_message(channel, final_response, author_id)
                db.update_message_status(msg_id_db, 'delivered')

        except Exception as e:
            print(f"Error processing message {msg_id_db}: {e}")
            db.update_message_status(msg_id_db, 'failed', str(e))
        finally:
            if system_prompt_path and os.path.exists(system_prompt_path):
                try:
                    os.remove(system_prompt_path)
                    print(f"Cleaned up system prompt file: {system_prompt_path}")
                except Exception as e:
                    print(f"Failed to remove temp system prompt file {system_prompt_path}: {e}")

def main():
    config = Config()

    intents = discord.Intents.default()
    intents.message_content = True

    bot = GeminiClawBot(gemini_config=config.gemini, command_prefix="!", intents=intents, proxy=config.proxy)
    bot.run(config.token)

if __name__ == "__main__":
    main()
