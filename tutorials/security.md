> [English](security.md) | [中文](security_zh.md)

# Security Configuration in Gemini Claw

Gemini Claw inherits the robust security architecture of the Gemini CLI, allowing you to safely execute agent commands within your environment. All security defaults are managed under the `[gemini]` section of your `config.toml` file.

---

## 1. Sandboxing (`sandbox = true`)

Sandboxing restricts the agent's execution capabilities at the operating system level to prevent unauthorized access or modifications outside your workspace.

- **How it works:** Enabling `sandbox = true` sets the `SEATBELT_PROFILE='geminiclaw'` environment variable and appends the `--sandbox` argument to all Gemini CLI subprocesses.
- **Seatbelt Restrictions & API Key Protection:** The `.gemini/sandbox-macos-geminiclaw.sb` sandbox profile explicitly denies read access to sensitive files such as `.zsh_history`, `.bash_history`, and `LaunchAgents` in your home directory, where API keys and other private secrets may be accidentally exposed or logged by shell history. Furthermore, all file writes are blocked by default except to specific allowlisted temporary or cache directories. Crucially, outbound network requests are restricted to Gemini API endpoints and official package indexes. This guarantees that your API keys and local secrets cannot be exfiltrated or stolen by malicious prompts or executing scripts directing data to third-party servers.
- **Customization:** Advanced users can customize the `.gemini/sandbox-macos-geminiclaw.sb` file in the workspace by adding specific allow rules or subpath exclusions as needed for their workflows.
- **Recommendation:** Always run with `sandbox = true` for maximum security.

---

## 2. YOLO Mode (`yolo = true`)

YOLO mode allows the agent to run commands and use tools automatically without prompting for manual user confirmation in the terminal.

- **How it works:** Enabling `yolo = true` adds the `-y` flag to the agent's execution command.
- **Recommendation:** For a seamless Discord bot experience, set `yolo = true` alongside sandboxing. If you cannot use a sandbox, you can disable YOLO mode and manage specific tool permissions using policies instead.

---

## 3. Policies (`policy = [...]`)

Security policies define granular, allow-listed tool permissions for the agent, restricting exactly what commands or files it can interact with.

- **How it works:** Add `.toml` policy files to the `policy` list in `config.toml`. Each path is injected as a `--policy <file>` argument during execution.
- **Example:**
  ```toml
  [gemini]
  policy = [".gemini/policy/tools.toml"]
  ```

---

## 4. Secure Deployment: Environment Variables & Background Service

To guarantee that your sensitive credentials (such as your `DISCORD_TOKEN` and `GOOGLE_API_KEY`) are never accessed by executing agent scripts, follow these secure deployment practices:

1. **Environment Variables:** Instead of hardcoding keys into `config.toml`, export them securely as environment variables in your shell or system service manager:
   ```bash
   export DISCORD_TOKEN="YOUR_DISCORD_BOT_TOKEN"
   export GOOGLE_API_KEY="YOUR_GOOGLE_API_KEY"
   ```
2. **Installing as a Background Service:** Integrate the environment keys directly into the launch plist or systemd file when running as a service, then install and run the background daemon:
   ```bash
   geminiclaw service install
   geminiclaw service start
   ```
3. **The Security Guarantee:** By injecting keys via the system environment and enforcing `sandbox = true`, the seatbelt profile completely denies any read access to configuration artifacts or shell histories where keys might otherwise be stored. Execution is entirely isolated, safeguarding your secrets against unauthorized reads or leaks.
