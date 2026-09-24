"""总平台登录密码加密。"""

from __future__ import annotations

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


def rsa_encrypt(public_key_pem: str, plaintext: str) -> str:
    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    except (ValueError, TypeError) as e:
        raise ValueError(f"无法解析服务端返回的 RSA 公钥: {e}") from e

    if not isinstance(public_key, rsa.RSAPublicKey):
        raise ValueError("总平台 RSA 接口返回的公钥不是 RSA 公钥")
    encrypted = public_key.encrypt(plaintext.encode("utf-8"), padding.PKCS1v15())
    return base64.b64encode(encrypted).decode("ascii")
