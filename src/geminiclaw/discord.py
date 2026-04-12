import os
import re
import subprocess
import signal
import discord
from discord.ext import commands

from . import db
from . import utils

logger = utils.setup_logger(__name__)

class StreamSender:
    def _clean_message(self, text):
        return re.sub(r'\[attachment:\s*.*?\]', '', text)

    def _split_elegant(self, text):
        max_len = self.bot.MAX_RESPONSE_LENGTH
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

    async def _send_current_chunk(self, flush=False):
        if not self.current_chunk:
            return

        # logger.info(f"current chunk: {self.current_chunk} flush: {flush}")

        if self.msg_to_edit:
            if len(self.current_chunk) > self.bot.MAX_RESPONSE_LENGTH:
                first_part, residue = self._split_elegant(self.current_chunk)
                edited_message = first_part
                await self.msg_to_edit.edit(content=edited_message)
                
                self.msg_to_edit, last_text = await self.send_smart_chunks(residue, incomplete=not flush)
                self.current_chunk = "" if flush else last_text
            else:
                suffix = "" if flush else " (incomplete)"
                edited_message = self.current_chunk + suffix
                # logger.info(f"edit message to: '{edited_message}'")
                if len(edited_message.strip()) == 0:
                    edited_message = "\u200b"  # avoid empty message
                await self.msg_to_edit.edit(content=edited_message)
                if flush:
                    self.current_chunk = ""
        else:
            if flush:
                await self.send_smart_chunks(self.current_chunk)
                self.current_chunk = ""
            else:
                self.msg_to_edit = await self.channel.send(self.current_chunk + " (incomplete)")
                self.streamed = True

    async def send(self, text=None, flush=False):
        if text is not None:
            self.current_chunk += text
            
        while True:
            match = re.search(r'\[attachment:\s*(.+?)\]', self.current_chunk)
            if not match:
                break
                
            before_text = self.current_chunk[:match.start()]
            path = match.group(1).strip()
            after_text = self.current_chunk[match.end():]
            
            self.current_chunk = before_text
            if self.current_chunk or self.msg_to_edit:
                await self._send_current_chunk(flush=True)
                
            cwd = self.bot.gemini_config.get('workspace', '.')
            full_path = os.path.abspath(os.path.normpath(os.path.join(cwd, path)))
            logger.info(f"send attachment path: {full_path}")
            if os.path.isfile(full_path):
                await self.bot.send_attachments(self.channel.id, [full_path])
                
            self.current_chunk = after_text
            self.msg_to_edit = None
            
        await self._send_current_chunk(flush=flush)

    async def flush(self):
        await self.send(flush=True)

    async def send_smart_chunks(self, text, incomplete=False):
        lines = text.splitlines(keepends=True)
        current_chunk = ""
        last_msg = None
        
        for line in lines:
            if len(current_chunk) + len(line) <= self.bot.MAX_RESPONSE_LENGTH:
                current_chunk += line
            else:
                if current_chunk:
                    last_msg = await self._send_chunk_impl(current_chunk)
                
                residue = line
                while len(residue) > self.bot.MAX_RESPONSE_LENGTH:
                    last_msg = await self._send_chunk_impl(residue[:self.bot.MAX_RESPONSE_LENGTH])
                    residue = residue[self.bot.MAX_RESPONSE_LENGTH:]
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
    MAX_RESPONSE_LENGTH = 1900

    def __init__(self, gemini_config, service_name="com.codescv.geminiclaw", cronjobs=None, prompt_config=None, always_reply=None, stream_off_channels=None, policy=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service_name = service_name
        self.gemini_config = gemini_config
        self.always_reply = always_reply or []
        self.stream_off_channels = stream_off_channels or []
        self.agent = None  # Will be set by main()
        self._active_streams = {}

    async def on_ready(self):
        print(f'Logged in as {self.user.name} ({self.user.id})')
        if self.agent:
            self.loop.create_task(self.agent.process_pending_messages_loop())
            await self.agent.start_cronjobs()

    def get_channel_from_id_sync(self, channel_id: str):
        """Safely get a channel from ID from cache, handling None and type conversion."""
        if not channel_id:
            return None
        try:
            return self.get_channel(int(channel_id))
        except (ValueError, TypeError):
            return None

    async def get_channel_from_id(self, channel_id: str):
        """Safely get a channel from ID, handling None, cache lookup, and API fetch."""
        channel = self.get_channel_from_id_sync(channel_id)
        if not channel and channel_id:
            try:
                channel = await self.fetch_channel(int(channel_id))
            except (discord.HTTPException, ValueError, TypeError):
                pass
        return channel

    def is_stream_off(self, channel_id: str) -> bool:
        stream_off = str(channel_id) in self.stream_off_channels
        channel = self.get_channel_from_id_sync(channel_id)
        if channel and isinstance(channel, discord.Thread) and getattr(channel, 'parent_id', None):
            stream_off = stream_off or (str(channel.parent_id) in self.stream_off_channels)
        return stream_off

    async def stream_start(self, channel_id: str):
        channel = await self.get_channel_from_id(channel_id)
        sender = StreamSender(self, channel)
        self._active_streams[str(channel_id)] = sender

    async def stream_send(self, channel_id: str, chunk: str):
        sender = self._active_streams.get(str(channel_id))
        if sender:
            await sender.send(chunk)

    async def stream_end(self, channel_id: str, error: str = None):
        sender = self._active_streams.pop(str(channel_id), None)
        if sender and error:
            await sender.send(error)
        elif sender:
            await sender.flush()

    async def channel_exists(self, channel_id: str) -> bool:
        channel = await self.get_channel_from_id(channel_id)
        return channel is not None

    async def get_channel_topic(self, channel_id: str) -> str:
        channel = await self.get_channel_from_id(channel_id)
        if channel:
            if isinstance(channel, discord.Thread) and hasattr(channel.parent, 'topic'):
                return channel.parent.topic
            elif hasattr(channel, 'topic'):
                return channel.topic
        return ""

    async def get_channel_users_str(self, channel_id: str) -> str:
        channel = await self.get_channel_from_id(channel_id)
        if not channel:
            logger.error(f"Can't get channel {channel_id}")
            return ""

        user_list_str = ""
        try:
            members = []
            if getattr(channel, 'type', None) == discord.ChannelType.private:
                if hasattr(channel, 'recipient') and channel.recipient:
                    members = [channel.recipient]
            elif hasattr(channel, 'members') and not isinstance(channel, discord.Thread):
                members = channel.members
            elif hasattr(channel, 'parent') and hasattr(channel.parent, 'members'):
                members = channel.parent.members
            elif hasattr(channel, 'guild') and hasattr(channel.guild, 'members'):
                members = channel.guild.members
            valid_members = [m for m in members if m.id != self.user.id]
            if valid_members:
                user_lines = []
                for m in valid_members[:5]:
                    name = getattr(m, 'display_name', getattr(m, 'name', 'Unknown'))
                    user_lines.append(f"  - {name} <@{m.id}>")
                user_list_str = "Here are some users in this channel you can mention:\n" + "\n".join(user_lines) + "\n"
        except:
            logger.exception(f"Can't get user list for channel {channel_id}")
        return user_list_str

    async def _send_plain_text(self, channel, text: str):
        if not text.strip():
            return
        lines = text.splitlines(keepends=True)
        chunk = ""
        for line in lines:
            if len(chunk) + len(line) <= self.MAX_RESPONSE_LENGTH:
                chunk += line
            else:
                if chunk.strip():
                    await channel.send(chunk)
                residue = line
                while len(residue) > self.MAX_RESPONSE_LENGTH:
                    part = residue[:self.MAX_RESPONSE_LENGTH]
                    if part.strip():
                        await channel.send(part)
                    residue = residue[self.MAX_RESPONSE_LENGTH:]
                chunk = residue
        if chunk.strip():
            await channel.send(chunk)

    async def send_message(self, channel_id: str, content: str):
        channel = await self.get_channel_from_id(channel_id)
        if channel:
            cwd = self.gemini_config.get('workspace', '.')
            remaining_text = content
            while True:
                match = re.search(r'\[attachment:\s*(.+?)\]', remaining_text)
                if not match:
                    break
                
                before_text = remaining_text[:match.start()]
                path = match.group(1).strip()
                remaining_text = remaining_text[match.end():]
                
                await self._send_plain_text(channel, before_text)
                
                full_path = os.path.abspath(os.path.normpath(os.path.join(cwd, path)))
                if os.path.isfile(full_path):
                    await self.send_attachments(channel_id, [full_path])
                    
            await self._send_plain_text(channel, remaining_text)

    async def send_attachments(self, channel_id: str, file_paths: list[str]):
        channel = await self.get_channel_from_id(channel_id)
        if channel:
            discord_files = []
            for path in file_paths:
                try:
                    discord_files.append(discord.File(path))
                except:
                    pass
            if discord_files:
                await channel.send("", files=discord_files)

    def typing(self, channel_id: str):
        channel = self.get_channel_from_id_sync(channel_id)
        if channel and hasattr(channel, 'typing'):
            return channel.typing()
        from contextlib import asynccontextmanager
        @asynccontextmanager
        async def noop():
            yield
        return noop()

    @property
    def user_id(self) -> str:
        return str(self.user.id) if self.user else ""

    async def get_author_name(self, author_id: str) -> str:
        author = None
        try:
            author_id_int = int(author_id)
            author = self.get_user(author_id_int)
            if not author:
                author = await self.fetch_user(author_id_int)
        except Exception:
            pass
        return f"{author.display_name} <@{author_id}>" if author else f"<@{author_id}>"

    def is_bot_mentioned(self, message: discord.Message) -> bool:
        is_mentioned = self.user.mentioned_in(message)
        if not is_mentioned and getattr(message, 'guild', None) and hasattr(message, 'role_mentions'):
            bot_member = message.guild.get_member(self.user.id)
            if bot_member:
                for role in message.role_mentions:
                    if role in bot_member.roles:
                        return True
        return is_mentioned

    async def get_system_instructions(self, channel_id: str) -> str:
        user_list_str = await self.get_channel_users_str(channel_id)
        topic = await self.get_channel_topic(channel_id)
        
        instructions = (
            "---BEGIN DISCORD INSTRUCTIONS---\n"
            f"You are chatting with the user in a discord channel. (channel id: {channel_id})\n"
            f"Your own discord user name and id is {self.user.name} <@{self.user.id}>.\n"
            "If you want to send a file to the user as an attachment, "
            "use the exact syntax: [attachment: path/to/file].\n"
            "The bot will extract this tag and upload the file to Discord.\n"
            f"{user_list_str}"
            "When you need to mention a user, use the strict syntax with the integer user id: <@user_id>\n"
            "---END DISCORD INSTRUCTIONS---\n\n"
        )
        if topic and topic.strip():
            instructions += (
                f"---BEGIN TOPIC INSTRUCTIONS---\n"
                f"{topic.strip()}\n"
                f"---END TOPIC INSTRUCTIONS---\n\n"
            )
        return instructions

    async def ensure_thread_for_cronjob(self, channel_id: str, prompt: str, mention_user_id: str, gemini_session_id: str) -> str:
        channel = await self.get_channel_from_id(channel_id)
        if channel:
            if not isinstance(channel, discord.Thread) and getattr(channel, 'type', None) != discord.ChannelType.private:
                try:
                    thread_name = await self.generate_thread_summary(prompt if prompt else "Cronjob")
                    thread = await channel.create_thread(name=thread_name, type=discord.ChannelType.public_thread)
                    db.set_thread_active(thread.id, True)
                    logger.info(f"bind thread {thread.id} to gemini session: {gemini_session_id}")
                    if gemini_session_id:
                        db.set_thread_session(thread.id, gemini_session_id)
                    msg_text = f"<@{mention_user_id}>" if mention_user_id else "Executing cronjob...*"
                    await thread.send(msg_text)
                    return str(thread.id)
                except:
                    pass
            else:
                try:
                    msg_text = f"<@{mention_user_id}>" if mention_user_id else "Executing cronjob...*"
                    await channel.send(msg_text)
                except:
                    pass
        return str(channel_id)

    async def update_idle_thread_name(self, channel_id: str, response: str):
        channel = await self.get_channel_from_id(channel_id)
        if channel and isinstance(channel, discord.Thread):
            count = db.get_message_count(channel.id)
            if count <= 4:
                summary = await self.generate_thread_summary(response)
                if summary and summary != channel.name:
                    try:
                        await channel.edit(name=summary)
                    except:
                        pass


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
        is_bot_mentioned = self.is_bot_mentioned(message)

        logger.info(f"Received Message: (first 120 chars)\n{message.content[:120]}\nfrom {message.author}\n"
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
                    logger.info(f'killing process: {process.pid} for channel {chan_id_str}')
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    try:
                        await message.add_reaction("💀")
                    except Exception:
                        pass
                else:
                    logger.warning(f"Can't find the process to kill. Channel Id: {chan_id_str}")
            else:
                logger.warning(f"Can't find the process to kill. Channel Id: {chan_id_str}")
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
                logger.error(f"Failed to run restart command: {e}")
            return

        if len(message.content.strip()) == 0 and not message.attachments:
            # empty message can happen with new thread created by someone else
            logger.info(f"Skipped empty message from {message.author}")
            return

        if is_thread and db.has_thread(message.channel.id) and not db.is_thread_active(message.channel.id):
            logger.info("Thread is deactivated. Ignoring all message until -continue.")
            return

        should_reply = False
        is_new_thread_participant = False

        is_always_reply = False
        if not is_thread and not message.mentions and self.always_reply:
            if str(message.author.id) in self.always_reply or message.author.name in self.always_reply:
                is_always_reply = True

        if is_bot_mentioned or is_dm or is_always_reply:
            if is_thread:
                if not db.has_thread(message.channel.id):
                    is_new_thread_participant = True
                    db.set_thread_active(message.channel.id, True)
                    should_reply = True
                elif db.is_thread_active(message.channel.id):
                    should_reply = True
                else:
                    logging.info(f"Thread {message.channel.id} is deactivated. Ignoring all message until -continue.")
            else:
                should_reply = True
        elif is_thread:
            if db.is_thread_active(message.channel.id):
                if message.mentions:
                    logger.info('Skpping message explicitly mentioning others in active thread')
                else:
                    logger.info('Replying to an active thread')
                    should_reply = True
            else:
                if not db.has_thread(message.channel.id):
                    try:
                        starter_msg = await message.channel.parent.fetch_message(message.channel.id)
                        if self.is_bot_mentioned(starter_msg):
                            # the thread could be created while awaiting. so check again.
                            if not db.has_thread(message.channel.id):
                                logger.info(f'Recovering thread state for thread {message.channel.id}')
                                is_new_thread_participant = True
                                db.set_thread_active(message.channel.id, True)
                                should_reply = True
                    except Exception as e:
                        logger.error(f"Error fetching starter message: {e}")
                else:
                    logger.info("Thread inactive, stop replying.")

        if not should_reply:
            return

        prompt = message.content
        for user in message.mentions:
            prompt = (
                prompt
                .replace(f'<@{user.id}>', f'<@{user.id}>({user.display_name})')
            )
        prompt = prompt.strip()

        if is_new_thread_participant:
            logger.info(f"Fetching history for newly joined thread {message.channel.id}")
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
                logger.error(f"Error fetching history: {e}")
        
        target_channel_id = message.channel.id

        if not is_thread and not is_dm:
            try:
                thread_name = await self.generate_thread_summary(prompt if prompt else "Attachment")
                thread = await message.create_thread(name=thread_name)
                target_channel_id = thread.id
                db.set_thread_active(thread.id, True)
                logger.info(f"Created thread {thread_name} ({thread.id})")
            except Exception as e:
                logger.error(f"Failed to create thread: {e} thread name: {thread_name}")
                try:
                    existing_thread = message.channel.get_thread(message.id)
                    if not existing_thread and message.guild:
                        existing_thread = await message.guild.fetch_channel(message.id)
                    
                    if existing_thread:
                        target_channel_id = existing_thread.id
                        db.set_thread_active(target_channel_id, True)
                        logger.info(f"Joined existing thread ({target_channel_id})")
                    else:
                        logger.error("Thread error.")
                        return
                except Exception as fetch_error:
                    logger.error(f"Failed to fetch existing thread: {fetch_error}")
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
                logger.info(f"Downloaded {len(attachments_paths)} attachments to {attachments_dir}")
            except Exception as e:
                logger.error(f"Failed to download attachments: {e}")

        import json
        attachments_json = json.dumps(attachments_paths) if attachments_paths else None
        db.insert_message(target_channel_id, message.id, message.author.id, prompt, attachments=attachments_json)
        await message.add_reaction('✅')
