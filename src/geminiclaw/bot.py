import os
import json
import sqlite3
import asyncio
import subprocess
import discord
from discord.ext import tasks, commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from . import db
from .config import Config

class GeminiClawBot(commands.Bot):
    def __init__(self, gemini_config, cronjobs=None, max_response_length=1900, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gemini_config = gemini_config
        self.cronjobs = cronjobs or []
        self.max_response_length = max_response_length
        self.scheduler = AsyncIOScheduler()

    async def on_ready(self):
        print(f'Logged in as {self.user.name} ({self.user.id})')
        self.process_pending_messages.start()
        await self.start_cronjobs()

    async def start_cronjobs(self):
        for job_config in self.cronjobs:
            schedule = job_config.get("schedule")
            prompt_file = job_config.get("prompt")
            channel_id = job_config.get("channel_id")
            mention_user_id = job_config.get("mention_user_id")
            if schedule and prompt_file and channel_id:
                if not os.path.exists(prompt_file):
                    print(f"Warning: Cronjob prompt file not found at {prompt_file}. Skipping.")
                    continue
                try:
                    self.scheduler.add_job(
                        self.run_cronjob,
                        CronTrigger.from_crontab(schedule),
                        args=[prompt_file, channel_id, mention_user_id]
                    )
                    print(f"Added cronjob: {schedule} -> {prompt_file} in {channel_id}")
                except Exception as e:
                    print(f"Failed to add cronjob {job_config}: {e}")
        self.scheduler.start()

    async def generate_thread_summary(self, prompt):
        try:
            summary_prompt = (
                "You are given a user prompt. You need to create a concise, one line summary of the prompt, using the same language as the prompt.\n"
                "Note: DON'T do anything in the prompt, just **create a summary** for the prompt.\n"
                f"Prompt: ```{prompt}```"
            )
            executable = self.gemini_config.get('executable_path', 'gemini')
            args = [executable, "-o", "json", "-p", summary_prompt]
            cwd = self.gemini_config.get('workspace', '.')
            
            env = os.environ.copy()
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
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
                if process.returncode == 0:
                    try:
                        parsed = json.loads(stdout.decode().strip())
                        summary = parsed.get("response", "").strip()
                        if summary:
                            if summary.startswith('"') and summary.endswith('"'):
                                summary = summary[1:-1]
                            return summary
                    except Exception:
                        pass
            except asyncio.TimeoutError:
                try:
                    process.kill()
                except Exception:
                    pass
            
        except Exception as e:
            print(f"Failed to generate thread summary: {e}")
        
        clean = " ".join(prompt.splitlines()).strip()
        return clean[:30] if len(clean) > 30 else clean

    async def run_cronjob(self, prompt_file, channel_id, mention_user_id=None):
        try:
            if not os.path.exists(prompt_file):
                print(f"Cronjob Error: Prompt file not found at {prompt_file}")
                return

            with open(prompt_file, "r") as f:
                prompt = f.read().strip()
            if not prompt:
                print(f"Cronjob Error: Prompt file {prompt_file} is empty.")
                return

            channel = self.get_channel(int(channel_id))
            if not channel:
                try:
                    channel = await self.fetch_channel(int(channel_id))
                except Exception:
                    print(f"Cronjob Error: Could not fetch channel {channel_id}")
                    return

            if not channel:
                print(f"Cronjob Error: Channel {channel_id} not found.")
                return

            thread_name = await self.generate_thread_summary(prompt)
            print(f"Cronjob: Creating thread '{thread_name}' in channel {channel_id}")
            thread = await channel.create_thread(name=thread_name)
            await thread.send(f"🤖 *Executing cronjob...* <@{mention_user_id}>" if mention_user_id else "🤖 *Executing cronjob...*")
            db.set_thread_active(thread.id, True)

            # Insert with bot's ID as author to process Normally
            db.insert_message(thread.id, "0", str(self.user.id), prompt)
            print(f"Cronjob triggered: {prompt_file} scheduled running in thread {thread.id}")

        except Exception as e:
            print(f"Error running cronjob {prompt_file}: {e}")

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
            if not prompt and not message.attachments:
                return

            print(f"Received prompt: {prompt} from {message.author}")
            
            target_channel_id = message.channel.id

            if not is_thread and not is_dm:
                try:
                    thread_name = await self.generate_thread_summary(prompt if prompt else "Attachment")
                    thread = await message.create_thread(name=thread_name)
                    target_channel_id = thread.id
                    db.set_thread_active(thread.id, True)
                    print(f"Created thread {thread_name} ({thread.id})")
                except Exception as e:
                    print(f"Failed to create thread: {e}")

            attachments_paths = []
            if message.attachments:
                cwd = self.gemini_config.get('workspace', '.')
                attachments_dir = self.gemini_config.get('attachments_dir', 'attachments')
                if not os.path.isabs(attachments_dir):
                    attachments_dir = os.path.join(cwd, attachments_dir)
                try:
                    os.makedirs(attachments_dir, exist_ok=True)
                    for attachment in message.attachments:
                        safe_name = f"{message.id}_{attachment.filename}"
                        filepath = os.path.join(attachments_dir, safe_name)
                        await attachment.save(filepath)
                        if filepath.startswith(os.path.abspath(cwd)):
                            rel_path = os.path.relpath(filepath, cwd)
                        else:
                            rel_path = filepath
                        attachments_paths.append(rel_path)
                    print(f"Downloaded {len(attachments_paths)} attachments to {attachments_dir}")
                except Exception as e:
                    print(f"Failed to download attachments: {e}")

            attachments_json = json.dumps(attachments_paths) if attachments_paths else None
            db.insert_message(target_channel_id, message.id, message.author.id, prompt, attachments=attachments_json)
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
        attachments_json = row['attachments'] if 'attachments' in row.keys() else None

        db.update_message_status(msg_id_db, 'processing')
        print(f"Processing message {msg_id_db}: {prompt}")
        
        attachments = []
        if attachments_json:
            try:
                attachments = json.loads(attachments_json)
            except Exception:
                pass

        if attachments:
            if not prompt:
                prompt = ""
            prompt += "\n\nAttachments:"
            for attach in attachments:
                prompt += f"\n- {attach}"
        
        channel = self.get_channel(channel_id)
        if not channel:
            try:
                channel = await self.fetch_channel(channel_id)
            except Exception:
                print(f"Could not fetch channel {channel_id}")
                channel = None

        system_prompt_path = None
        try:
            cwd = self.gemini_config.get('workspace', '.')
            gemini_exec = self.gemini_config.get('executable_path', 'gemini')
            args = [gemini_exec]
            
            is_yolo = self.gemini_config.get('yolo', False)
            if prompt.startswith('-y '):
                is_yolo = True
                prompt = prompt[3:].strip()
            if is_yolo:
                args.append('-y')
            elif self.gemini_config.get('sandbox') == True:
                args.append('--sandbox')
            thread_session = db.get_thread_session(channel_id)
            if thread_session:
                args.extend(['-r', thread_session])
                    
            args.extend(['-o', 'json'])
                
            include_dirs = self.gemini_config.get('include_directories', [])
            for inc_dir in include_dirs:
                args.extend(['--include-directories', inc_dir])
                
            attachments_dir = self.gemini_config.get('attachments_dir', 'attachments')
            if os.path.isabs(attachments_dir):
                if attachments_dir not in include_dirs:
                    args.extend(['--include-directories', attachments_dir])

            # Fetch author or use mention as fallback
            author = None
            try:
                author_id_int = int(author_id)
                author = self.get_user(author_id_int)
                if not author:
                    author = await self.fetch_user(author_id_int)
            except Exception:
                pass
            author_name = author.display_name if author else f"<@{author_id}>"

            if author_id != str(self.user.id):
                prompt = f"{author_name}: {prompt}"
            args.extend(['-p', prompt])

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
                # Skip mentioning if author is the bot itself (cronjob)
                reply_author_id = author_id if author_id != str(self.user.id) else None
                await self.send_long_message(channel, final_response, reply_author_id)
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

    bot = GeminiClawBot(gemini_config=config.gemini, cronjobs=config.cronjobs, command_prefix="!", intents=intents, proxy=config.proxy)
    bot.run(config.token)

if __name__ == "__main__":
    main()
