"""
一键配置阿里云百炼（DashScope）上游渠道和模型定价

用法：在项目根目录执行
    python scripts/setup_dashscope.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import UpstreamChannel, ModelPricing, ChannelStatus

# ============================================================
# 配置区 —— 把你的信息填到这里
# ============================================================
DASHSCOPE_CONFIG = {
    "name": "阿里百炼-通义千问",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "api_key": "sk-ws-H.RPYPRRR.x2oB.MEQCIBcvXD-Y5dA3pHbKL_Z5OOrkeIcfj_bzEhJIsLGhqlRJAiAuGxov5zFKK_DLkZH7iPqAApEy5NzOe2RZgGIHdnD_1A",
    "models": "*",          # * 表示支持所有模型
    "weight": 100,          # 负载权重（当前唯一渠道时无需关心）
    "priority": 0,
    "remark": "阿里云百炼 DashScope 兼容 OpenAI 接口",
}

# 通义千问系列模型定价（单位：元 / 1000 tokens）
# 以下是阿里云官方公开定价，你可以通过管理后台自行调整
QWEN_PRICING = [
    {"model": "qwen-turbo",           "input": 0.3,  "output": 0.6,  "desc": "通义千问 Turbo - 高性价比轻量模型"},
    {"model": "qwen-plus",            "input": 0.8,  "output": 2.0,  "desc": "通义千问 Plus - 平衡性能与成本"},
    {"model": "qwen-max",             "input": 2.0,  "output": 6.0,  "desc": "通义千问 Max - 顶级推理能力"},
    {"model": "qwen2.5-7b-instruct",  "input": 1.0,  "output": 2.0,  "desc": "Qwen2.5 7B 开源模型"},
    {"model": "qwen2.5-14b-instruct", "input": 2.0,  "output": 4.0,  "desc": "Qwen2.5 14B 开源模型"},
    {"model": "qwen2.5-32b-instruct", "input": 3.5,  "output": 7.0,  "desc": "Qwen2.5 32B 开源模型"},
    {"model": "qwen2.5-72b-instruct", "input": 4.0,  "output": 12.0, "desc": "Qwen2.5 72B 开源模型"},
]


async def main():
    async with AsyncSessionLocal() as db:
        # ---- 1. 添加上游渠道 ----
        result = await db.execute(
            select(UpstreamChannel).where(
                UpstreamChannel.base_url == DASHSCOPE_CONFIG["base_url"],
                UpstreamChannel.api_key == DASHSCOPE_CONFIG["api_key"],
            )
        )
        existing_channel = result.scalar_one_or_none()

        if existing_channel:
            print(f"[SKIP] 上游渠道已存在 (id={existing_channel.id})：{existing_channel.name}")
        else:
            channel = UpstreamChannel(
                name=DASHSCOPE_CONFIG["name"],
                base_url=DASHSCOPE_CONFIG["base_url"],
                api_key=DASHSCOPE_CONFIG["api_key"],
                models=DASHSCOPE_CONFIG["models"],
                weight=DASHSCOPE_CONFIG["weight"],
                priority=DASHSCOPE_CONFIG["priority"],
                status=ChannelStatus.active,
                remark=DASHSCOPE_CONFIG["remark"],
            )
            db.add(channel)
            await db.commit()
            await db.refresh(channel)
            print(f"[OK] 上游渠道已添加 (id={channel.id})：{channel.name}")

        # ---- 2. 添加模型定价 ----
        added = 0
        skipped = 0
        for p in QWEN_PRICING:
            result = await db.execute(
                select(ModelPricing).where(ModelPricing.model == p["model"])
            )
            existing = result.scalar_one_or_none()
            if existing:
                print(f"[SKIP] 模型定价已存在：{p['model']}  (id={existing.id})")
                skipped += 1
            else:
                pricing = ModelPricing(
                    model=p["model"],
                    input_price=p["input"],
                    output_price=p["output"],
                    description=p["desc"],
                    is_active=True,
                )
                db.add(pricing)
                added += 1

        if added:
            await db.commit()
            print(f"[OK] 新增 {added} 条模型定价")
        if skipped:
            print(f"[SKIP] 跳过 {skipped} 条已存在的定价")

        # ---- 3. 最终汇总 ----
        print("\n" + "=" * 60)
        print("[OK] 阿里云百炼 DashScope 配置完成！")
        print("=" * 60)
        print(f"Base URL : {DASHSCOPE_CONFIG['base_url']}")
        print(f"API Key  : {DASHSCOPE_CONFIG['api_key'][:12]}****")
        print(f"支持模型 : {DASHSCOPE_CONFIG['models']}")
        print(f"定价条数 : {len(QWEN_PRICING)}")
        print()
        print("下一步操作：")
        print("1. 启动服务：uvicorn app.main:app --port 8000")
        print("2. 进入 /admin 管理后台，检查「上游渠道」和「模型定价」")
        print("3. 如需调整利润空间，在管理后台修改模型定价即可")
        print("4. 测试：curl http://localhost:8000/v1/chat/completions -H 'Authorization: Bearer <用户API Key>' -d '{\"model\":\"qwen-turbo\",\"messages\":[{\"role\":\"user\",\"content\":\"hello\"}]}'")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
