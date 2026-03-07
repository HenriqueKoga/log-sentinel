"""Tests for JWT encoder (encode/decode)."""

from __future__ import annotations

from datetime import timedelta

import jwt
import pytest

from logs_sentinel.infrastructure.auth.jwt import JWTEncoderImpl

_SECRET_32 = "test-secret-32-bytes-long!!!!!!!!"


def test_jwt_encode_decode_roundtrip() -> None:
    encoder = JWTEncoderImpl(secret_key=_SECRET_32, algorithm="HS256")
    payload = {"sub": "1", "tenant_id": 2, "role": "owner", "type": "access"}
    token = encoder.encode(payload, expires_delta=timedelta(minutes=5))
    assert isinstance(token, str)
    decoded = encoder.decode(token)
    assert decoded["sub"] == "1"
    assert decoded["tenant_id"] == 2
    assert decoded["role"] == "owner"
    assert "exp" in decoded


def test_jwt_decode_invalid_raises() -> None:
    encoder = JWTEncoderImpl(secret_key=_SECRET_32, algorithm="HS256")
    with pytest.raises(jwt.InvalidTokenError):
        encoder.decode("invalid-token")


def test_jwt_decode_wrong_secret_raises() -> None:
    encoder = JWTEncoderImpl(secret_key=_SECRET_32, algorithm="HS256")
    token = encoder.encode({"sub": "1"}, expires_delta=timedelta(minutes=5))
    other = JWTEncoderImpl(secret_key="other-secret-32-bytes-long!!!!!!!!!", algorithm="HS256")
    with pytest.raises(jwt.InvalidTokenError):
        other.decode(token)
