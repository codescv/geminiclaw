# Memory Management in Gemini Claw

Gemini Claw uses a transparent, file-backed memory system stored directly in your local workspace. This ensures that all task progress, user preferences, learnings, and error logs persist reliably across bot restarts and long-running conversations.

---

## Core Memory Architecture

Memory is structured as standard markdown files under the `memory/` directory of your workspace. The agent interacts with these files guided by internal rules and scheduled cronjobs.

### Key Memory Files

1. **`memory/Progress.md`**
   - **Purpose:** Tracks the ongoing status and next steps for active projects, reading sessions, and complex, multi-phase tasks.
   - **Format:**
     ```markdown
     # {Project Name}
     - {local timestamp}: {A short sentence describing progress and next steps}
     ```
   - **Interaction:** The agent reads this when resuming past tasks or continuing a project, and writes to it proactively when the user initiates tracking.

2. **`memory/Learnings.md`**
   - **Purpose:** Acts as long-term knowledge retention, storing lessons learned, significant user preferences, and important events.
   - **Format:**
     ```markdown
     - {local timestamp}: {A short sentence describing the learning}
     ```
   - **Interaction:** Injected automatically into the agent's system prompt via `config.toml`. The agent writes here whenever instructed to remember critical user instructions or insights.

3. **`memory/Errors.md`**
   - **Purpose:** Collects logs of failed tasks or unexpected script behaviors.
   - **Interaction:** Maintained primarily via automated daily consolidation cronjobs.

---

## Automation via Cronjobs

Gemini Claw automates memory maintenance and cleanup so the agent doesn't have to manually parse every log file during live chat.

- **Memory Updates Cronjob:** Governed by `cronjobs/Memory Updates.md` and scheduled in `config.toml`.
- **Workflow:** Once daily (e.g., at 3:00 AM), the background cronjob triggers silently. It scans `.gemini/tmp` for log files modified in the last 24 hours, filters the contents for new developments or errors, and summarizes them natively into `memory/Progress.md` or `memory/Errors.md`.

---

## Best Practices

- **Persistence First:** Ensure your workspace `memory/` folder is initialized properly (done automatically upon running `geminiclaw init`).
- **Custom Memory Rules:** If you wish to track domain-specific rules or instructions, you can add custom markdown instruction files to the `[prompt]` section of `config.toml`.
