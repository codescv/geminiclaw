> [English](security.md) | [中文](security_zh.md)

# Gemini Claw 安全配置与机制继承

Gemini Claw 全面继承了 Gemini CLI 完善的安全架构，这允许你在自己的环境中安全地运行智能体命令。所有核心安全默认配置均在 `config.toml` 文件中的 `[gemini]` 配置段下管理。

---

## 1. 沙盒执行环境保护 (`sandbox = true`)

沙盒可在操作系统层级严格限制智能体的执行能力，防止其未授权访问或修改你工作区之外的系统文件。

- **运行机制：** 开启 `sandbox = true` 会设置环境变量 `SEATBELT_PROFILE='geminiclaw'` 并为所有 Gemini CLI 的子进程追加参数 `--sandbox`。
- **Seatbelt 安全限制与密钥保护：** `.gemini/sandbox-macos-geminiclaw.sb` 沙盒文件明确拒绝读取如主目录下的 `.zsh_history`、`.bash_history` 及 `LaunchAgents` 等敏感文件，因为诸如 API 密钥等私密凭证极易在 shell 历史记录中泄露。不仅如此，除特定的临时缓存目录外，所有的任意写入操作也会被自动拦截。最关键的是，对外网络请求被完全限制在 Gemini API 节点及官方包服务器下，这从根本上保证了无论执行何种恶意脚本或提示词，你的密钥都无法被外部第三方服务窃取。
- **定制化：** 高级用户可以通过向工作区内的 `.gemini/sandbox-macos-geminiclaw.sb` 增加自定义放行规则来适配特定的工作流。
- **最佳实践建议：** 强烈建议始终保持开启 `sandbox = true` 以获取最高级别的安全保障。

---

## 2. YOLO 免打扰模式 (`yolo = true`)

YOLO 模式允许智能体在终端中自动运行命令及工具权限，而不再强制要求对每步操作都提示用户进行手动按键确认。

- **运行机制：** 开启 `yolo = true` 会向智能体执行命令追加参数 `-y`。

---

## 3. 工具策略 (`policy = [...]`)

安全策略为智能体提供了细粒度的、白名单机制的工具权限支持，严格约束智能体究竟能够调用哪些命令和访问哪些文件。

- **示例：**
  ```toml
  [gemini]
  policy = [".gemini/policy/tools.toml"]
  ```

---

## 4. 安全部署：环境变量与独立后台服务

为了彻底确保像 `DISCORD_TOKEN` 与 `GOOGLE_API_KEY` 等敏感凭证绝不会被智能体脚本访问或窃取，请遵循以下安全部署架构建议：

1. **环境变量：** 替代在 `config.toml` 中直接硬编码明文密钥，请在 shell 启动配置或系统服务管理器中以安全环境变量的形式导出它们：
   ```bash
   export DISCORD_TOKEN="YOUR_DISCORD_BOT_TOKEN"
   export GOOGLE_API_KEY="YOUR_GOOGLE_API_KEY"
   ```
2. **作为后台独立服务安装：** 在以服务形式运行时，将环境变量直接集成到 launch plist 文件或 systemd 服务定义中，然后安装并启动该后台守护进程：
   ```bash
   geminiclaw service install
   geminiclaw service start
   ```
3. **安全隔离保证：** 通过系统层级注入密钥并强制叠加 `sandbox = true` 机制，沙盒协议会完全切断任何针对配置工件和 shell 历史日志的读取权限。智能体执行完全被隔离在一个密封空间中，从而彻底消除了未授权读取或泄密的隐患。
