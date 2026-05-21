[简体中文](./README_zh.md) | English

# AI Gateway

A high-performance, asynchronous AI model aggregation gateway built with FastAPI. It features Server-Sent Events (SSE) streaming passthrough, dynamic multi-provider routing, and non-blocking asynchronous audit logging.

## Features

- **Asynchronous Streaming Proxy**: Implemented via `httpx.AsyncClient` async generators to deliver zero-latency SSE response passthrough, keeping Time-to-First-Token (TTFT) close to native upstream APIs.
- **Dynamic Multi-Provider Routing**: Exposes a unified OpenAI-compatible interface that dynamically dispatches requests to DeepSeek, Gemini, or Qwen based on the `model` parameter, equipped with basic error isolation (fallback).
- **Non-blocking Audit Logging**: Utilizes `aiosqlite` to asynchronously log request metadata, response status, and token metrics, ensuring telemetry collection never blocks the main execution path.
- **Protocol Compatibility**: Fully compliant with the OpenAI `/v1/chat/completions` specification, supporting both streaming and non-streaming modalities.

## Quick Start

### 1. Prerequisites

Ensure Python 3.10+ is installed in your environment.

```bash
# Clone the repository and navigate into the directory
cd ai-gateway

# Install required dependencies
pip install -r requirements.txt
```

### 2. Setup Environment & Run

The gateway retrieves provider credentials via environment variables. Inject your API keys and spin up the service using uvicorn:

```bash
# Export the required API keys based on your selected providers
export DEEPSEEK_API_KEY="your_deepseek_key"
export GEMINI_API_KEY="your_gemini_key"
export QWEN_API_KEY="your_qwen_key"

# Start the gateway server
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### API Usage Example

Once started, the gateway is available at `http://127.0.0.1:8000`. You can interact with it using any OpenAI-compatible SDK or via standard curl:

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": true
  }'
```

### Project Structure

```
├── main.py          # Core gateway logic (routing, streaming proxy, and database lifespan)
├── requirements.txt # Core dependencies
└── .gitignore       # Git exclusion configuration (excludes .venv/ and local sqlite DBs)
```
