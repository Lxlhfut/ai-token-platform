from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
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

