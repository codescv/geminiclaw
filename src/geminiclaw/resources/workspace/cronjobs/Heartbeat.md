# Check background tasks
Check `memory/background_tasks.jsonl`.

- Delete the expired tasks.
- Check the status of the running background tasks. If task is finished (successful or failed), also delete it.

# Reporting
- If there are status updates about background tasks, report it to the user. If the task is associated with a channel id, YOU MUST WRITE "[to_channel: {channel_id}]" at the beginning of the message.
- Otherwise, just reply the text "NO_REPLY".