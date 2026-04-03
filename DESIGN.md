# Gemini Claw - Agent based on Gemini CLI

Gemini CLI is already a full-featured agent - it can do almost anything.
The only major piece missing is communication channels that allow it to be controlled by the user remotely (e.g., via Discord).

## Architecture

Message flow:
```text
Inbound Channels (e.g. Discord) -> SQLite Database -> Polling loop (Python async task) -> Gemini CLI Subprocess -> Outbound Response
```

### Components

**1. Channels (Discord Bot)**
- **Inbound:** Listens for mentions, whitelisted users (if not in a thread and no explicit mentions), or specific commands in a Discord channel using `discord.py`. Parses the user's message and inserts it into an SQLite database with a status of `pending`.
- **Outbound:** An asynchronous task running alongside the bot continuously polls the SQLite database for messages marked as `completed` or `failed`. Once found, it sends the stored response back to the corresponding Discord channel and updates the record to `delivered`.

**2. Database Layer**
- SQLite is used as a decoupling layer to ensure message durability if the execution takes a long time or the bot crashes.
- **Table `messages`:**
  - `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
  - `channel_id` (TEXT)
  - `message_id` (TEXT)
  - `prompt` (TEXT)
  - `status` (TEXT) - `pending`, `processing`, `completed`, `failed`, `delivered`
  - `response` (TEXT)
  - `created_at` (TIMESTAMP)

**3. Polling Loop & Subprocess Execution**
- A Python `asyncio` loop running concurrently with the Discord bot.
- It polls the database for `pending` messages (filtering out channels that are already busy) and marks them as `processing`.
- It processes messages concurrently by spawning background `asyncio` tasks, ensuring that messages from the same thread are still processed serially.
- It executes the Gemini CLI using a headless Python subprocess.
  - **Command Execution:** To avoid the complexities of forwarding PTY interactions over Discord, we will use Gemini CLI's headless mode (`-p`) combined with YOLO mode (`-y` or `--yolo`) to automatically accept tools. Any `policy` files defined in the `[gemini]` section of `config.toml` will be appended automatically as `--policy <file>` arguments.
  - **Execution Command:** `gemini -y -p "<prompt>"` (we can potentially add `-r latest` to resume state, or manage sessions manually per user/channel).
- Standard output and standard error are captured. Once the process completes, the output is saved to the `response` field, and the status is updated to `completed` (or `failed` if the exit code is non-zero).

**4. Setup and Configuration Commands**
- To guide the user during the initial bootstrap, we provide a CLI interface:
  - `uv run geminiclaw init`: Run when the user first clones the repository. It creates a `config.toml` file from the example, and initializes the SQLite database schema.
  - The CLI handles both starting the bot (`uv run geminiclaw start`) and managing the background service for macOS and Linux (`uv run geminiclaw service`).
- These commands act as entry points that spawn the respective Python utility functions in `src/geminiclaw/cli.py` to keep the heavy lifting in Python.
 
**5. Attachments Handling**
- **Inbound (Download)**: Any file attached to a message mentioning the bot is downloaded to a configurable directory (e.g., inside the workspace).
- **Prompt Enrichment**: The bot appends an `Attachments:` list to the prompt, referencing the downloaded files (e.g., `- attachments/message_id_filename.ext`). This informs the agent about availability.
- **Agent Access**: Since files are in the workspace or included via `--include-directories`, the Gemini CLI agent can access them using its tools (like reading files).
- **Outbound (Transmission)**: The agent can send files back to the user by including the syntax `[attachment: path/to/file]` in its response. The bot extracts these paths from the final response, verifies the files exist within the workspace, and securely uploads them as Discord attachments in a subsequent message.
 
**6. Cronjobs Management**
- **Triggering**: Periodically triggers based on `cron` schedule expressions using `apscheduler`. It also supports an optional `probability` parameter to randomly skip executions based on a given float chance.
- **Flow**: Reads a prompt file and inserts a **pending message** into the SQLite database with the thread's ID (or creates a thread) and sets the `author_id` to the bot's own ID. If the cronjob has `silent` set to true, it will insert a silent message and skip thread creation.
- **Processing**: The standard async polling loop automatically picks this up, executes it with the Gemini agent, and delivers the response into the thread just like a normal user prompt. For silent messages, execution happens in the background without any Discord interaction. This decouples scheduling from execution logic.
 
## Process Management
- **Single Process:** The Discord Bot (`discord.py` client loop) and the database polling mechanism will run within the same Python process using `asyncio` tasks. This avoids the overhead and complexity of managing multiple background services, while still keeping the architecture decoupled via the SQLite layer.
- **Process Killing:** The bot tracks running `gemini` subprocesses in a dictionary. When a `-kill` command is received in a channel, it terminates the process for that specific channel (or thread) manually.
- **Process Restarting:** When a `-restart` command is received, the bot spawns a background shell command `geminiclaw service restart` to restart the bot service itself. Use with caution as it will disconnect the bot temporarily.
