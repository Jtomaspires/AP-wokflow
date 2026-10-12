"""Argon2 passwords and session tokens."""

import re

from app.auth.passwords import hash_password, needs_rehash, verify_password
from app.auth.tokens import new_token, token_hash


def test_hash_is_not_the_plain_password():
    hashed = hash_password("secret")
    assert hashed != "secret"
    assert hashed.startswith("$argon2")


def test_verify_password():
    hashed = hash_password("secret")
    assert verify_password(hashed, "secret") is True
    assert verify_password(hashed, "wrong") is False


def test_fresh_hash_does_not_need_rehash():
    assert needs_rehash(hash_password("secret")) is False


def test_tokens_differ():
    assert new_token() != new_token()


def test_token_hash_is_sha256_hex():
    digest = token_hash(new_token())
    assert re.fullmatch(r"[0-9a-f]{64}", digest)
    assert token_hash("abc") == token_hash("abc")
