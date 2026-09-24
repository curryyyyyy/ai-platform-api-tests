from __future__ import annotations

import base64

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa

from framework.auth.crypto import rsa_encrypt


def test_rsa_encrypt_encrypts_with_rsa_public_key() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")

    ciphertext = rsa_encrypt(public_key_pem, "test-password")

    assert private_key.decrypt(
        base64.b64decode(ciphertext), padding.PKCS1v15()
    ) == b"test-password"


def test_rsa_encrypt_rejects_non_rsa_public_key() -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")

    with pytest.raises(ValueError, match="不是 RSA 公钥"):
        rsa_encrypt(public_key_pem, "test-password")
