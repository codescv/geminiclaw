Rules for agent - This file contains rules you need to follow while doing your job.

# Using the Command Line Tools
- Don't delete files using `rm`. Instead, **move** them to `~/.Trash`.

# Background Processes
For long running processes(e.g. >30min), you MUST use the `background-task` skill to run it in background.

# Files Management
**IMPORTANT**: No new files in current directory (the Gemini CLI workspace).
If you need to write any scripts, save outputs, clone repos, download files, run commands with outputs etc, **ALWAYS CREATE** a **new project directory** `projects/project_name` with a readable name and put all files in it.

# Memory
- `memory/Progress.md`: the progress of the user's readings, projects, research etc.
  - When to Read: When you need to know the current progress (e.g. user asks to continue a project or a reading)
  - When to Write: When user asks to start tracking.
- `memory/Learnings.md`: significant events, thoughts, decisions, opinions, lessons learned.
  - When to Read: This is automatically injected to sys prompt. No need to read.
  - When to Write: When user asks you to remember something, this is the default place to do it.

# Skills
For skill related scripts, put them in the `scripts` folder inside the `skill`.

# Coding
## Python
- Use `uv` to manage dependencies and virtual environments. NEVER run `python` directly.
- Run `uv` with `--default-index https://pypi.org/simple` to make sure the packages are installed from the official PyPI index.
- For one-file scripts, use **Inline Script Metadata** defined by [PEP 723](https://peps.python.org/pep-0723/) to manage dependencies.
## NodeJS
- Use `npm` to manage dependencies for complex projects.
- Use `npx --package=axios --package=cheerio node script.js` to run one-file scripts with dependencies (add that in the comment of the script if you create scripts).

