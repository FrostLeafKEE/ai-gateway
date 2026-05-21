import json
import os
import time
from contextlib import asynccontextmanager

import aiosqlite
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

# ---------------------------------------------------------------------------
# Route table: ordered list of (keyword, env_var_base, env_var_key)
# Each entry reads its own TARGET_URL and TARGET_API_KEY from environment,
# falling back to the inline defaults shown below.
# ---------------------------------------------------------------------------
ROUTES = [
    {
        "match": "deepseek",
        "url": os.environ.get("DEEPSEEK_URL", "https://api.deepseek.com/v1"),
        "key_env": "DEEPSEEK_API_KEY",
    },
    {
        "match": "gemini",
        "url": os.environ.get("GEMINI_URL", "https://generativelanguage.googleapis.com/v1beta/openai"),
        "key_env": "GEMINI_API_KEY",
    },
    {
        "match": "qwen",
        "url": os.environ.get("QWEN_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        "key_env": "QWEN_API_KEY",
    },
    # Catch‑all default (lowest priority)
    {
        "match": "",
        "url": os.environ.get("FALLBACK_URL", "https://api.deepseek.com/v1"),
        "key_env": "FALLBACK_API_KEY",
    },
]

DB_PATH = os.environ.get("DB_PATH", "gateway.db")


# ── Lifespan (startup / shutdown) ────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS api_logs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            model_requested TEXT    NOT NULL,
            model_real      TEXT    NOT NULL,
            prompt_tokens   INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            latency_ms      INTEGER NOT NULL DEFAULT 0,
            status_code     INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
        );
    """)
    app.state.db = db

    yield

    await db.close()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ──────────────────────────────────────────────────────────────

def _resolve_route(model: str) -> dict | None:
    """Return the first matching route for *model* (case‑insensitive)."""
    lowered = model.lower()
    for route in ROUTES:
        if route["match"] and route["match"] in lowered:
            return route
    for route in ROUTES:
        if not route["match"]:
            return route
    return None


def _resolve_key(route: dict) -> str:
    """Resolve API key with fallback: channel‑specific → API_KEY → FALLBACK_API_KEY."""
    key = os.environ.get(route.get("key_env", ""), "") or ""
    if not key:
        key = os.environ.get("API_KEY", "") or ""
    if not key:
        key = os.environ.get("FALLBACK_API_KEY", "") or ""
    return key


def _estimate_tokens(text: str) -> int:
    """Heuristic token count: non‑whitespace chars × 1.3."""
    n = len(text.replace(" ", "").replace("\n", "").replace("\r", ""))
    return max(1, int(n * 1.3))


def _parse_sse_line(line: str) -> dict | None:
    """Parse a single ``data: {...}`` SSE line into a dict, or return None."""
    line = line.strip()
    if line.startswith("data: ") and line != "data: [DONE]":
        try:
            return json.loads(line[6:])
        except json.JSONDecodeError:
            return None
    return None


# ── Logging ──────────────────────────────────────────────────────────────

async def _log_completion(db, model_requested: str, model_real: str,
                           prompt_tokens: int, completion_tokens: int,
                           latency_ms: int, status_code: int):
    await db.execute(
        """INSERT INTO api_logs
               (model_requested, model_real, prompt_tokens, completion_tokens, latency_ms, status_code)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (model_requested, model_real, prompt_tokens, completion_tokens, latency_ms, status_code),
    )
    await db.commit()


async def _stream_with_logging(request: Request, url: str, headers: dict,
                                body: dict, route: dict):
    start_time = time.time()
    db = request.app.state.db
    model_requested = body.get("model", "")
    model_real = route["match"] or model_requested

    content_parts: list[str] = []
    usage = None
    status_code = 200

    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST", url + "/chat/completions", json=body, headers=headers
        ) as resp:
            status_code = resp.status_code

            async for line in resp.aiter_lines():
                try:
                    data = _parse_sse_line(line)
                    if data is not None:
                        if "usage" in data:
                            usage = data["usage"]
                        for choice in data.get("choices", []):
                            delta = choice.get("delta", {})
                            if "content" in delta:
                                content_parts.append(delta["content"])
                except Exception:
                    pass  # 单行解析失败不中断流

                yield (line + "\n").encode("utf-8")

    # ── stream finished → write audit log ──
    latency_ms = int((time.time() - start_time) * 1000)
    if usage:
        pt = usage.get("prompt_tokens", 0)
        ct = usage.get("completion_tokens", 0)
    else:
        pt = 0
        ct = _estimate_tokens("".join(content_parts))

    try:
        await _log_completion(db, model_requested, model_real, pt, ct, latency_ms, status_code)
    except Exception:
        pass  # 数据库写入失败不牵连前端


# ── Endpoint ─────────────────────────────────────────────────────────────

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    model = body.get("model", "")

    route = _resolve_route(model)
    if route is None:
        return {
            "error": {
                "message": f"Model '{model}' not supported by gateway",
                "type": "invalid_request_error",
                "param": "model",
                "code": "model_not_found",
            }
        }

    target_url = route["url"]
    target_key = _resolve_key(route)
    if not target_key:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "message": f"No API key available for '{model}' — set {route['key_env']}, API_KEY, or FALLBACK_API_KEY",
                    "type": "authentication_error",
                    "code": "no_api_key",
                }
            },
        )
    stream = body.get("stream", False)
    headers = {
        "Authorization": f"Bearer {target_key}",
        "Content-Type": "application/json",
    }

    if stream:
        return StreamingResponse(
            _stream_with_logging(request, target_url, headers, body, route),
            media_type="text/event-stream",
        )

    # ── Non‑streaming ────────────────────────────────────────────────────
    start_time = time.time()
    async with httpx.AsyncClient() as client:
        resp = await client.post(target_url + "/chat/completions", json=body, headers=headers)

    result = resp.json()
    latency_ms = int((time.time() - start_time) * 1000)

    usage = result.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    if not completion_tokens:
        content = ""
        choices = result.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
        completion_tokens = _estimate_tokens(content)

    await _log_completion(
        request.app.state.db,
        model,
        route["match"] or model,
        prompt_tokens,
        completion_tokens,
        latency_ms,
        resp.status_code,
    )

    return result
