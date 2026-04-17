import os
import signal
import json
import asyncio
import subprocess
import time
import re
import random
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from . import db
from . import utils
from .chatbot import ChatBot

logger = utils.setup_logger(__name__)

OUTPUT_BUFFER_LIMIT = 2 ** 20  # 1MB
NO_REPLY = "NO_REPLY"

class Agent:
    """
    The primary Agent class that bridges the Chat interface with the Gemini CLI.
    
    It manages subprocess execution, cron-based scheduled tasks, message stream mapping,
    and routing logic for multi-bot interactions.
    """

    def __init__(self,
        bot: ChatBot,
        gemini_config: dict,
        prompt_config: dict = None,
        policy: list = None,
        cronjobs: list = None):
        """
        Initialize the Agent with bot capabilities and configurations.

        Args:
            bot: The running chat bot instance.
            gemini_config: Configuration mapping for the Gemini CLI (e.g., timeout, workspace).
            prompt_config: Paths to prompt templates.
            policy: A list of policy definitions to pass to the Gemini CLI.
            cronjobs: Scheduled messaging jobs configurations.
        """
        self.bot = bot
        self.gemini_config = gemini_config
        self.prompt_config = prompt_config or {}
        self.policy = policy or []
        self.cronjobs = cronjobs or []
        
        self.scheduler = AsyncIOScheduler()
        self.running_processes = {}  # map channel_id (str) to subprocess

    @property
    def cwd(self) -> str:
        """Get the working directory for Gemini execution."""
        return self.gemini_config.get('workspace', '.')

    async def start_cronjobs(self):
        """Start the apscheduler context and configure background cron tasks."""
        for job_config in self.cronjobs:
            schedule = job_config.get("schedule")
            prompt_file = job_config.get("prompt")
            channel_id = job_config.get("channel_id")
            mention_user_id = job_config.get("mention_user_id")
            silent = job_config.get("silent", False)
            probability = job_config.get("probability")
            skip_if_empty = job_config.get("skip_if_empty")
            if schedule and prompt_file and (channel_id or silent):
                if not os.path.exists(prompt_file):
                    logger.warning(f"Cronjob prompt file not found at {prompt_file}. Skipping.")
                    continue
                try:
                    self.scheduler.add_job(
                        self.run_cronjob,
                        CronTrigger.from_crontab(schedule),
                        args=[prompt_file, channel_id, mention_user_id, silent, probability, skip_if_empty]
                    )
                    logger.info(f"Added cronjob: {schedule} -> {prompt_file}, report channel: {channel_id}")
                except Exception as e:
                    logger.exception(f"Failed to add cronjob {job_config}: {e}")
            else:
                logger.warning(f"Cronjob skipped {job_config} (missing channel_id, schedule, or prompt file)")
        self.scheduler.start()

    async def run_cronjob(
        self, prompt_file: str,
        channel_id,
        mention_user_id=None,
        silent: bool = False,
        probability=None,
        skip_if_empty=None):
        """
        Execute a configured cronjob, running the underlying Gemini CLI process.

        Args:
            prompt_file: The path to the prompt context file.
            channel_id: Target channel where output is sent (if not silent).
            mention_user_id: Use the tag [mention:<id>] to ping the user.
            silent: If True, runs the CLI process strictly in the background without sending to chat bot.
            probability: Float representing the chance (0.0 to 1.0) that the cronjob runs.
            skip_if_empty: Path to file to check for emptiness.
        """
        if probability is not None:
            try:
                prob = float(probability)
                if random.random() > prob:
                    logger.info(f"Cronjob {prompt_file} skipped due to probability ({prob})")
                    return
            except ValueError:
                logger.exception(f"Cronjob Error: Invalid probability value {probability}")
                
        if skip_if_empty:
            check_path = skip_if_empty if os.path.isabs(skip_if_empty) else os.path.join(self.cwd, skip_if_empty)
            if not os.path.exists(check_path):
                logger.info(f"Cronjob {prompt_file} skipped because {skip_if_empty} is missing.")
                return
            try:
                with open(check_path, "r") as f:
                    content = f.read()
                if len(content.strip()) == 0:
                    logger.info(f"Cronjob {prompt_file} skipped because {skip_if_empty} is empty.")
                    return
            except Exception as e:
                logger.exception(f"Error reading skip_if_empty file {check_path}: {e}")
                
        try:
            if not os.path.exists(prompt_file):
                logger.error(f"Cronjob Error: Prompt file not found at {prompt_file}")
                return

            with open(prompt_file, "r") as f:
                prompt = f.read().strip()
            if not prompt:
                logger.error(f"Cronjob Error: Prompt file {prompt_file} is empty.")
                return

            if silent:
                logger.info(f"Cronjob triggered (silent): {prompt_file} scheduled running in background")
                try:
                    process, system_prompt_path = await self._execute_gemini_command(prompt, channel_id, self.bot.user_id, True)
                    stdout, stderr = await process.communicate()
                    if process.returncode != 0:
                        logger.error(f"Silent cronjob {prompt_file} failed: {stderr.decode().strip()}")
                    else:
                        logger.info(f"Silent cronjob {prompt_file} completed successfully.")
                    if system_prompt_path and os.path.exists(system_prompt_path):
                        os.remove(system_prompt_path)
                except Exception as e:
                    logger.exception(f"Error executing silent cronjob {prompt_file}: {e}")
                return

            if mention_user_id:
                prompt = f"[mention:{mention_user_id}]{prompt}"

            db.insert_message(channel_id, "0", self.bot.user_id, prompt)
            logger.info(f"Cronjob triggered: {prompt_file} scheduled running in channel {channel_id}")

        except Exception as e:
            logger.exception(f"Error running cronjob {prompt_file}: {e}")

    async def _execute_gemini_command(
        self, prompt: str,
        channel_id,
        author_id,
        is_cronjob: bool = False):
        """Construct and invoke the Gemini CLI subprocess for a given prompt context."""
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

        for p in self.policy:
            args.extend(['--policy', p])

        thread_session = db.get_thread_session(channel_id)
        if thread_session:
            args.extend(['-r', thread_session])
        else:
            logger.info(f"Creating a new session for {channel_id}")
        
        if is_cronjob or self.bot.is_stream_off(str(channel_id)):
            args.extend(['-o', 'json'])
        else:
            args.extend(['-o', 'stream-json'])
            
        include_dirs = self.gemini_config.get('include_directories', [])
        for inc_dir in include_dirs:
            args.extend(['--include-directories', inc_dir])
            
        attachments_dir = self.gemini_config.get('attachments_dir', 'attachments')
        if os.path.isabs(attachments_dir):
            if attachments_dir not in include_dirs:
                args.extend(['--include-directories', attachments_dir])

        author_name = await self.bot.get_author_name(author_id)
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        if author_id != self.bot.user_id:
            # Cronjobs will have a message with the bot user id, and we don't append anything
            prompt = (
                f"{prompt}\n"
                f"--- Message Above From {author_name} at {timestamp} ---\n"
            )
        args.extend(['-p', prompt])
        
        system_prompt_content = ""
        
        try:
            import importlib.resources
            content = importlib.resources.files("geminiclaw.resources").joinpath("system.md").read_text()
            if content:
                system_prompt_content += (
                    f"---BEGIN SYSTEM PROMPT---\n"
                    f"{content}\n"
                    "---END SYSTEM PROMPT---\n\n"
                )
        except Exception as e:
            logger.warning(f"Failed to read system prompt from resources: {e}")

        if hasattr(self, 'prompt_config') and self.prompt_config:
            user_paths = self.prompt_config.get("user")
            if user_paths:
                if isinstance(user_paths, str):
                    user_paths = [user_paths]
                for path in user_paths:
                    full_path = path if os.path.isabs(path) else os.path.join(self.cwd, path)
                    if os.path.exists(full_path):
                        try:
                            with open(full_path, "r") as f:
                                content = f.read().strip()
                            if content:
                                filename = os.path.basename(path)
                                system_prompt_content += (
                                    f"---BEGIN {filename}---\n"
                                    f"{content}\n"
                                    f"---END {filename}---\n\n"
                                )
                        except Exception as e:
                            logger.warning(f"Failed to read user prompt from {full_path}: {e}")
        
        system_prompt_content += await self.bot.get_system_instructions(channel_id)

        timestamp_val = int(time.time())
        safe_author_id = str(author_id).replace('/', '_').replace(':', '_')
        system_prompt_path = f"/tmp/gemini_system_{safe_author_id}_{timestamp_val}.md"
        
        with open(system_prompt_path, "w") as f:
            f.write(system_prompt_content)
            
        env = os.environ.copy()
        if 'api_key' in self.gemini_config:
            env['GOOGLE_API_KEY'] = self.gemini_config['api_key']
        if 'project' in self.gemini_config:
            env['GOOGLE_CLOUD_PROJECT'] = self.gemini_config['project']
        if 'location' in self.gemini_config:
            env['GOOGLE_CLOUD_LOCATION'] = self.gemini_config['location']
        if self.gemini_config.get('cli_home') is not None:
            env['GEMINI_CLI_HOME'] = str(self.gemini_config['cli_home'])
        env['GEMINI_SYSTEM_MD'] = system_prompt_path
        if self.gemini_config.get('sandbox') == True:
            env['SEATBELT_PROFILE'] = 'geminiclaw'

        process = await asyncio.create_subprocess_exec(
            *args,
            stdin=subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=OUTPUT_BUFFER_LIMIT,
            cwd=self.cwd,
            env=env,
            start_new_session=True
        )
        return process, system_prompt_path

    async def _get_gemini_output(self, process, channel_id, author_id, msg_id_db, timeout_seconds, is_cronjob: bool = False, prompt: str = "", mention_user_id=None):
        """Collect synchronous (buffered) output from the Gemini CLI."""
        final_response = ""
        error = ""
        gemini_session_id = ""
        
        try:
            async with self.bot.typing(channel_id):
                stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
                output = stdout_bytes.decode().strip()
                error = stderr_bytes.decode().strip()
                
                if output:
                    try:
                        parsed = json.loads(output)
                        if isinstance(parsed, dict):
                            response_text = parsed.get("response", "")
                            if response_text:
                                final_response = response_text

                            if parsed.get("session_id"):
                                gemini_session_id = parsed.get("session_id")
                                db.set_thread_session(channel_id, gemini_session_id)
                                
                    except json.JSONDecodeError:
                        logger.exception(f"json error: {output}")
                        
            if not final_response:
                if isinstance(process.returncode, int) and process.returncode < 0:
                    final_response = "Stopped by user."
                elif error:
                    final_response = f"Error: {error}"
                else:
                    final_response = "Gemini completed but returned no output."
                    
        except asyncio.TimeoutError:
            try:
                if isinstance(process.pid, int):
                    os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            final_response = f"Error: Gemini command timed out after {timeout_seconds} seconds."

        if NO_REPLY in final_response:
            return NO_REPLY, channel_id
        
        match = re.search(r'\[to_channel:\s*(\d+)\]', final_response)
        if match:
            target_id = match.group(1)
            if await self.bot.channel_exists(target_id):
                print(f"Routing response to channel {target_id}")
                channel_id = target_id
                final_response = final_response.replace(match.group(0), "").strip()

        if is_cronjob and final_response:
            channel_id = await self.bot.ensure_thread_for_cronjob(channel_id, prompt, mention_user_id, gemini_session_id)

        if final_response:
            await self.bot.send_message(channel_id, final_response)

        return final_response, channel_id

    async def _stream_gemini_output(self, process, channel_id, author_id, msg_id_db, timeout_seconds):
        """Process standard asynchronous stream output from the Gemini CLI."""
        final_response = ""
        await self.bot.stream_start(channel_id)

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
                        await self.bot.stream_send(channel_id, content)
                    elif parsed.get("type") == "result":
                        logger.info(f"result: {parsed}")
                    elif parsed.get("session_id"):
                        db.set_thread_session(channel_id, parsed.get("session_id"))
                except json.JSONDecodeError:
                    logger.exception(f"json error: {line_str}")

        error = ""
        stderr_output = ""
        try:
            async with self.bot.typing(channel_id):
                await read_stream()

            # wait for process to finish
            await process.wait()
            stderr_output = (await process.stderr.read()).decode().strip()

            if isinstance(process.returncode, int) and process.returncode < 0:
                error = "Stopped by user."

        except asyncio.TimeoutError:
            try:
                if isinstance(process.pid, int):
                    os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            error = f"Error: Gemini command timed out after {timeout_seconds} seconds."
        except:
            error = stderr_output

        await self.bot.stream_end(channel_id, error=error)

        return final_response


    async def process_single_message(self, row):
        """Retrieve, lock, execute, and deliver a single database message record to the agent."""
        msg_id_db = row['id']
        channel_id = row['channel_id']
        prompt = row['prompt']
        author_id = row['author_id']
        attachments_json = row['attachments'] if 'attachments' in row.keys() else None

        mention_user_id = None
        if prompt.startswith("[mention:"):
            match = re.search(r'\[mention:(\d+)\]', prompt)
            if match:
                mention_user_id = match.group(1)
                prompt = prompt[match.end():].strip()

        logger.info(f"Processing message {msg_id_db} from {author_id}:(first 120 chars)\n{prompt[:120]}\nattachments: {attachments_json}\n")
        
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
        
        if not await self.bot.channel_exists(str(channel_id)):
            logger.warning(f"Could not fetch channel {channel_id}, skipping message.")
            db.update_message_status(msg_id_db, 'failed', 'Channel not found or deleted')
            self.running_processes.pop(str(row['channel_id']), None)
            return

        system_prompt_path = None
        try:
            is_cronjob = str(dict(row).get('message_id', '')) == "0"
            process, system_prompt_path = await self._execute_gemini_command(prompt, str(channel_id), author_id, is_cronjob=is_cronjob)
            self.running_processes[str(row['channel_id'])] = process

            logger.info(f"system prompt file for message {msg_id_db} created: {system_prompt_path}")
            
            timeout_seconds = self.gemini_config.get('timeout', 600)
            
            if self.bot.is_stream_off(str(channel_id)) or is_cronjob:
                final_response, actual_channel_id = await self._get_gemini_output(
                    process, str(channel_id), author_id, msg_id_db, timeout_seconds, 
                    is_cronjob=is_cronjob, prompt=prompt, mention_user_id=mention_user_id
                )
            else:
                final_response = await self._stream_gemini_output(process, str(channel_id), author_id, msg_id_db, timeout_seconds)
                actual_channel_id = str(channel_id)

            db.update_message_status(msg_id_db, 'completed', final_response)

            if final_response == NO_REPLY:
                logger.info(f"Skipped reply for message {msg_id_db} prompt: {prompt[:120]}\n")
                return

            await self.bot.update_idle_thread_name(actual_channel_id, final_response)

            db.update_message_status(msg_id_db, 'delivered')

        except Exception as e:
            logger.exception(f"Error processing message {msg_id_db}")
            db.update_message_status(msg_id_db, 'failed', str(e))
        finally:
            self.running_processes.pop(str(row['channel_id']), None)
            if system_prompt_path and os.path.exists(system_prompt_path):
                try:
                    os.remove(system_prompt_path)
                    logger.info(f"Cleaned up system prompt file: {system_prompt_path}")
                except Exception as e:
                    logger.exception(f"Failed to remove temp system prompt file {system_prompt_path}: {e}")

    async def process_pending_messages_loop(self):
        """Listen to the polling layer for pending tasks and trigger concurrent handlers."""
        while True:
            try:
                busy_threads = list(self.running_processes.keys())
                row = db.get_next_processable_message(busy_threads)
                if not row:
                    await asyncio.sleep(5)
                    continue

                msg_id_db = row['id']
                db.update_message_status(msg_id_db, 'processing')
                self.running_processes[str(row['channel_id'])] = None
                
                asyncio.create_task(self.process_single_message(row))
            except Exception as e:
                logger.exception(f"Error in process_pending_messages loop: {e}")
                await asyncio.sleep(5)
