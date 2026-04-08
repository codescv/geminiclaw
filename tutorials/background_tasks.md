# Long-Running Background Tasks in Gemini Claw

Gemini Claw supports running and tracking tasks that take a long time to complete (such as training models, compiling software, or rendering complex videos) without blocking the bot's response loop.

---

## How Background Tasks Work

When a task is expected to run for more than 30 minutes, the agent launches it as a detached process and tracks its lifecycle through local memory files and scheduled heartbeats.

### 1. Running Detached Commands

To prevent a process from being killed when the agent finishes sending its initial reply, the command must be launched in the background using `nohup`:

```bash
nohup <long_running_command> & > <log_file>
```

### 2. Tracking the Task in Memory

Immediately after spawning a background process, the agent records its details into `memory/Background Tasks.md` using the following format:

```markdown
# {Task Name}
- Context: What this task does (used for user reporting).
- PID: The process ID of the actual command (not `nohup`, retrieved via `pgrep` or `ps`).
- Condition: How to determine if the task succeeded (e.g., checking for a specific output file or log success message).
- Expiration: A tolerant timeout period (e.g., 2 hours, max 3 days).
- Channel ID: The Discord channel ID where the task originated.
```

### 3. Automated Heartbeat Monitoring

Gemini Claw monitors background tasks automatically via a scheduled heartbeat cronjob defined in `config.toml`.

- **The Checkup:** Defined by `cronjobs/Heartbeat.md`. Periodically (e.g., every 30 minutes), the background polling loop checks the `memory/Background Tasks.md` file.
- **Actions:**
  - Cleans up any tasks that have expired.
  - Checks if the running tasks have met their completion conditions (success or failure).
  - Reports back any status updates natively to the Discord channel using the `[to_channel: {channel_id}]` routing tag.

