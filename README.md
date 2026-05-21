# High-Performance AI Gateway (高性能 AI 聚合网关)

基于 FastAPI + HTTPX + Async Generator 打造的轻量级大模型聚合网关，完美对齐 OpenAI/DeepSeek 标准接口规范。

## 🚀 核心特性
- **零延迟流式转发**：采用异步生成器（Async Generator）包装上游 SSE 二进制流，实现打字机特效的秒级透传。
- **动态分发路由**：支持基于模型名称（如 `deepseek`, `qwen`, `gemini`）的自动渠道匹配与向前兼容的 Fallback 兜底机制。
- **非阻塞异步审计**：结合 `aiosqlite` 异步驱动，在流式连接闭合尾端进行非阻塞埋点，静默记录耗时及 Token 开销，完全不拖慢前端响应。

## 🛠️ 快速启动
1. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

2. 配置环境变量，启动服务：
   ```bash
   export DEEPSEEK_API_KEY="your_key"
   uvicorn main:app --reload
   ```
   将 `your_key` 替换为你的 DeepSeek API Key。其他渠道（Gemini、Qwen 等）对应设置 `GEMINI_API_KEY`、`QWEN_API_KEY`。

3. 调用示例：
   ```bash
   curl http://localhost:8000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{
       "model": "deepseek-chat",
       "messages": [{"role": "user", "content": "Hello"}],
       "stream": true
     }'
   ```
