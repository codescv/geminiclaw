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
- **Inbound:** Listens for mentions or specific commands in a Discord channel using `discord.py`. Parses the user's message and inserts it into an SQLite database with a status of `pending`.
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
- It polls the database for `pending` messages and marks them as `processing`.
- It executes the Gemini CLI using a headless Python subprocess.
  - **Command Execution:** To avoid the complexities of forwarding PTY interactions over Discord, we will use Gemini CLI's headless mode (`-p`) combined with YOLO mode (`-y` or `--yolo`) to automatically accept tools.
  - **Execution Command:** `gemini -y -p "<prompt>"` (we can potentially add `-r latest` to resume state, or manage sessions manually per user/channel).
- Standard output and standard error are captured. Once the process completes, the output is saved to the `response` field, and the status is updated to `completed` (or `failed` if the exit code is non-zero).

**4. Setup and Configuration Commands**
- To guide the user during the initial bootstrap, we will write a tiny NodeJS Gemini CLI extension.
- This extension provides native Gemini CLI commands:
  - `/claw setup`: Run when the user first clones the repository. It creates a `.env` file, prompts the user for their Discord bot token, initializes the SQLite database schema, and ensures Python dependencies are installed via `uv`.
  - `/claw configure`: Used to update existing configurations later.
- These commands act as entry points that spawn the respective Python utility scripts (`src/setup.py` and `src/configure.py`) to keep the heavy lifting in Python.

## Process Management
- **Single Process:** The Discord Bot (`discord.py` client loop) and the database polling mechanism will run within the same Python process using `asyncio` tasks. This avoids the overhead and complexity of managing multiple background services, while still keeping the architecture decoupled via the SQLite layer.
