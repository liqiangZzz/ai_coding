# 快速上手

本文档帮助你从零开始，在本地启动 LQ-AICODING 后端和前端，并通过两种方式提交任务。

> 本文件只覆盖快速启动和基本使用场景。项目架构、核心能力、配置说明等内容请阅读 [README.md](./README.md)。

## 前置条件

- **Python 3.11+**（项目依赖 `pyproject.toml` 中声明 `requires-python = ">=3.11"`）
- **Node.js 18+**（前端基于 Vite 7 + Vue 3）
- **Git**（用于克隆和管理 GitHub 仓库）

### 配置环境变量

在项目根目录创建 `.env` 文件（可参考 `.env.example`），至少配置以下变量：

```text
DEEPSEEK_API_KEY=你的DeepSeek API Key
GITHUB_TOKEN=你的GitHub个人访问令牌
MAIN_MODEL=deepseek-v4-pro
```

> 更多配置项（智谱搜索 API、多平台路径、日志等）请参考 `.env.example` 中的完整注释。

## 1. 本地启动后端

### 1.1 安装依赖

```bash
# 在项目根目录执行
pip install -e .
```

这会根据 `pyproject.toml` 安装所有运行时依赖（FastAPI、LangGraph、DeepAgents、Uvicorn 等）。

### 1.2 启动服务

```bash
uvicorn agent.app:app --host 127.0.0.1 --port 2024
```

- 服务启动后访问 `http://127.0.0.1:2024`。
- 健康检查：`http://127.0.0.1:2024/health` 返回服务状态与关键配置信息。
- `agent/app.py` 是 FastAPI 应用的唯一入口，启动时会自动加载 `.env` 并初始化日志系统。

## 2. 本地启动前端

### 2.1 安装依赖

```bash
cd ui
npm install
```

### 2.2 启动开发服务器

```bash
npm run dev
```

- 前端默认运行在 `http://127.0.0.1:3000`。
- Vite 开发服务器会将 `/dashboard/api` 请求自动代理到后端 `http://127.0.0.1:2024`（代理配置见 `ui/vite.config.js`）。
- 如后端运行在其他端口，可通过环境变量 `VITE_DASHBOARD_API_BASE_URL` 指定代理目标。

### 2.3 一键启动（可选）

项目提供了 `scripts/start_all.py` 脚本，可同时启动后端（端口 2024）和前端（端口 3000）：

```bash
python scripts/start_all.py
```

按 `Ctrl+C` 即可同时停止两个服务。

## 3. 提交任务

### 3.1 通过 Dashboard 对话

1. 打开浏览器访问 `http://127.0.0.1:3000`。
2. 在左侧会话列表点击「新建会话」。
3. 输入 GitHub 仓库地址（支持 `owner/repo` 简写或完整 URL）和你的任务描述。
4. 发送消息后，后端会实时返回 Agent 的执行过程（通过 SSE 流式传输）。
5. 你可以在页面中看到 Agent 的工具调用步骤、中间输出和最终回答。

### 3.2 通过 API 调用

如果你需要在脚本或其他系统中调用，可以直接请求后端 API：

```bash
curl -X POST http://127.0.0.1:2024/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/owner/repo.git",
    "prompt": "你的任务描述"
  }'
```

请求体字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `repo_url` | string | 是 | GitHub 仓库地址（完整 URL 或 `owner/repo`） |
| `prompt` | string | 是 | 用户任务描述 |
| `thread_id` | string | 否 | 可选的会话线程 ID，用于多轮对话 |

响应示例：

```json
{
  "thread_id": "abc123...",
  "status": "completed",
  "result": "..."
}
```

> 接口定义见 `agent/api/routes.py` 中的 `TaskCreateRequest` 模型。

## 4. 编码任务流程

LQ-AICODING 对编码类任务（如新增功能、修改代码、修复缺陷）有固定的安全流程：

```text
用户提交任务
  → Agent 识别为 coding 类型
  → 生成技术方案（只读，不修改任何文件）
  → 用户确认方案（回复"确认实施"或类似确认语）
  → Agent 进入 coding 模式：修改代码、运行验证
  → 提交分支并推送到 GitHub
  → 创建 Pull Request
```

关键说明：

- **方案阶段**：Agent 只分析仓库、阅读代码，输出中文技术方案。不会修改任何文件，也不会提交或推送。
- **确认机制**：用户必须明确确认方案后，Agent 才会进入实施阶段。如果对方案不满意，可以要求修改方案。
- **实施阶段**：Agent 按确认的方案修改代码、运行验证（如果项目有测试），然后自动创建分支、提交并推送。
- **PR 创建**：完成推送后，Agent 自动创建 Pull Request。如果相同源分支和目标分支已存在 PR，会自动复用。
- **非 coding 任务**（分析、问答、审查等）全程只读，不会触发代码修改和 PR 创建。

这一流程由 `agent/core/runtime.py` 中的任务状态机控制，确保编码操作始终在用户明确授权后进行。

## 常见问题

### 启动后端时报 `ModuleNotFoundError: No module named 'agent'`

请确认已执行 `pip install -e .`，该命令会将当前项目以可编辑模式安装到 Python 环境中。

### 前端页面打开后无法连接后端

检查后端是否已启动在 `127.0.0.1:2024`。如果后端在其他端口，启动前端时设置环境变量：

```bash
VITE_DASHBOARD_API_BASE_URL=http://127.0.0.1:自定义端口 npm run dev
```

### 任务执行时报 GitHub 相关错误

请确认 `.env` 中的 `GITHUB_TOKEN` 已正确配置，且令牌具有仓库读写权限。`/health` 接口可查看 `has_github_token` 状态。

### Windows 用户注意事项

- 路径配置统一使用正斜杠 `/`，避免反斜杠转义问题。
- 虚拟环境 Python 路径为 `.venv\Scripts\python.exe`（macOS/Linux 为 `.venv/bin/python`）。
- 项目 `.gitattributes` 已配置统一换行符，跨平台协作不会产生整文件差异。