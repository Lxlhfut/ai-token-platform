from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.anthropic_adapter import (
    anthropic_to_openai_request,
    build_anthropic_stream,
    openai_to_anthropic_response,
)
from app.services.proxy_service import authenticate_api_key, proxy_openai_request

router = APIRouter(tags=["proxy"])


def _extract_api_key(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return request.headers.get("x-api-key", "").strip()


@router.post("/v1/chat/completions")
async def chat_completions(request: Request, db: AsyncSession = Depends(get_db)):
    raw_key = _extract_api_key(request)
    user, api_key = await authenticate_api_key(db, raw_key)
    try:
        body = await request.json()
    except Exception:
        raw = await request.body()
        import json
        try:
            body = json.loads(raw)
        except Exception:
            raise HTTPException(status_code=400, detail={"error": {"message": "Invalid JSON body", "type": "invalid_request_error"}})
    stream = body.get("stream", False)
    result = await proxy_openai_request(db, user, api_key, "/chat/completions", body, stream=stream)
    if hasattr(result, "__aiter__") or hasattr(result, "body_iterator"):
        return result
    return result


@router.post("/v1/completions")
async def completions(request: Request, db: AsyncSession = Depends(get_db)):
    raw_key = _extract_api_key(request)
    user, api_key = await authenticate_api_key(db, raw_key)
    body = await request.json()
    stream = body.get("stream", False)
    result = await proxy_openai_request(db, user, api_key, "/completions", body, stream=stream)
    if hasattr(result, "body_iterator"):
        return result
    return result


@router.post("/v1/embeddings")
async def embeddings(request: Request, db: AsyncSession = Depends(get_db)):
    """Embeddings 接口，LobeChat / OpenAI Translator 等会用到"""
    raw_key = _extract_api_key(request)
    user, api_key = await authenticate_api_key(db, raw_key)
    body = await request.json()
    result = await proxy_openai_request(db, user, api_key, "/embeddings", body)
    return result


@router.get("/v1/models")
async def list_models(request: Request, db: AsyncSession = Depends(get_db)):
    raw_key = _extract_api_key(request)
    await authenticate_api_key(db, raw_key)
    from sqlalchemy import select
    from app.models import ModelPricing, UpstreamChannel, ChannelStatus
    from app.services.channel import channel_supports_model

    # 1) 取所有活跃定价（排除 * 通配）
    p_result = await db.execute(select(ModelPricing).where(ModelPricing.is_active.is_(True), ModelPricing.model != "*"))
    pricings = p_result.scalars().all()

    # 2) 取所有活跃渠道
    c_result = await db.execute(select(UpstreamChannel).where(UpstreamChannel.status == ChannelStatus.active))
    channels = c_result.scalars().all()

    # 3) 只列出「有定价 且 有渠道支持」的模型
    supported = []
    for p in pricings:
        for ch in channels:
            if channel_supports_model(ch, p.model):
                supported.append(p)
                break

    return {
        "object": "list",
        "data": [{"id": m.model, "object": "model", "created": 1700000000, "owned_by": "platform"} for m in supported],
    }


@router.get("/v1/dashboard/billing/subscription")
async def billing_subscription(request: Request, db: AsyncSession = Depends(get_db)):
    """Cursor Verify 会请求此端点检查账户配额"""
    raw_key = _extract_api_key(request)
    user, _ = await authenticate_api_key(db, raw_key)
    return {
        "object": "billing_subscription",
        "has_payment_method": True,
        "soft_limit_usd": 999999,
        "hard_limit_usd": 999999,
        "system_hard_limit_usd": 999999,
        "plan": {"id": "payg", "title": "Pay-as-you-go"},
    }


@router.get("/v1/dashboard/billing/usage")
async def billing_usage(request: Request, db: AsyncSession = Depends(get_db)):
    """Cursor / ChatGPT wrapper 会请求此端点查询用量"""
    raw_key = _extract_api_key(request)
    user, _ = await authenticate_api_key(db, raw_key)
    return {
        "object": "list",
        "daily_costs": [],
        "total_usage": round(user.balance * 100, 2),  # 单位 cents
    }


# ── Anthropic 兼容端点 ────────────────────────────────────────────────────

def _anthropic_error_response(status_code: int, detail) -> JSONResponse:
    """将 OpenAI 格式 HTTPException detail 转为 Anthropic 格式 JSONResponse。
    用 JSONResponse 而非 raise HTTPException，避免 FastAPI 再包一层 {"detail": ...}。"""
    msg = "Unknown error"
    err_type = "api_error"
    if isinstance(detail, dict):
        inner = detail.get("error", {})
        if isinstance(inner, dict):
            msg = inner.get("message", str(detail))
            err_type = inner.get("type", "api_error")
        elif isinstance(inner, str):
            msg = inner
    elif isinstance(detail, str):
        msg = detail
    return JSONResponse(
        status_code=status_code,
        content={"type": "error", "error": {"type": err_type, "message": msg}},
    )


@router.post("/v1/messages")
async def anthropic_messages(request: Request, db: AsyncSession = Depends(get_db)):
    """Anthropic 兼容 /v1/messages — Claude Code / Claude Desktop 可用此端点。"""
    try:
        # Anthropic 认证支持 x-api-key 和 Authorization: Bearer 两种方式
        raw_key = _extract_api_key(request)
        user, api_key = await authenticate_api_key(db, raw_key)

        anthropic_body = await request.json()
    except HTTPException as e:
        return _anthropic_error_response(e.status_code, e.detail)
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"type": "error", "error": {"type": "invalid_request_error", "message": "Invalid JSON body"}},
        )

    openai_body = anthropic_to_openai_request(anthropic_body)
    model = openai_body["model"]
    is_stream = anthropic_body.get("stream", False)

    try:
        if is_stream:
            # 流式请求：内部用非流式拿完整回复，再模拟 Anthropic SSE 事件序列
            openai_body["stream"] = False
            openai_resp = await proxy_openai_request(db, user, api_key, "/chat/completions", openai_body, stream=False)
            anthropic_resp = openai_to_anthropic_response(openai_resp, model)

            async def generate():
                for event in build_anthropic_stream(anthropic_resp):
                    yield event

            return StreamingResponse(generate(), media_type="text/event-stream",
                                     headers={"x-robots-tag": "noindex"})
        else:
            openai_resp = await proxy_openai_request(db, user, api_key, "/chat/completions", openai_body, stream=False)
            return openai_to_anthropic_response(openai_resp, model)
    except HTTPException as e:
        return _anthropic_error_response(e.status_code, e.detail)


@router.post("/v1/messages/count_tokens")
async def anthropic_count_tokens(request: Request, db: AsyncSession = Depends(get_db)):
    """Anthropic token 计数端点 — Claude Code 可能调用，返回估算值。"""
    try:
        raw_key = _extract_api_key(request)
        await authenticate_api_key(db, raw_key)

        body = await request.json()
    except HTTPException as e:
        return _anthropic_error_response(e.status_code, e.detail)
    except Exception:
        return JSONResponse(status_code=400, content={"type": "error", "error": {"type": "invalid_request_error", "message": "Invalid JSON"}})

    # 粗估算：每 4 字符 ≈ 1 token
    text = ""
    for msg in body.get("messages", []):
        content = msg.get("content", "")
        if isinstance(content, str):
            text += content
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text += block.get("text", "")

    est = max(len(text) // 4, 1)
    return {"input_tokens": est}

