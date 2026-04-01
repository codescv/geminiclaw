# Memory Management using GeminiClawDock

By default, an LLM agent starts fresh with every new conversation and forgets things over time. However, [GeminiClawDock](https://github.com/codescv/GeminiClawDock) implements an automated memory management system using an [Obsidian Vault](https://obsidian.md/) structure to give your bot persistent, long-term memory.

## Inside the `notes/` Vault

The workspace template contains a `notes/` directory, which acts as the bot's central brain. It is divided into distinct sections:

### 1. Long-Term Memory (`notes/Memory.md`)
This file is the bot's permanent storage. It contains core facts, learned user preferences, and critical information that should persist indefinitely. The bot will automatically read this file to gain context about who you are and what it has learned in the past.

### 2. Short-Term Memory (`notes/Daily/`)
This directory acts as a daily log or scratchpad. During conversations, the bot can write temporary notes, summarize recent events, or log tasks it is currently working on. It's a great place to store context that is important right now but might not be needed a year from now.

### 3. Rules and Persona (`notes/Settings/`)
As mentioned in the role-playing tutorial, this folder contains `Rules.md`, `Soul.md`, and `User.md`. These files form the bot's behavioral foundation.

## How the Agent Uses Memory

Because the Gemini CLI has full access to the workspace directory, the agent can use its built-in tool capabilities to actively read and write to these files:

- **Recalling Info**: When asked about a past event, the bot can read `notes/Memory.md` to find the answer.
- **Saving Info**: If you tell the bot an important fact ("Remember that my favorite language is Python"), the bot can write that fact to `notes/Daily/` or directly to `notes/Memory.md`.

You can open the `notes/` folder in Obsidian (or any Markdown editor) to visually inspect, edit, or reorganize the bot's memories at any time. If you want the bot to instantly know a new fact, simply type it into `Memory.md` yourself!
