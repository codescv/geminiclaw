---
name: background-task
description: Manage background tasks.
---

For long running processes(e.g. >30min), you can run a command in the background:
- set the `is_background` parameter to true.
- **YOU MUST** use the command `nohup <command> & > <log_file>` to run it detached. Otherwise the process will just be killed when you reply to the user.

Before replying to the user, you must write memory about the task in `memory/background_tasks.jsonl`:
Each task is a json object containing the following keys:
- "context": What this task does (useful for reporting it later to the user).
- "pid": The PID of the background task. Note: this is **NOT** the PID of `nohup`, but the PID of the actual command. You need to use `ps` or `pgrep` to get the PID of the actual command. `nohup` will be killed once you finish your reply.
- "condition": How to check if the task succeeds? (Result files, log files etc)
- "expiration": When will this task be considered expired. Set a tolerant expiration time. If you estimate it should take 1 hour, set it to 2 hours. Max is 3 days.
- "channel_id": the discord channel id where this task is created.
