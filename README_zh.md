简体中文 | [English](./README.md)

# AI Gateway

一个基于 FastAPI 开发的高性能异步 AI 大模型聚合网关。支持 Server-Sent Events (SSE) 流式零延迟转发、动态多渠道路由及非阻塞式异步审计日志落库。

## 特性

- **异步流式代理**：基于 `httpx.AsyncClient` 的异步生成器实现，支持 SSE 流式响应的无缝透传，首字延迟（TTFT）接近原生 API。
- **多渠道动态路由**：统一对外的 OpenAI 标准接口，根据 `model` 参数自动分发至 DeepSeek、Gemini 或 Qwen 远端端点，具备基础的异常隔离（Fallback）能力。
- **非阻塞审计日志**：基于 `aiosqlite` 实现请求元数据、响应状态及 Token 消耗量的异步落库，确保监控统计不阻塞主业务逻辑流程。
- **协议兼容**：完全兼容 OpenAI 的 `/v1/chat/completions` 标准协议，支持 stream 与 non-stream 双模式。

## 快速启动

### 1. 环境准备

确保本地已安装 Python 3.10+ 环境。

```bash
# 克隆并进入项目
cd ai-gateway

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量与启动

网关通过环境变量读取各渠道凭证。在终端中注入鉴权密钥并使用 uvicorn 启动服务：

```bash
# 注入需要的 API Key（根据实际使用的渠道配置）
export DEEPSEEK_API_KEY="your_deepseek_key"
export GEMINI_API_KEY="your_gemini_key"
export QWEN_API_KEY="your_qwen_key"

# 启动服务
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### API 使用示例

服务启动后，网关地址为 `http://127.0.0.1:8000`。可以使用任何兼容 OpenAI SDK 的客户端或通过 curl 直接调用：

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": true
  }'
```

### 项目结构

```
├── main.py          # 网关核心逻辑（包含路由分发、流式转发与 lifespan 数据库初始化）
├── requirements.txt # 项目核心依赖
└── .gitignore       # 忽略配置文件（已排除 .venv/ 虚拟环境与本地 sqlite 数据库）
```
