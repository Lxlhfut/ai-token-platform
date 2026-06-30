"""
支付宝电脑网站支付服务
API: alipay.trade.page.pay
"""
from __future__ import annotations

import base64
import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote_plus, urlencode

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

from app.config import get_settings

settings = get_settings()

ALIPAY_GATEWAY = "https://openapi.alipay.com/gateway.do"


def _ensure_pem(key: str, label: str) -> str:
    """自动补全 PEM 头尾标识（兼容纯 base64 格式）"""
    key = key.strip()
    if not key.startswith("-----BEGIN"):
        lines = []
        for i in range(0, len(key), 64):
            lines.append(key[i:i+64])
        return f"-----BEGIN {label}-----\n" + "\n".join(lines) + f"\n-----END {label}-----"
    return key


def _load_private_key() -> object:
    """加载商户私钥"""
    key = settings.alipay_app_private_key
    if not key:
        raise ValueError("ALIPAY_APP_PRIVATE_KEY 未配置")
    pem = _ensure_pem(key, "PRIVATE KEY")
    return serialization.load_pem_private_key(
        pem.encode("utf-8"),
        password=None,
        backend=default_backend(),
    )


def _sign_string(sign_str: str) -> str:
    """RSA2-SHA256 签名"""
    private_key = _load_private_key()
    signature = private_key.sign(
        sign_str.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("utf-8")


def _verify_signature(sign_str: str, signature: str) -> bool:
    """验证支付宝公钥签名"""
    public_key_pem = settings.alipay_public_key
    if not public_key_pem:
        raise ValueError("ALIPAY_PUBLIC_KEY 未配置")
    pem = _ensure_pem(public_key_pem, "PUBLIC KEY")
    public_key = serialization.load_pem_public_key(
        pem.encode("utf-8"),
        backend=default_backend(),
    )
    try:
        public_key.verify(
            base64.b64decode(signature),
            sign_str.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False


def _build_sign_str(params: dict) -> str:
    """构建待签名字符串：排序后 & 连接，不编码"""
    sorted_items = sorted(
        (k, v) for k, v in params.items() if v not in (None, "") and k not in ("sign",)
    )
    return "&".join(f"{k}={v}" for k, v in sorted_items)


def _build_query(params: dict) -> str:
    """构建 URL 编码的参数字符串（包含 sign）"""
    sorted_items = sorted(
        (k, v) for k, v in params.items() if v not in (None, "")
    )
    return "&".join(f"{k}={quote_plus(str(v))}" for k, v in sorted_items)


def build_page_pay_url(
    out_trade_no: str,
    total_amount: float,
    subject: str,
) -> str:
    """
    构建支付宝电脑网站支付 URL
    返回完整的支付宝收银台 URL，前端直接跳转即可
    """
    biz_content = {
        "out_trade_no": out_trade_no,
        "total_amount": f"{total_amount:.2f}",
        "subject": subject,
        "product_code": "FAST_INSTANT_TRADE_PAY",
    }

    params = {
        "app_id": settings.alipay_app_id,
        "method": "alipay.trade.page.pay",
        "format": "JSON",
        "charset": "utf-8",
        "sign_type": "RSA2",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "version": "1.0",
        "notify_url": settings.alipay_notify_url,
        "return_url": settings.alipay_return_url,
        "biz_content": json.dumps(biz_content, ensure_ascii=False),
    }

    sign_str = _build_sign_str(params)
    params["sign"] = _sign_string(sign_str)

    return f"{ALIPAY_GATEWAY}?{_build_query(params)}"


def verify_notify(params: dict) -> bool:
    """验证支付宝异步通知签名"""
    sign = params.get("sign", "")
    sign_str = _build_sign_str(params)
    return _verify_signature(sign_str, sign)
