---
name: cronjob
description: Help the user set up cronjobs that can run periodically.
---

# Gathering Information
Make sure to get the following information from the user:
1. The schedule: user provides in natural language, but you need to convert it to the cron format
2. Which channel will the user be notified? (Tell the user to find it in the url of discord channel: https://discord.com/channels/server_id/channel_id)
3. Do you want to be notified? (Yes/No) If yes, put user's digital user id. If you can't infer the user's digital id, ask them to right click on their avatar and copy user id.
4. Understand task the user wants to accomplish. You will write this task into markdown in the `cronjob/{task_name}.md` file later.

# The Config file
The cronjobs are managed in the `config.toml` file in the "cronjob" array.
Before making changes, **Back up** the old `config.toml` to `config.toml.bak.{1-5}` just in case.
An example is provided below:

```toml
[[cronjob]]
schedule = "*/5 * * * *"                     # Cron schedule expression (convert user's schedule into the cron format)
prompt = "cronjobs/daily_summary.md"         # Path to the prompt file (write your prompt in the file)
channel_id = "123456789012345678"            # Discord Channel ID to send the notification
mention_user_id = "123456789012345678"       # Do you want to be notified? If yes, put user's digital user id
```

# Restart
After the config file change, send the following for user to confirm:
- the `cronjob` section to user
- the job markdown
Then ask if the user wants to modify anything. If not, ask the user to use `/restart` to restart the server.