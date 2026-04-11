# Template

# {Task Name}
- Context: What this task does (useful for reporting it later to the user).
- PID: The PID of the background task. Note: this is **NOT** the PID of `nohup`, but the PID of the actual command. You need to use `ps` or `pgrep` to get the PID of the actual command. `nohup` will be killed once you finish your reply.
- Condition: How to check if the task succeeds? (Result files, log files etc)
- Expiration: When will this task be considered expired. Set a tolerant expiration time. If you estimate it should take 1 hour, set it to 2 hours. Max is 3 days.
- Channel ID: the discord channel id where this task is created.

Please keep the above as a template end edit from the line below.
---
