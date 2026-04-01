# Role Playing with Custom Prompts and Discord Topics

GeminiClaw is highly flexible and can be instructed to adopt specific personas or follow distinct role-playing scenarios. There are two primary ways to set up role-playing: globally using custom prompt files, or per-channel using Discord topics.

## Method 1: Using Custom Prompts (Global)

If you want your bot to have a consistent persona across all interactions, you can use custom markdown files for the system prompt. The [GeminiClawDock](https://github.com/codescv/GeminiClawDock) template provides an excellent structure for this.

1. **Create Persona Files**: In your workspace, create files like `notes/Settings/Soul.md` or `notes/Settings/User.md`. In these files, define the bot's identity, its goals, the rules it should follow, and your customized background.
2. **Configure `config.toml`**: Inject these files into the bot's base system prompt by referencing them in your `config.toml` under the `[prompt]` section:

```toml
[prompt]
user = [
    "notes/Settings/Rules.md",
    "notes/Settings/Soul.md",
    "notes/Settings/User.md"
]
```

Every time the bot responds, it will read these files and adopt the persona defined within them.

## Method 2: Using Discord Channel Topics (Per-Channel)

If you want different channels to have different role-play scenarios (e.g., a "pirate-tavern" channel and a "sci-fi-bridge" channel) without running multiple bot instances, you can use Discord channel topics.

1. **Edit Channel Topic**: Right-click a text channel in Discord, select **Edit Channel**, and write your prompt instructions in the **Channel Topic** field. For example: `You are a helpful and enthusiastic pirate. Respond to all queries with nautical slang.`
2. **Interact**: Whenever a user talks to the bot in that channel (or in a thread created within that channel), GeminiClaw will automatically read the channel topic and inject it into the prompt.

The bot sees this as:
```text
---BEGIN TOPIC INSTRUCTIONS---
You are a helpful and enthusiastic pirate. Respond to all queries with nautical slang.
---END TOPIC INSTRUCTIONS---
```

This makes it incredibly easy to create dynamic, context-specific role-playing environments on your server on the fly!
