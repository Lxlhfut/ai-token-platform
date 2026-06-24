from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import ApiKey, UsageLog, User
from app.services.billing import calculate_cost, deduct_balance, get_model_pricing
from app.services.channel import normalize_base_url, select_channel

settings = get_settings()


async def authenticate_api_key(db: AsyncSession, raw_key: str) -> tuple[User, ApiKey]:
    result = await db.execute(select(ApiKey).where(ApiKey.key == raw_key, ApiKey.is_active.is_(True)))
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=401, detail={"error": {"message": "Invalid API key", "type": "invalid_api_key"}})
    result = await db.execute(select(User).where(User.id == api_key.user_id, User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail={"error": {"message": "User disabled", "type": "invalid_api_key"}})
    api_key.last_used_at = datetime.now(timezone.utc)
    return user, api_key


async def proxy_openai_request(
    db: AsyncSession,
    user: User,
    api_key: ApiKey,
    path: str,
    body: dict,
    stream: bool = False,
):
    model = body.get("model", "gpt-3.5-turbo")
    channel = await select_channel(db, model)
    if not channel:
        raise HTTPException(status_code=503, detail={"error": {"message": f"No channel available for model: {model}", "type": "server_error"}})

    pricing = await get_model_pricing(db, model)
    if not pricing:
        raise HTTPException(status_code=402, detail={"error": {"message": f"Model {model} has no pricing configured. Please contact admin.", "type": "invalid_request_error"}})

    # 流式传输：预估 8192 tokens 的费用作为最低余额门槛，避免用户余额几乎为 0 时白嫖
    est_stream_tokens = 8192 if stream else 1
    min_cost = calculate_cost(pricing, est_stream_tokens, 0)
    if user.balance < min_cost:
        raise HTTPException(
            status_code=402,
            detail={"error": {"message": "Insufficient balance", "type": "insufficient_quota"}},
        )

    base_url = normalize_base_url(channel.base_url)
    url = f"{base_url}{path}"
    headers = {
        "Authorization": f"Bearer {channel.api_key}",
        "Content-Type": "application/json",
    }
    request_id = f"req-{uuid.uuid4().hex[:16]}"

    if stream:
        return await _stream_proxy(db, user, api_key, channel, url, headers, body, model, pricing, request_id)

    async with httpx.AsyncClient(timeout=settings.upstream_timeout) as client:
        try:
            resp = await client.post(url, json=body, headers=headers)
        except httpx.RequestError as e:
            await _log_usage(db, user, api_key, channel, model, 0, 0, 0, 0, request_id, "error", str(e))
            await db.commit()
            raise HTTPException(status_code=502, detail={"error": {"message": f"Upstream error: {e}", "type": "server_error"}})

    if resp.status_code != 200:
        error_text = resp.text[:500]
        await _log_usage(db, user, api_key, channel, model, 0, 0, 0, 0, request_id, "error", error_text)
        await db.commit()
        raise HTTPException(status_code=resp.status_code, detail=resp.json() if resp.headers.get("content-type", "").startswith("application/json") else error_text)

    data = resp.json()
    usage = data.get("usage") or {}
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
    cost = calculate_cost(pricing, prompt_tokens, completion_tokens)

    if not await deduct_balance(db, user, cost, f"{model} usage {request_id}"):
        raise HTTPException(status_code=402, detail={"error": {"message": "Insufficient balance after request", "type": "insufficient_quota"}})

    await _log_usage(db, user, api_key, channel, model, prompt_tokens, completion_tokens, total_tokens, cost, request_id, "success")
    await db.commit()
    return data


async def _stream_proxy(db, user, api_key, channel, url, headers, body, model, pricing, request_id):
    from starlette.responses import StreamingResponse

    prompt_tokens = 0
    completion_tokens = 0
    chunks: list[str] = []

    async def generate():
        nonlocal prompt_tokens, completion_tokens
        async with httpx.AsyncClient(timeout=settings.upstream_timeout) as client:
            try:
                async with client.stream("POST", url, json=body, headers=headers) as resp:
                    if resp.status_code != 200:
                        error_body = await resp.aread()
                        yield error_body
                        await _log_usage(db, user, api_key, channel, model, 0, 0, 0, 0, request_id, "error", error_body.decode()[:500])
                        await db.commit()
                        return
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            payload = line[6:]
                            if payload.strip() == "[DONE]":
                                yield "data: [DONE]\n\n"
                                continue
                            try:
                                chunk = json.loads(payload)
                                usage = chunk.get("usage")
                                if usage:
                                    prompt_tokens = usage.get("prompt_tokens", prompt_tokens)
                                    completion_tokens = usage.get("completion_tokens", completion_tokens)
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                if delta.get("content"):
                                    completion_tokens += max(len(delta["content"]) // 4, 1)
                            except json.JSONDecodeError:
                                pass
                        chunks.append(line)
                        yield f"{line}\n\n"
            except httpx.RequestError as e:
                await _log_usage(db, user, api_key, channel, model, 0, 0, 0, 0, request_id, "error", str(e))
                await db.commit()
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                return

        total_tokens = prompt_tokens + completion_tokens
        cost = calculate_cost(pricing, prompt_tokens, completion_tokens)
        deducted = await deduct_balance(db, user, cost, f"{model} stream {request_id}")
        status = "success" if deducted else "insufficient_balance"
        await _log_usage(db, user, api_key, channel, model, prompt_tokens, completion_tokens, total_tokens, cost, request_id, status)
        await db.commit()

    return StreamingResponse(generate(), media_type="text/event-stream")


async def _log_usage(db, user, api_key, channel, model, prompt, completion, total, cost, request_id, status, error=None):
    log = UsageLog(
        user_id=user.id,
        channel_id=channel.id if channel else None,
        api_key_id=api_key.id if api_key else None,
        model=model,
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=total,
        cost=cost,
        request_id=request_id,
        status=status,
        error_message=error,
    )
    db.add(log)
