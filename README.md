> [English](README.md) | [中文](README_zh.md)

# Gemini Claw

Gemini Claw is a Discord bot powered by the [Gemini CLI](https://github.com/google/gemini-cli). It acts as a bridge, allowing you to interact with the Gemini CLI agent directly from your Discord server.

# Why Gemini Claw?

The Gemini CLI is already an incredibly capable, full-featured AI agent. However, it is primarily designed for local terminal use and lacks remote communication channels. Gemini Claw solves this by providing a seamless bridge to Discord. 

Instead of building a new agent from scratch, Gemini Claw leverages the power of the existing ecosystem:
- **Built-in Security:** Inherits the Gemini CLI's robust security policy support, ensuring safe execution of commands.
- **Simplicity:** A small, easy-to-understand Python codebase that acts merely as a decoupling layer.
- **Extensibility:** Adds new capabilities through native Gemini CLI extensions rather than reinventing the wheel.

# Features

- **Threaded Interactions**: Supports threaded interactions with Gemini CLI agents.
- **Memory Management**: Supports memory management for tracking progresses, learning about user preferences etc.
- **Security**: Well integrated with Gemini CLI's sandbox and security policy support, preventing leaks of secrets such as API keys.
- **Channel topic as system prompt**: Supports channel topic injected to system prompt to provide channel based customizations.
- **Cronjobs**: Supports cronjobs that read a prompt file, execute it using Gemini CLI, and send the output to a specific Discord channel in a new thread.
- **Role Playing**: Supports **multiple** role playing for different channels.
- **Long Running Tasks**: Supports long running tasks that can be run in background, and heartbeat to check status and report.
- **Multi-Bot Chat**: Supports multiple Gemini CLI agents chatting with each other in a Discord channel.
- **Attachments**: Supports two way videos, images, voice messages and file attachments.


# Screenshots

<div align="center">
  <img src="images/ss1.PNG" alt="Screenshot 1" width="30%">
  <img src="images/ss2.PNG" alt="Screenshot 2" width="30%">
  <img src="images/ss3.PNG" alt="Screenshot 3" width="30%">
</div>

## Threaded Interations
<img src="images/threads.png">

## Multi bots chat
<img src="images/debate_1.png">
<img src="images/debate_2.png">


# Prerequisites

## Dependencies
- **Python:** Ensure you have [Python](https://www.python.org/downloads/) installed.
- **uv:** This project uses `uv` for dependency management. Install it via `curl -LsSf https://astral.sh/uv/install.sh | sh`.
- **Gemini CLI:** Ensure you have the Gemini CLI installed and authenticated.

## Discord Bot Configuration
Before running the setup, you need to create a bot on Discord:
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click **New Application** and give it a name.
3. On the left sidebar, click on **Bot**.
4. **Make it Private:** First, go to **App Settings** -> **Installation** and set the **Install Link** to **None**. Once that is set, go back to the **Bot** tab and uncheck the **Public Bot** toggle so only you can add it to servers.
5. Click **Reset Token** and copy your new `DISCORD_TOKEN`.
6. **CRITICAL:** Scroll down to the **Privileged Gateway Intents** section and turn **Message Content Intent** to **ON**.
7. On the left sidebar, click on **OAuth2** -> **OAuth2 URL Generator**.
8. Under **Scopes**, check the **bot** checkbox.
9. Under **Bot Permissions**, check **Send Messages**, **Read Message History**, and **View Channels**.
10. At the bottom of the page, **Copy the generated URL**.
11. Paste that URL into a new browser tab, select your server, and click **Authorize** to invite the bot.


# Installation

You can install and run `geminiclaw` directly using `uv tool` without cloning the source code:

```bash
uv tool install git+https://github.com/codescv/geminiclaw.git
```

# Initialize the Bot
Once installed, run the following command to initialize the setup:
```bash
geminiclaw init
```
This will copy all files from the bundled workspace to the current directory and initialize the SQLite database, and then print instructions for recommended configurations.

*Note: Set `HTTP_PROXY` and `HTTPS_PROXY` in your shell environment if you need one for connecting Gemini CLI and Discord API server.*

# Running as a Service

The `geminiclaw` CLI provides commands to manage the background service for macOS / Linux.

- **Install the Service:** `geminiclaw service install` (Installs the background service)
- **Start the Service:** `geminiclaw service start` (Starts the background service)
- **Stop the Service:** `geminiclaw service stop` (Stops the background service)
- **Restart the Service:** `geminiclaw service restart` (Restarts the background service)
- **Check Status:** `geminiclaw service status` (Checks the status of the service)

# Using the Bot
Once started, simply mention the bot in your Discord server followed by your prompt, or send it a Direct Message.

```text
@GeminiClaw write a python script to reverse a string
```

 
# Configuration
Every configurable option is stored in `config.toml` file. Read the comments
for instructions.

## Always Reply (Whitelist)

You can configure the bot to always reply to specific whitelisted users without requiring them to explicitly mention the bot in every message. This takes effect only if the message is not within a thread and there are no explicit mentions.

Add the `always_reply` list to your `config.toml` file under the `[discord]` section:

```toml
[discord]
always_reply = ["user1", "user2"]
```

## Prompt Customization

You can customize the base prompts used by the Gemini CLI agent by modifying the markdown files in the `prompts` directory. These files are injected to the system prompt when calling the Gemini CLI.

```toml
[prompt]
user = ["user.md", ...]
```

## Cronjobs

You can configure periodic tasks (cronjobs) that read a prompt file, execute it using Gemini, and send the output to a specific Discord channel in a new thread.

### Configuration

Add `[[cronjob]]` sections to your `config.toml` (or `private/config.toml`):

```toml
[[cronjob]]
schedule = "*/5 * * * *"                     # Cron schedule expression
prompt = "cronjobs/daily_summary.md"         # Path to the prompt file
channel_id = "123456789012345678"            # Discord Channel ID (find in https://discord.com/channels/server_id/channel_id)
mention_user_id = "123456789012345678"       # Optional: Your User ID to join the thread automatically
silent = false                               # Optional: Set to true to run the job silently without sending Discord messages
probability = 1.0                            # Optional: Probability of execution (0.0 to 1.0)
```

# 📖 Tip: How to find your Discord User ID & Channel ID

Some settings needs your discord channel id or user id. Here is how to find them:

1. **Enable Developer Mode**:
   - Go to Discord **User Settings** -> **Advanced**.
   - Toggle **Developer Mode** to **ON**.

2. **Copy Your User ID**:
   - Right-click your **avatar/name** in any member list or chat.
   - Click **Copy User ID** at the bottom of the menu.

3. **Copy Channel ID**:
   - Right-click your **channel name** in the channel list.
   - Click **Copy Channel ID** at the bottom of the menu.

# Tutorials

For more advanced usage, check out our dedicated tutorials:

- [Role Playing](tutorials/role_playing.md)
- [Memory Management](tutorials/memory_management.md)
- [Background Tasks](tutorials/background_tasks.md)
- [Security](tutorials/security.md)
