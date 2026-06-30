from __future__ import annotations

import random

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChannelStatus, UpstreamChannel


def channel_supports_model(channel: UpstreamChannel, model: str) -> bool:
    if channel.models.strip() == "*":
        return True
    supported = {m.strip() for m in channel.models.split(",") if m.strip()}
    return model in supported


async def select_channel(db: AsyncSession, model: str) -> Optional[UpstreamChannel]:
    result = await db.execute(
        select(UpstreamChannel)
        .where(UpstreamChannel.status == ChannelStatus.active)
        .order_by(UpstreamChannel.priority.desc(), UpstreamChannel.id.asc())
    )
    channels = [c for c in result.scalars().all() if channel_supports_model(c, model)]
    if not channels:
        return None
    weights = [max(c.weight, 1) for c in channels]
    return random.choices(channels, weights=weights, k=1)[0]


def normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")
