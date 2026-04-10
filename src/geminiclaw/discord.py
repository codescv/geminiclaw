import os
import re
import subprocess
import signal
import discord
from discord.ext import commands

from . import db

class StreamSender:
    def _clean_message(self, text):
        return re.sub(r'\[attachment:\s*.*?\]', '', text)

    def _split_elegant(self, text):
        max_len = self.bot.max_response_length
        last_newline = text[:max_len].rfind('\n')
        if last_newline != -1:
            return text[:last_newline+1], text[last_newline+1:]
        return text[:max_len], text[max_len:]

    def __init__(self, bot, channel):
        self.bot = bot
        self.channel = channel
        self.msg_to_edit = None
        self.current_chunk = ""
        self.streamed = False

    async def send(self, text=None, flush=False):
        if text is not None:
            self.current_chunk += text
            
        self.current_chunk = self._clean_message(self.current_chunk)
        if not self.current_chunk:
            return

        if self.msg_to_edit:
            if len(self.current_chunk) > self.bot.max_response_length:
                first_part, residue = self._split_elegant(self.current_chunk)
                final_text = first_part
                await self.msg_to_edit.edit(content=final_text)
                
                self.msg_to_edit, last_text = await self.send_smart_chunks(residue, incomplete=not flush)
                self.current_chunk = "" if flush else last_text
            else:
                suffix = "" if flush else " (incomplete)"
                final_text = self.current_chunk
                await self.msg_to_edit.edit(content=final_text + suffix)
                if flush:
                    self.current_chunk = ""
        else:
            if flush:
                await self.send_smart_chunks(self.current_chunk)
                self.current_chunk = ""
            else:
                self.msg_to_edit = await self.channel.send(self.current_chunk + " (incomplete)")
                self.streamed = True

    async def flush(self):
        await self.send(flush=True)

    async def send_smart_chunks(self, text, incomplete=False):
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
        return last_msg, current_chunk

    async def _send_chunk_impl(self, chunk, is_last=False, incomplete=False):
        clean_chunk = self._clean_message(chunk)
        if chunk.strip() and not clean_chunk.strip():
            return None
        
        suffix = " (incomplete)" if is_last and incomplete else ""
        content = clean_chunk + suffix
        msg = await self.channel.send(content)
        return msg


class DiscordBot(commands.Bot):
    def __init__(self, gemini_config, service_name="com.codescv.geminiclaw", cronjobs=None, prompt_config=None, always_reply=None, stream_off_channels=None, max_response_length=1900, policy=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service_name = service_name
        self.gemini_config = gemini_config
        self.always_reply = always_reply or []
        self.max_response_length = max_response_length
        self.agent = None  # Will be set by main()

    async def on_ready(self):
        print(f'Logged in as {self.user.name} ({self.user.id})')
        if self.agent:
            self.loop.create_task(self.agent.process_pending_messages_loop())
            await self.agent.start_cronjobs()

    def is_stream_off(self, channel_id: str, channel=None) -> bool:
        stream_off = str(channel_id) in self.stream_off_channels
        if channel and isinstance(channel, discord.Thread) and getattr(channel, 'parent_id', None):
            stream_off = stream_off or (str(channel.parent_id) in self.stream_off_channels)
        return stream_off

    async def create_stream_sender(self, channel_id: str, channel=None):
        if not channel:
            channel = self.get_channel(int(channel_id))
            if not channel:
                channel = await self.fetch_channel(int(channel_id))
        return StreamSender(self, channel)

    async def process_pending_messages(self):
        if self.agent:
            busy_threads = list(self.agent.running_processes.keys())
            row = db.get_next_processable_message(busy_threads)
            if row:
                msg_id_db = row['id']
                db.update_message_status(msg_id_db, 'processing')
                self.agent.running_processes[str(row['channel_id'])] = None
                await self.agent.process_single_message(row)

    async def generate_thread_summary(self, prompt):
        cleaned = re.sub((r'\s*' f'@{self.user.name}' r'\s*'), '', prompt)
        lines = [line.strip() for line in cleaned.split('\n') if line.strip()]
        summary = lines[0] if lines else cleaned[:30].strip()
        return summary[:30] if len(summary) > 5 else "Thread"

    async def on_message_edit(self, before, after):
        if after.author == self.user:
            return
        if before.content.endswith(" (incomplete)") and not after.content.endswith(" (incomplete)"):
            await self.on_message(after)

    async def on_message(self, message):
        if message.author == self.user:
            return
        if message.content.endswith(" (incomplete)"):
            return

        is_thread = isinstance(message.channel, discord.Thread)
        is_dm = isinstance(message.channel, discord.DMChannel)
        is_bot_mentioned = self.user.mentioned_in(message)

        print(f"===Received Message: {message.content[:120]} (first 120 chars)\nfrom {message.author}\n"
              f"is_thread: {is_thread}\n is_dm: {is_dm}\n is_bot_mentioned: {is_bot_mentioned}")

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

        if message.content.strip().lower() == "-kill":
            chan_id_str = str(message.channel.id)
            if self.agent and chan_id_str in self.agent.running_processes:
                process = self.agent.running_processes[chan_id_str]
                if process:
                    print(f'killing process: {process.pid} for channel {chan_id_str}')
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    try:
                        await message.add_reaction("💀")
                    except Exception:
                        pass
                else:
                    print(f"Can't find the process to kill. Channel Id: {chan_id_str}")
            else:
                print(f"Can't find the process to kill. Channel Id: {chan_id_str}")
            return

        if message.content.strip().lower() == "-restart":
            try:
                await message.add_reaction("🔄")
                subprocess.Popen([
                    "geminiclaw", 
                    "service", 
                    "restart", 
                    "--service-name", 
                    self.service_name
                ], start_new_session=True)
            except Exception as e:
                print(f"Failed to run restart command: {e}")
            return

        if is_thread and db.has_thread(message.channel.id) and not db.is_thread_active(message.channel.id):
            print("Thread is deactivated. Ignoring all message until -continue.")
            return

        should_reply = False
        is_new_thread_participant = False

        is_always_reply = False
        if not is_thread and not message.mentions and self.always_reply:
            if str(message.author.id) in self.always_reply or message.author.name in self.always_reply:
                is_always_reply = True

        if is_bot_mentioned or is_dm or is_always_reply:
            print('Replying to a message (mention, DM, or always_reply)')
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
                        print(f'Recovering thread state for thread {message.channel.id}')
                        is_new_thread_participant = True
                        db.set_thread_active(message.channel.id, True)
                        should_reply = True
                except Exception as e:
                    print(f"Error fetching starter message: {e}")
            else:
                print("Thread inactive, stop replying.")

        if not should_reply:
            return

        prompt = message.content
        for user in message.mentions:
            prompt = prompt.replace(f'<@{user.id}>', f'@{user.display_name}').replace(f'<@!{user.id}>', f'@{user.display_name}')
        prompt = prompt.strip()

        if is_new_thread_participant:
            print(f"Fetching history for newly joined thread {message.channel.id}")
            history_text = ""
            try:
                async for msg in message.channel.history(limit=20, before=message):
                    content = msg.clean_content.strip()
                    if content:
                        history_text = f"{content}\n--- Message Above From {msg.author.display_name} <@{msg.author.id}> ---\n" + history_text
                if hasattr(message.channel, 'parent') and message.channel.parent:
                    try:
                        starter_msg = await message.channel.parent.fetch_message(message.channel.id)
                        if starter_msg and starter_msg.id != message.id:
                            content = starter_msg.clean_content.strip()
                            if content:
                                starter_sig = f"{content}\n--- Message Above From {starter_msg.author.display_name} <@{starter_msg.author.id}> ---\n"
                                if not history_text.startswith(starter_sig):
                                    history_text = starter_sig + history_text
                    except Exception as e:
                        pass
                
                if history_text:
                    prompt = f"[Previous Context]\n{history_text.strip()}\n\n[Current Message]\n{prompt}"
            except Exception as e:
                print(f"Error fetching history: {e}")
        
        if not prompt and not message.attachments:
            return
        
        target_channel_id = message.channel.id

        if not is_thread and not is_dm:
            try:
                thread_name = await self.generate_thread_summary(prompt if prompt else "Attachment")
                thread = await message.create_thread(name=thread_name)
                target_channel_id = thread.id
                db.set_thread_active(thread.id, True)
                print(f"Created thread {thread_name} ({thread.id})")
            except Exception as e:
                print(f"Failed to create thread: {e} thread name: {thread_name}")
                try:
                    existing_thread = message.channel.get_thread(message.id)
                    if not existing_thread and message.guild:
                        existing_thread = await message.guild.fetch_channel(message.id)
                    
                    if existing_thread:
                        target_channel_id = existing_thread.id
                        db.set_thread_active(target_channel_id, True)
                        print(f"Joined existing thread ({target_channel_id})")
                    else:
                        print("Thread error.")
                        return
                except Exception as fetch_error:
                    print(f"Failed to fetch existing thread: {fetch_error}")
                    return

        attachments_paths = []
        if message.attachments:
            import json
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

        import json
        attachments_json = json.dumps(attachments_paths) if attachments_paths else None
        db.insert_message(target_channel_id, message.id, message.author.id, prompt, attachments=attachments_json)
        await message.add_reaction('✅')
