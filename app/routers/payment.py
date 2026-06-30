"""
支付路由 — 支付宝电脑网站支付 + 微信 Native 支付
"""
from __future__ import annotations

import io
import json
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import RechargeOrder, RechargeOrderStatus, User
from app.services.alipay import build_page_pay_url, verify_notify
from app.services.billing import recharge_balance
from app.services.wechatpay import (
    create_native_order,
    is_configured as wechat_configured,
    verify_notify as wechat_verify_notify,
)

router = APIRouter(prefix="/api/payment", tags=["payment"])
settings = get_settings()


# ===================== 支付宝 =====================

@router.post("/alipay/create")
async def create_alipay_order(
    amount: float = Body(..., gt=0, embed=True, description="充值金额（元）"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建支付宝支付订单，返回支付跳转 URL"""
    if not settings.alipay_app_id:
        raise HTTPException(status_code=503, detail="支付宝支付未配置")

    order_no = "A" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + secrets.token_hex(4).upper()

    order = RechargeOrder(
        order_no=order_no,
        user_id=user.id,
        amount=amount,
        pay_method="alipay",
        status=RechargeOrderStatus.pending,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    subject = f"{settings.platform_name} 余额充值 ¥{amount:.2f}"
    pay_url = build_page_pay_url(
        out_trade_no=order_no,
        total_amount=amount,
        subject=subject,
    )

    return {"ok": True, "order_no": order_no, "pay_url": pay_url}


@router.post("/alipay/notify")
async def alipay_notify(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """支付宝异步通知回调"""
    form = await request.form()
    params = dict(form)

    if not verify_notify(params):
        return HTMLResponse(content="fail", status_code=400)

    trade_status = params.get("trade_status", "")
    out_trade_no = params.get("out_trade_no", "")

    result = await db.execute(
        select(RechargeOrder).where(RechargeOrder.order_no == out_trade_no)
    )
    order = result.scalar_one_or_none()

    if not order:
        return HTMLResponse(content="fail", status_code=404)
    if order.status == RechargeOrderStatus.paid:
        return HTMLResponse(content="success")

    if trade_status in ("TRADE_SUCCESS", "TRADE_FINISHED"):
        user_result = await db.execute(select(User).where(User.id == order.user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            return HTMLResponse(content="fail", status_code=404)

        order.status = RechargeOrderStatus.paid
        order.paid_at = datetime.now(timezone.utc)

        await recharge_balance(
            db, user, order.amount,
            remark=f"支付宝支付 {order.order_no}",
        )
        return HTMLResponse(content="success")

    return HTMLResponse(content="success")


@router.get("/alipay/return")
async def alipay_return(request: Request, db: AsyncSession = Depends(get_db)):
    """支付宝同步跳转 — 跳回用户中心"""
    params = dict(request.query_params)

    if verify_notify(params):
        out_trade_no = params.get("out_trade_no", "")
        result = await db.execute(
            select(RechargeOrder).where(RechargeOrder.order_no == out_trade_no)
        )
        order = result.scalar_one_or_none()
        if order and order.status != RechargeOrderStatus.paid:
            user_result = await db.execute(select(User).where(User.id == order.user_id))
            user = user_result.scalar_one_or_none()
            if user:
                order.status = RechargeOrderStatus.paid
                order.paid_at = datetime.now(timezone.utc)
                await recharge_balance(
                    db, user, order.amount,
                    remark=f"支付宝支付 {order.order_no}",
                )

    return RedirectResponse(url="/dashboard", status_code=302)


@router.get("/alipay/status")
async def check_alipay_config():
    """检查支付宝是否已配置"""
    return {"configured": bool(settings.alipay_app_id)}


# ===================== 微信支付 =====================

@router.post("/wechat/create")
async def create_wechat_order(
    amount: float = Body(..., gt=0, embed=True, description="充值金额（元）"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建微信 Native 支付订单，返回 code_url（前端用此生成二维码）"""
    if not wechat_configured():
        raise HTTPException(status_code=503, detail="微信支付未配置")

    order_no = "W" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + secrets.token_hex(4).upper()

    order = RechargeOrder(
        order_no=order_no,
        user_id=user.id,
        amount=amount,
        pay_method="wechat_pay",
        status=RechargeOrderStatus.pending,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    description = f"{settings.platform_name} 余额充值 ¥{amount:.2f}"
    try:
        code_url = await create_native_order(
            out_trade_no=order_no,
            total_amount=amount,
            description=description,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"微信支付下单失败: {str(e)}")

    return {"ok": True, "order_no": order_no, "code_url": code_url}


@router.post("/wechat/notify")
async def wechat_notify(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """微信支付异步通知回调"""
    body_raw = await request.body()
    body_str = body_raw.decode("utf-8")

    # 解析 headers
    headers_lower = {k.lower(): v for k, v in request.headers.items()}

    # 验证签名 + 解密 resource
    verified, trade_data = await wechat_verify_notify(headers_lower, body_str)
    if not verified or not trade_data:
        return Response(content=json.dumps({"code": "FAIL", "message": "签名验证失败"}), media_type="application/json", status_code=400)

    out_trade_no = trade_data.get("out_trade_no", "")
    trade_state = trade_data.get("trade_state", "")

    result = await db.execute(
        select(RechargeOrder).where(RechargeOrder.order_no == out_trade_no)
    )
    order = result.scalar_one_or_none()

    if not order:
        return Response(content=json.dumps({"code": "FAIL", "message": "订单不存在"}), media_type="application/json", status_code=404)

    if order.status == RechargeOrderStatus.paid:
        return Response(content=json.dumps({"code": "SUCCESS"}), media_type="application/json")

    if trade_state == "SUCCESS":
        user_result = await db.execute(select(User).where(User.id == order.user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            return Response(content=json.dumps({"code": "FAIL", "message": "用户不存在"}), media_type="application/json", status_code=404)

        order.status = RechargeOrderStatus.paid
        order.paid_at = datetime.now(timezone.utc)

        await recharge_balance(
            db, user, order.amount,
            remark=f"微信支付 {order.order_no}",
        )

    return Response(content=json.dumps({"code": "SUCCESS"}), media_type="application/json")


@router.get("/wechat/status")
async def check_wechat_config():
    """检查微信支付是否已配置"""
    return {"configured": wechat_configured()}


# ===================== 订单状态查询 =====================

@router.get("/order/{order_no}")
async def query_order_status(
    order_no: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询支付订单状态（用于前端轮询）"""
    result = await db.execute(
        select(RechargeOrder).where(
            RechargeOrder.order_no == order_no,
            RechargeOrder.user_id == user.id,
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return {
        "order_no": order.order_no,
        "amount": order.amount,
        "status": order.status.value,
        "pay_method": order.pay_method,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
    }


# ===================== QR 码生成 =====================

@router.get("/qrcode")
async def generate_qrcode(data: str = Query(..., description="二维码内容（微信 code_url）")):
    """生成 PNG 格式的支付二维码图片"""
    import qrcode as qrcode_lib

    qr = qrcode_lib.QRCode(
        version=1,
        error_correction=qrcode_lib.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return StreamingResponse(buf, media_type="image/png")
