"""Session tokens: the cookie holds the raw token, Postgres only its SHA-256."""

import hashlib
import secrets


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
