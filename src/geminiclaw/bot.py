import os
import json
import sqlite3
import asyncio
import subprocess
import discord
from discord.ext import tasks, commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import time
import re
from apscheduler.triggers.cron import CronTrigger
from . import db
from .config import Config

class StreamSender:
    """Handles sending long text responses to Discord with smart chunking and streaming edits."""
    
    def _clean_message(self, text):
        """Removes outbound attachment tags from text to keep Discord messages clean."""
        return re.sub(r'\[attachment:\s*.*?\]', '', text)

    def _split_elegant(self, text):
        """Finds the last newline within max length to avoid cutting words in half."""
        max_len = self.bot.max_response_length
        last_newline = text[:max_len].rfind('\n')
        if last_newline != -1:
            return text[:last_newline+1], text[last_newline+1:]
        return text[:max_len], text[max_len:]

    def __init__(self, bot, channel, prefix=""):
        self.bot = bot
        self.channel = channel
        self.prefix = prefix
        self.msg_to_edit = None  # Reference to the active message we are editing during streaming
        self.current_chunk = ""  # Accumulated text that hasn't been finalized yet
        self.is_first_chunk = True # Flag to ensure prefix is only added once
        self.streamed = False      # Marker if we actually streamed or just sent static

    async def send(self, text=None, flush=False):
        """Accumulates text and sends/edits Discord messages. Set flush=True for final delivery."""
        if text is not None:
            self.current_chunk += text
            
        self.current_chunk = self._clean_message(self.current_chunk)
        if not self.current_chunk:
            return

        if self.msg_to_edit:
            # We have an active message we are editing!
            if len(self.current_chunk) > self.bot.max_response_length:
                # It overflowed! Split elegantly and finalize the first part.
                first_part, residue = self._split_elegant(self.current_chunk)
                final_text = self.prefix + first_part if self.is_first_chunk else first_part
                await self.msg_to_edit.edit(content=final_text)
                self.is_first_chunk = False
                
                # Use smart chunks for residue (it might still be huge, so split it further)
                self.msg_to_edit = await self.send_smart_chunks(residue, incomplete=not flush)
                if flush:
                    self.current_chunk = ""
            else:
                # Fits in one message! Just edit it.
                suffix = "" if flush else " (incomplete)"
                final_text = self.prefix + self.current_chunk if self.is_first_chunk else self.current_chunk
                await self.msg_to_edit.edit(content=final_text + suffix)
                if flush:
                    self.current_chunk = ""
        else:
            # First message of the stream or static message
            if flush:
                await self.send_smart_chunks(self.current_chunk)
                self.current_chunk = ""
            else:
                self.msg_to_edit = await self.channel.send(self.current_chunk + " (incomplete)")
                self.streamed = True

    async def flush(self):
        """Wrapper to finalize the stream and send all remaining text."""
        await self.send(flush=True)

    async def send_smart_chunks(self, text, incomplete=False):
        """Splits text line-by-line into Discord messages without cutting lines where possible."""
        lines = text.splitlines(keepends=True)
        current_chunk = ""
        last_msg = None
        
        for line in lines:
            if len(current_chunk) + len(line) <= self.bot.max_response_length:
                current_chunk += line
            else:
                if current_chunk:
                    last_msg = await self._send_chunk_impl(current_chunk)
                
                residue = line
                while len(residue) > self.bot.max_response_length:
                    last_msg = await self._send_chunk_impl(residue[:self.bot.max_response_length])
                    residue = residue[self.bot.max_response_length:]
                current_chunk = residue
                
        if current_chunk:
            last_msg = await self._send_chunk_impl(current_chunk, is_last=True, incomplete=incomplete)
        return last_msg

    async def _send_chunk_impl(self, chunk, is_last=False, incomplete=False):
        """Sends a single chunk of text to Discord and returns the message object."""
        clean_chunk = self._clean_message(chunk)
        if chunk.strip() and not clean_chunk.strip():
            return None
        
        suffix = " (incomplete)" if is_last and incomplete else ""
        content = self.prefix + clean_chunk + suffix if self.is_first_chunk else clean_chunk + suffix
        msg = await self.channel.send(content)
        self.is_first_chunk = False
        return msg

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
            pass
        
        print(f"Failed to generate thread summary, fallback to using prompt")
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

    async def on_message_edit(self, before, after):
        if after.author == self.user:
            return

        # Check if a bot message just finished streaming
        if before.content.endswith(" (incomplete)") and not after.content.endswith(" (incomplete)"):
            await self.on_message(after)

    async def on_message(self, message):
        if message.author == self.user:
            # don't answer myself
            return

        if message.content.endswith(" (incomplete)"):
            # don't answer incomplete messages
            return

        is_thread = isinstance(message.channel, discord.Thread)
        is_dm = isinstance(message.channel, discord.DMChannel)
        is_bot_mentioned = self.user.mentioned_in(message)

        if message.content.strip().lower() == "-stop":
            if is_thread:
                db.set_thread_active(message.channel.id, False)
                try:
                    await message.add_reaction("🛑")
                except Exception:
                    pass
            return

        if message.content.strip().lower() == "-continue":
            if is_thread:
                db.set_thread_active(message.channel.id, True)
                try:
                    await message.add_reaction("▶️")
                except Exception:
                    pass
            return

        # Explicitly enforce -stop: if it's inactive, ignore all pings until -continue
        if is_thread and db.has_thread(message.channel.id) and not db.is_thread_active(message.channel.id):
            print("Thread is deactivated. Ignoring all message until -continue.")
            return

        should_reply = False
        is_new_thread_participant = False

        if is_bot_mentioned or is_dm:
            print('Replying to a mentioned message')
            should_reply = True
            if is_thread:
                if not db.has_thread(message.channel.id):
                    is_new_thread_participant = True
                db.set_thread_active(message.channel.id, True)
        elif is_thread:
            if db.is_thread_active(message.channel.id):
                if message.mentions:
                    print('Skpping message explicitly mentioning others in active thread')
                else:
                    print('Replying to an active thread')
                    should_reply = True
            elif not db.has_thread(message.channel.id):
                try:
                    starter_msg = await message.channel.parent.fetch_message(message.channel.id)
                    if self.user.mentioned_in(starter_msg):
                        # this only happens when the bot is offline when the thread is created
                        # a fallback to recover the thread state if the bot crashes or restarts
                        print(f'Recovering thread state for thread {message.channel.id}')
                        is_new_thread_participant = True
                        db.set_thread_active(message.channel.id, True)
                        should_reply = True
                except Exception as e:
                    print(f"Error fetching starter message: {e}")
            else:
                # otherwise, the thread has been marked as inactive (possbily by -stop)
                print("Thread inactive, stop replying.")

        if not should_reply:
            # early return
            return

        # replace mentions with display names, so that bots knows their identity referered in the message
        prompt = message.content
        for user in message.mentions:
            prompt = prompt.replace(f'<@{user.id}>', f'@{user.display_name}').replace(f'<@!{user.id}>', f'@{user.display_name}')
        prompt = prompt.strip()

        if is_new_thread_participant:
            print(f"Fetching history for newly joined thread {message.channel.id}")
            history_text = ""
            try:
                # fetch last 20 messages to provide context
                async for msg in message.channel.history(limit=20, before=message):
                    # NOTE: the msg is in reverse time order
                    content = msg.clean_content.strip()
                    if content:
                        history_text = f"{msg.author.display_name}: {content}\n" + history_text
                # Try to fetch the starter message from the parent channel
                if hasattr(message.channel, 'parent') and message.channel.parent:
                    try:
                        starter_msg = await message.channel.parent.fetch_message(message.channel.id)
                        # Ensure we don't accidentally duplicate if it was yielded by history
                        if starter_msg and starter_msg.id != message.id:
                            content = starter_msg.clean_content.strip()
                            if content and not history_text.startswith(f"{starter_msg.author.display_name}: {content}"):
                                history_text = f"{starter_msg.author.display_name}: {content}\n" + history_text
                    except Exception as e:
                        pass
                
                if history_text:
                    prompt = f"[Previous Context]\n{history_text.strip()}\n\n[Current Message]\n{prompt}"
            except Exception as e:
                print(f"Error fetching history: {e}")
        
        if not prompt and not message.attachments:
            return

        print(f"====Received prompt: {prompt[:120]} from {message.author}\n====")
        
        target_channel_id = message.channel.id

        if not is_thread and not is_dm:
            # Create a thread for the first message
            try:
                thread_name = await self.generate_thread_summary(prompt if prompt else "Attachment")
                thread = await message.create_thread(name=thread_name)
                target_channel_id = thread.id
                db.set_thread_active(thread.id, True)
                print(f"Created thread {thread_name} ({thread.id})")
            except Exception as e:
                print(f"Failed to create thread: {e}")
                try:
                    existing_thread = message.channel.get_thread(message.id)
                    if not existing_thread and message.guild:
                        existing_thread = await message.guild.fetch_channel(message.id)
                    
                    if existing_thread:
                        target_channel_id = existing_thread.id
                        db.set_thread_active(target_channel_id, True)
                        print(f"Joined existing thread ({target_channel_id})")
                except Exception as fetch_error:
                    print(f"Failed to fetch existing thread: {fetch_error}")

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


    async def _prepare_gemini_args(self, prompt, channel_id, author_id, channel):
        """Prepare command line arguments and environment variables for the Gemini CLI."""
        cwd = self.gemini_config.get('workspace', '.')
        gemini_exec = self.gemini_config.get('executable_path', 'gemini')
        args = [gemini_exec] # Start with the executable path
        
        # Check if the user specified YOLO mode (skip confirmation)
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
                
        args.extend(['-o', 'stream-json'])
            
        include_dirs = self.gemini_config.get('include_directories', [])
        for inc_dir in include_dirs:
            args.extend(['--include-directories', inc_dir])
            
        attachments_dir = self.gemini_config.get('attachments_dir', 'attachments')
        if os.path.isabs(attachments_dir):
            if attachments_dir not in include_dirs:
                args.extend(['--include-directories', attachments_dir])

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
            if not prompt.startswith('[Previous Context]'):
                prompt = f"{author_name}: {prompt}"
        args.extend(['-p', prompt])

        system_prompt_content = f'Identity: Your name is <@{self.user.name}>.\n'
        system_prompt_content += 'If you want to send a file to the user as an attachment, use the exact syntax: [attachment: path/to/file]. The bot will extract this tag and upload the file to Discord.'

        topic = None
        if isinstance(channel, discord.Thread):
            if hasattr(channel.parent, 'topic'):
                topic = channel.parent.topic
        elif isinstance(channel, discord.TextChannel):
            topic = channel.topic
        
        if topic and topic.strip():
            system_prompt_content += f"\nInstructions: {topic.strip()}"
        
        system_prompt_path = f"/tmp/gemini_system_{channel_id}_{self.user.id}.md"
        with open(system_prompt_path, "w") as f:
            f.write(system_prompt_content)
            
        env = os.environ.copy()
        if 'api_key' in self.gemini_config:
            env['GOOGLE_API_KEY'] = self.gemini_config['api_key']
        if 'project' in self.gemini_config:
            env['GOOGLE_CLOUD_PROJECT'] = self.gemini_config['project']
        if 'location' in self.gemini_config:
            env['GOOGLE_CLOUD_LOCATION'] = self.gemini_config['location']
        env['GEMINI_SYSTEM_MD'] = system_prompt_path

        return args, env, cwd, system_prompt_path

    async def _execute_gemini_command(self, args, env, cwd):
        """Execute the Gemini CLI command as a subprocess with standard output pipes."""
        return await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env
        )

    async def _stream_gemini_output(self, process, channel, author_id, msg_id_db, timeout_seconds):
        """Read output stream from Gemini process, send chunks to Discord, and return final response."""
        final_response = ""
        
        # Try to find the starter message author if we are in a thread
        starter_author_id = None
        if channel and isinstance(channel, discord.Thread):
            try:
                starter_msg = await channel.parent.fetch_message(channel.id)
                starter_author_id = str(starter_msg.author.id)
            except Exception:
                pass
        
        reply_author_id = author_id if (author_id != str(self.user.id) and author_id != starter_author_id) else None
        prefix = f"<@{reply_author_id}>\n" if reply_author_id else ""
        
        sender = StreamSender(self, channel, prefix)

        async def read_stream():
            nonlocal final_response
            while True:
                line = await asyncio.wait_for(process.stdout.readline(), timeout=timeout_seconds)
                if not line:
                    break
                
                line_str = line.decode().strip()
                if not line_str:
                    continue

                try:
                    parsed = json.loads(line_str)
                    if parsed.get("type") == "message" and parsed.get("role") == "assistant":
                        content = parsed.get("content", "")
                        final_response += content
                        await sender.send(content)
                    elif parsed.get("type") == "result":
                        pass
                    elif parsed.get("session_id"):
                        db.set_thread_session(channel.id, parsed.get("session_id"))
                except json.JSONDecodeError:
                    pass

        try:
            async with channel.typing():
                await read_stream()

            await sender.flush()

            await process.wait()
            stderr_output = await process.stderr.read()
            error = stderr_output.decode().strip()

            if not final_response:
                if error:
                    final_response = f"Error: {error}"
                    if sender.msg_to_edit:
                        await sender.msg_to_edit.edit(content=final_response)
                else:
                    final_response = "Gemini completed but returned no output."

        except asyncio.TimeoutError:
            try:
                process.kill()
            except Exception:
                pass
            final_response = f"Error: Gemini command timed out after {timeout_seconds} seconds."
            if sender.msg_to_edit:
                try:
                    await sender.msg_to_edit.edit(content=final_response)
                except:
                    pass

        if not sender.streamed and final_response:
            await sender.send(final_response, flush=True)

        return final_response

    async def _handle_outbound_attachments(self, final_response, channel, cwd):
        """Extract [attachment: path] tags from final__response and upload files to Discord."""
        outbound_files = []
        if final_response:
            for match in re.finditer(r'\[attachment:\s*(.+?)\]', final_response):
                path = match.group(1).strip()
                full_path = os.path.abspath(os.path.normpath(os.path.join(cwd, path)))
                if os.path.isfile(full_path):
                    if full_path not in outbound_files:
                        outbound_files.append(full_path)

        if outbound_files:
            for i in range(0, len(outbound_files), 10):
                batch_paths = outbound_files[i:i+10]
                discord_files = []
                for path in batch_paths:
                    try:
                        discord_files.append(discord.File(path))
                    except Exception as e:
                        print(f"Error preparing file {path}: {e}")
                
                if discord_files:
                    try:
                        await channel.send("", files=discord_files)
                    except Exception as e:
                        print(f"Error sending files: {e}")
                        await channel.send(f"Failed to send some attachments: {e}")


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
        print(f"====Processing message {msg_id_db}: {prompt[:120]}\n====")
        
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
                print(f"Could not fetch channel {channel_id}, skipping message.")
                db.update_message_status(msg_id_db, 'failed', 'Channel not found or deleted')
                return

        system_prompt_path = None
        try:
            args, env, cwd, system_prompt_path = await self._prepare_gemini_args(prompt, row['channel_id'], author_id, channel)
            
            print(f"====system prompt file created: {system_prompt_path}")
            print('====prompt:', prompt[:120], f'...{len(prompt)} chars' if len(prompt) > 120 else '')
            print('====')
            
            process = await self._execute_gemini_command(args, env, cwd)
            
            timeout_seconds = self.gemini_config.get('timeout', 600)
            final_response = await self._stream_gemini_output(process, channel, author_id, msg_id_db, timeout_seconds)

            db.update_message_status(msg_id_db, 'completed', final_response)
            
            # Send attachments
            await self._handle_outbound_attachments(final_response, channel, cwd)

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
