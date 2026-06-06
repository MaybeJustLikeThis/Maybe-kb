# Fix: MCP kb 连接失败修复

## 问题

`kb.exe` 被其他进程占用时，`pip install -e .` 无法覆盖，导致 `kb` 模块损坏。
MCP server 启动时 `import kb` 失败（`ModuleNotFoundError: No module named 'kb'`）。

## 根因

1. 早期 `pip install -e .` 失败 — `kb.exe` 被 MCP 进程锁定（`OSError: [WinError 32]`）
2. 安装回滚不完整 — `kb.exe` 保留旧版，但模块文件丢失
3. `mcp.json` 配置 `"command": "kb"` 指向损坏的 `kb.exe`

## 修复方案：重装 kb 包

### 步骤

1. **终止占用进程** — `taskkill /F /IM kb.exe` 杀掉所有 kb 进程
2. **重装** — `pip install -e C:/Users/cherry/Desktop/kb`
3. **验证 CLI** — `kb --help` 正常输出
4. **验证 MCP** — `kb mcp` 不报错，工具列表完整

### 验证标准

- `kb --help` 输出帮助信息
- `kb mcp` 启动不报 ModuleNotFoundError
- Claude Code CLI 和 VS Code 插件中 kb MCP 工具可用（kb_search、kb_list 等）

## 影响范围

- `~/.claude/mcp.json` — 无需修改
- `C:/Users/cherry/Desktop/kb` — 无代码变更，仅重装包

## 风险

低。仅修复包安装状态，不涉及代码改动。
