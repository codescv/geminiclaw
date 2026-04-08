Rules for agent - This file contains rules you need to follow while doing your job.

# Using the Command Line Tools
- When writing / editing files, prefer using "write_file" and "replace" tools over shell commands.
- Be 100% transparent: when you got denied by policy, **print the full command** you were trying to run to notify the user.
- Every python tool should be run with `uv run --default-index https://pypi.org/simple`, never `python` or `python3` or `pip`
- Use `env` command to set environment variables. Don't do this "VAR=value command" or "export X=y". They are denied by policy.
- Don't delete files using `rm`. Instead, **move** them to `~/.Trash`.
- When using shell redirection, redirect to a temp file and then use `read_file`, `write_file` or `replace` tools. This can help you avoid policy denials.
	- Do: `command1 | command2 | command3 > /tmp/temp_file.txt` then `write_file(target_file, content=read_file("/tmp/temp_file.txt"))`. 
	- Don't: `command1 | command2 | command3 > target_file`.

# Background Processes
For long running processes(>30min), you can run a command in the background:
- set the `is_background` parameter to true.
- **YOU MUST** use the command `nohup <command> & > <log_file>` to run it detached. Otherwise the process will just be killed when you reply to the user.
- Before replying to the user, you must write memory about the task in `memory/Background Tasks.md`.(Read the file for detailed instructions.)

# Files Management
**IMPORTANT**: If you need to write any temporary scripts, save outputs, clone repos, download files etc, **ALWAYS CREATE** a **new project** with a readable name and put all files in `temp/project_name`. This is your only **project directory**.
If you need to download third party tools or open source repos, install them in your **project directory**. Don't install it globally.

# Skills
For skill related scripts, put them in the `scripts` folder inside the `skill`.
For example: `gemini/skills/my-skill/scripts/my_helper_script.py`.
Please use self contained, one-file scripts for a skill with **Inline Script Metadata** to declare dependencies to keep the skills directory clean.

# Development
## Python
- Use `uv` to manage dependencies and virtual environments. NEVER run `python` directly.
- For `uv` to resolve dependencies, it's important to run `uv` with `--default-index https://pypi.org/simple`.
- For one-file scripts, use **Inline Script Metadata** defined by [PEP 723](https://peps.python.org/pep-0723/) to manage dependencies.
## NodeJS
- Use `npm` to manage dependencies for complex projects.
- Use `npx --package=axios --package=cheerio node script.js` to run one-file scripts with dependencies (add that in the comment of the script if you create scripts).

