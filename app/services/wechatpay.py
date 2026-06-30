"""
微信支付 V3 Native 支付服务
Native 支付：后端下单获取 code_url，前端生成二维码，用户扫码支付后异步通知到账
"""
from __future__ import annotations

import base64
import json
import secrets
import time
from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
from httpx import AsyncClient

from app.config import get_settings

settings = get_settings()

WECHAT_API_BASE = "https://api.mch.weixin.qq.com"

# 缓存微信支付平台证书（用于验签回调通知）
_platform_cert: Optional[bytes] = None


def _ensure_pem(key: str, label: str) -> str:
    """自动补全 PEM 头尾标识（兼容纯 base64 格式）"""
    key = key.strip()
    if not key.startswith("-----BEGIN"):
        lines = []
        for i in range(0, len(key), 64):
            lines.append(key[i:i + 64])
        return f"-----BEGIN {label}-----\n" + "\n".join(lines) + f"\n-----END {label}-----"
    return key


def _sign(method: str, url: str, timestamp: int, nonce_str: str, body: str) -> str:
    """生成微信支付 V3 请求签名（RSA-SHA256）"""
    message = f"{method}\n{url}\n{timestamp}\n{nonce_str}\n{body}\n"
    private_key_pem = _ensure_pem(settings.wechat_private_key_pem, "PRIVATE KEY")
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode("utf-8"),
        password=None,
        backend=default_backend(),
    )
    signature = private_key.sign(
        message.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("utf-8")


def _make_authorization(method: str, url: str, body: str = "") -> tuple[str, str, str]:
    """构建 Authorization 请求头，同时返回 timestamp 和 nonce（用于验签回传）"""
    timestamp = int(time.time())
    nonce_str = secrets.token_hex(16)
    signature = _sign(method, url, timestamp, nonce_str, body)
    auth = (
        f'WECHATPAY2-SHA256-RSA2048 '
        f'mchid="{settings.wechat_mch_id}",'
        f'nonce_str="{nonce_str}",'
        f'timestamp="{timestamp}",'
        f'serial_no="{settings.wechat_serial_no}",'
        f'signature="{signature}"'
    )
    return auth


async def _fetch_platform_cert() -> bytes:
    """获取微信支付平台证书（用于验证回调签名）"""
    global _platform_cert
    if _platform_cert:
        return _platform_cert

    url = "/v3/certificates"
    auth = _make_authorization("GET", url)
    headers = {
        "Authorization": auth,
        "Accept": "application/json",
        "User-Agent": "AI-Token-Platform/1.0",
    }

    async with AsyncClient(base_url=WECHAT_API_BASE, timeout=15) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    cert_info = data["data"][0]
    encrypt_cert = cert_info["encrypt_certificate"]

    # 用 APIv3 密钥解密证书
    aes_key = settings.wechat_api_v3_key.encode("utf-8")
    cipher = AESGCM(aes_key)
    plaintext = cipher.decrypt(
        base64.b64decode(encrypt_cert["ciphertext"]),
        encrypt_cert.get("associated_data", "").encode("utf-8") if encrypt_cert.get("associated_data") else b"",
        encrypt_cert["nonce"].encode("utf-8"),
    )
    _platform_cert = plaintext
    return plaintext


def _verify_signature(timestamp: str, nonce_str: str, body: str, signature: str) -> bool:
    """用平台证书验证回调签名"""
    if not _platform_cert:
        return False
    try:
        public_key = serialization.load_pem_public_key(
            _platform_cert,
            backend=default_backend(),
        )
        message = f"{timestamp}\n{nonce_str}\n{body}\n"
        public_key.verify(
            base64.b64decode(signature),
            message.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False


async def create_native_order(
    out_trade_no: str,
    total_amount: float,
    description: str,
) -> str:
    """
    创建 Native 支付订单，返回 code_url

    Args:
        out_trade_no: 商户订单号
        total_amount: 金额（元）
        description: 商品描述

    Returns:
        code_url: weixin://wxpay/bizpayurl?pr=xxx 格式的二维码链接
    """
    total_cents = int(round(total_amount * 100))

    body = json.dumps({
        "appid": settings.wechat_app_id,
        "mchid": settings.wechat_mch_id,
        "description": description,
        "out_trade_no": out_trade_no,
        "notify_url": settings.wechat_notify_url,
        "amount": {
            "total": total_cents,
            "currency": "CNY",
        },
    }, ensure_ascii=False)

    url = "/v3/pay/transactions/native"
    auth = _make_authorization("POST", url, body)
    headers = {
        "Authorization": auth,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "AI-Token-Platform/1.0",
    }

    async with AsyncClient(base_url=WECHAT_API_BASE, timeout=15) as client:
        resp = await client.post(url, content=body, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    code_url = data.get("code_url", "")
    if not code_url:
        raise ValueError(f"微信支付返回异常: {json.dumps(data, ensure_ascii=False)}")

    return code_url


async def decrypt_notify_resource(resource: dict) -> dict:
    """
    解密微信支付回调通知中的 resource 字段

    微信回调 body 结构：
    {
      "id": "...",
      "create_time": "...",
      "resource_type": "encrypt-resource",
      "event_type": "TRANSACTION.SUCCESS",
      "resource": {
        "algorithm": "AEAD_AES_256_GCM",
        "ciphertext": "...",
        "associated_data": "",
        "nonce": "...",
        "original_type": "transaction"
      }
    }

    解密后得到交易详情 dict，包含 out_trade_no、trade_state 等字段
    """
    aes_key = settings.wechat_api_v3_key.encode("utf-8")
    cipher = AESGCM(aes_key)

    plaintext = cipher.decrypt(
        base64.b64decode(resource["ciphertext"]),
        resource.get("associated_data", "").encode("utf-8") if resource.get("associated_data") else b"",
        resource["nonce"].encode("utf-8"),
    )

    return json.loads(plaintext.decode("utf-8"))


async def verify_notify(headers: dict, body_raw: str) -> tuple[bool, dict | None]:
    """
    验证微信支付回调通知 → 返回 (是否成功, 解密后的交易数据)

    Args:
        headers: 请求头 dict（需要 wechatpay-timestamp/nonce/signature/serial）
        body_raw: 请求体原始 JSON 字符串

    Returns:
        (verified, decrypted_trade_data)
    """
    # 1. 获取平台证书（用于验签）
    await _fetch_platform_cert()

    # 2. 验证请求签名
    timestamp = headers.get("wechatpay-timestamp", "")
    nonce = headers.get("wechatpay-nonce", "")
    signature = headers.get("wechatpay-signature", "")
    serial = headers.get("wechatpay-serial", "")

    if not all([timestamp, nonce, signature]):
        return False, None

    if not _verify_signature(timestamp, nonce, body_raw, signature):
        return False, None

    # 3. 解密 resource
    body_data = json.loads(body_raw)
    resource = body_data.get("resource", {})
    if not resource:
        return False, None

    try:
        trade_data = await decrypt_notify_resource(resource)
        return True, trade_data
    except Exception:
        return False, None


def is_configured() -> bool:
    """检查微信支付是否已全部配置"""
    return all([
        settings.wechat_mch_id,
        settings.wechat_app_id,
        settings.wechat_api_v3_key,
        settings.wechat_serial_no,
        settings.wechat_private_key,
        settings.wechat_notify_url,
    ])
