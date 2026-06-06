# Fix MCP kb 连接失败 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 `kb` 包安装状态，使 MCP server 和 CLI 恢复正常工作。

**Architecture:** 纯运维修复 — 终止占用进程后重装 Python 包，验证 CLI 和 MCP 连接。

**Tech Stack:** Python 3.13, pip, Windows

---

### Task 1: 终止占用进程并重装 kb 包

**Files:**
- 无代码文件变更

- [ ] **Step 1: 终止所有 kb.exe 进程**

```bash
taskkill.exe //F //IM kb.exe
```

Expected: `成功: 终止了 N 个进程` 或 `未找到进程`（如果没有运行的进程）

- [ ] **Step 2: 重装 kb 包（editable mode）**

```bash
/c/Users/cherry/AppData/Local/Programs/Python/Python313/python.exe -m pip install -e "C:/Users/cherry/Desktop/kb"
```

Expected: `Successfully installed kb-0.1.0`

- [ ] **Step 3: 验证 kb CLI 正常**

```bash
/c/Users/cherry/AppData/Local/Programs/Python/Python313/Scripts/kb.exe --help
```

Expected: 输出 CLI 帮助信息，无 `ModuleNotFoundError`

- [ ] **Step 4: 验证 kb mcp 启动正常**

```bash
/c/Users/cherry/AppData/Local/Programs/Python/Python313/Scripts/kb.exe mcp --help 2>&1 || echo "mcp server starts in stdio mode, no --help expected"
```

Expected: 不报 `ModuleNotFoundError`。MCP server 以 stdio 模式启动是正常的（无 --help 输出）。

- [ ] **Step 5: 验证 MCP 工具可用**

在 Claude Code 中确认 `kb_search`、`kb_list`、`kb_read` 等工具可用。用户需重启 Claude Code 会话使 MCP 重新连接。

---

## Self-Review

**Spec coverage:** 设计文档中所有 4 个验证标准（`kb --help`、`kb mcp`、CLI 工具可用、VS Code 工具可用）均有对应步骤覆盖。

**Placeholder scan:** 无 TBD、TODO 或模糊步骤。所有命令都是具体可执行的。

**Type consistency:** 不适用（无代码变更）。

**额外考虑:** Windows Store 版 `python` 有 exit code 49 问题，所有命令使用完整 Python 路径 `/c/Users/cherry/AppData/Local/Programs/Python/Python313/python.exe`。
