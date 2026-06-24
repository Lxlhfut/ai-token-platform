"""
Anthropic ↔ OpenAI 格式双向转换适配器。

Claude Code / Claude Desktop 使用 Anthropic 原生 API 格式 (/v1/messages)，
本模块将其转换为 OpenAI 格式 (/v1/chat/completions)，复用现有计费与渠道路由，
再将 OpenAI 响应转换回 Anthropic 格式返回给客户端。
"""

from __future__ import annotations

import json
import uuid

from fastapi import HTTPException


# ── 请求转换：Anthropic → OpenAI ──────────────────────────────────────────

def anthropic_to_openai_request(anthropic_body: dict) -> dict:
    """将 Anthropic /v1/messages 请求体转换为 OpenAI /v1/chat/completions 格式。"""
    messages: list[dict] = []

    # Anthropic 的 system 是顶层字段，OpenAI 作为 messages[0] role=system
    system = anthropic_body.get("system")
    if isinstance(system, str) and system.strip():
        messages.append({"role": "system", "content": system})
    elif isinstance(system, list):
        text_parts = [b["text"] for b in system if isinstance(b, dict) and b.get("type") == "text"]
        if text_parts:
            messages.append({"role": "system", "content": "\n".join(text_parts)})

    # Anthropic messages → OpenAI messages
    for msg in anthropic_body.get("messages", []):
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif block.get("type") == "image":
                        # 透传图片 base64
                        messages.append({"role": role, "content": [
                            {"type": "image_url", "image_url": {"url": f"data:{block.get('source',{}).get('media_type','image/jpeg')};base64,{block.get('source',{}).get('data','')}"}}
                        ]})
                        continue
            if text_parts:
                messages.append({"role": role, "content": "\n".join(text_parts)})
        else:
            messages.append({"role": role, "content": str(content)})

    openai_body: dict = {
        "model": anthropic_body.get("model", "claude-3-5-sonnet-20241022"),
        "messages": messages,
        "max_tokens": anthropic_body.get("max_tokens", 1024),
    }

    # 透传可选参数
    for key in ("temperature", "top_p", "stop", "stream"):
        if key in anthropic_body:
            openai_body[key] = anthropic_body[key]

    return openai_body


# ── 响应转换：OpenAI → Anthropic ──────────────────────────────────────────

def openai_to_anthropic_response(openai_response: dict, model: str) -> dict:
    """将 OpenAI /v1/chat/completions 非流式响应转换为 Anthropic 格式。"""
    choices = openai_response.get("choices", [])
    content_text = ""
    finish_reason = "end_turn"

    if choices:
        message = choices[0].get("message") or {}
        content_text = message.get("content") or ""
        fr = choices[0].get("finish_reason", "stop")
        finish_reason = _map_finish_reason(fr)

    usage = openai_response.get("usage") or {}
    msg_id = openai_response.get("id") or f"msg_{uuid.uuid4().hex[:24]}"

    return {
        "id": msg_id,
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": content_text}],
        "model": model,
        "stop_reason": finish_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }


def _map_finish_reason(openai_reason: str) -> str:
    """OpenAI finish_reason → Anthropic stop_reason"""
    mapping = {
        "stop": "end_turn",
        "length": "max_tokens",
        "content_filter": "end_turn",  # Anthropic 没有 content_filter，映射为 end_turn
    }
    return mapping.get(openai_reason, openai_reason)


# ── 流式响应：非流式内部调用 + 模拟 Anthropic SSE 事件 ────────────────────

def build_anthropic_stream(anthropic_response: dict) -> list[str]:
    """将非流式 Anthropic 响应组装为标准 Anthropic SSE 事件序列。

    Claude Code 需要严格的 SSE 事件格式（event: xxx\ndata: {}\n\n）。
    内部使用非流式调用拿到完整回复后，拆分出 message_start / content_block_start /
    content_block_delta / content_block_stop / message_delta / message_stop 六个事件。
    """
    msg_id = anthropic_response["id"]
    model = anthropic_response["model"]
    stop_reason = anthropic_response.get("stop_reason", "end_turn")
    text = anthropic_response["content"][0]["text"] if anthropic_response.get("content") else ""
    usage = anthropic_response.get("usage", {})

    def sse(event_type: str, data: dict) -> str:
        return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    return [
        sse("message_start", {
            "type": "message_start",
            "message": {
                "id": msg_id, "type": "message", "role": "assistant",
                "content": [], "model": model,
                "stop_reason": None, "stop_sequence": None,
                "usage": {"input_tokens": 0, "output_tokens": 0},
            },
        }),
        sse("content_block_start", {
            "type": "content_block_start", "index": 0,
            "content_block": {"type": "text", "text": ""},
        }),
        sse("content_block_delta", {
            "type": "content_block_delta", "index": 0,
            "delta": {"type": "text_delta", "text": text},
        }),
        sse("content_block_stop", {
            "type": "content_block_stop", "index": 0,
        }),
        sse("message_delta", {
            "type": "message_delta",
            "delta": {"stop_reason": stop_reason, "stop_sequence": None},
            "usage": {"output_tokens": usage.get("output_tokens", 0)},
        }),
        sse("message_stop", {
            "type": "message_stop",
        }),
    ]


# ── 错误转换 ──────────────────────────────────────────────────────────────

def _openai_error_to_anthropic(status_code: int, detail) -> HTTPException:
    """将 OpenAI 格式的 HTTPException 转为 Anthropic 格式。"""
    error_body = {"type": "error", "error": {"type": "api_error", "message": "Unknown error"}}

    if isinstance(detail, dict):
        inner = detail.get("error", {})
        if isinstance(inner, dict):
            error_body["error"] = {
                "type": inner.get("type", "api_error"),
                "message": inner.get("message", str(detail)),
            }
        else:
            error_body["error"]["message"] = str(detail)
    elif isinstance(detail, str):
        error_body["error"]["message"] = detail

    return HTTPException(status_code=status_code, detail=error_body)
