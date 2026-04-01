# Automatic Backup and Maintenance Using Cronjobs

GeminiClaw supports executing scheduled tasks via cronjobs. While you can use cronjobs to send daily weather updates or news summaries to a Discord channel, one of their most powerful uses is **Automated Memory Management and Backup** when combined with the [GeminiClawDock](https://github.com/codescv/GeminiClawDock) structure.

## The Problem: Memory Clutter

As you chat with the bot, it logs events in its short-term memory (`notes/Daily/`). Over time, this folder can become cluttered with hundreds of daily logs, making it harder for the bot to find important information.

## The Solution: Scheduled Consolidation

You can create a cronjob that periodically wakes up the agent and asks it to review its recent short-term memories, summarize them, and move the important extracted facts into long-term memory (`notes/Memory.md`).

### 1. Create a Maintenance Prompt

Create a prompt file, for example `notes/Cronjobs/memory_consolidation.md`, with instructions like:

```markdown
Please review the recent log files in the `notes/Daily/` folder.
Extract any important user facts, ongoing project details, or persistent preferences that you learned recently.
Append these important facts to `notes/Memory.md` so you don't forget them.
Afterwards, summarize what you did.
```

### 2. Configure the Cronjob

Open your `config.toml` and add the cronjob section. You can set it to run silently in the background every night at midnight.

```toml
[[cronjob]]
# Run daily at 00:00 (Midnight)
schedule = "0 0 * * *"
# The task instruction you created
prompt = "notes/Cronjobs/memory_consolidation.md"
# An admin channel ID where the summary report will be posted
channel_id = "123456789012345678" 
# Run silently if you prefer not to see the report in Discord
silent = false
```

### Other Backup Ideas

Using the same cronjob mechanism, you can automate other background tasks:
- **Git Backup**: Create a prompt that asks the agent to run `git add .`, `git commit -m "Daily backup"`, and `git push` to automatically back up its notes vault to GitHub.
- **Log Cleanup**: Schedule a weekly job that asks the agent to delete temporary experimental files in the `temp/` folder to free up space.
