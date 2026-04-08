# Format
For each error, log the following:

```markdown
- Time: {local timestamp}
- Tool: The tool used. e.g. `run_shell_command`
- Args: The args for the tool. e.g. `{"command": "cat temp/errors.json | jq '.[].time' | sort | uniq -c"}`
- Error: The error message. e.g. `Tool execution denied by policy.`
```