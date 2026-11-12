"""Centralized Authentication, PBKDF2 Password Hashing, Signed Bearer Tokens, and RBAC."""

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from typing import Any, Dict, Optional

from fastapi import Depends, Header, HTTPException, Request

from core.config import settings

logger = logging.getLogger("ues.security")

_PBKDF2_ITERS = 120_000


def hash_password(plain_password: str, salt: Optional[str] = None) -> str:
    """Hash a password with PBKDF2-HMAC-SHA256 and random 16-byte salt."""
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        plain_password.encode("utf-8"),
        salt.encode("utf-8"),
        _PBKDF2_ITERS,
    )
    return f"pbkdf2_sha256${_PBKDF2_ITERS}${salt}${base64.b64encode(dk).decode('ascii')}"


def verify_password(plain_password: str, stored_value: str) -> bool:
    """Verify plaintext password against PBKDF2 hash (with legacy plaintext migration support)."""
    if not stored_value:
        return False
    if stored_value.startswith("pbkdf2_sha256$"):
        try:
            _, iters_s, salt, b64_hash = stored_value.split("$", 3)
            dk = hashlib.pbkdf2_hmac(
                "sha256",
                plain_password.encode("utf-8"),
                salt.encode("utf-8"),
                int(iters_s),
            )
            candidate = base64.b64encode(dk).decode("ascii")
            return hmac.compare_digest(candidate, b64_hash)
        except Exception:
            return False
    return hmac.compare_digest(plain_password, stored_value)


def _resolve_users_path() -> str:
    preferred = settings.USERS_DB_PATH
    try:
        parent = os.path.dirname(preferred) or "."
        os.makedirs(parent, exist_ok=True)
        return preferred
    except OSError:
        return "/tmp/ues_users.json"


def _default_users_hashed() -> Dict[str, Dict[str, str]]:
    admin_user = settings.BOOTSTRAP_ADMIN_USER
    admin_alias = settings.BOOTSTRAP_ADMIN_ALIAS
    admin_pw = settings.BOOTSTRAP_ADMIN_PASSWORD
    users = {
        admin_user: {"password": hash_password(admin_pw), "role": "admin"},
    }
    if admin_alias and admin_alias != admin_user:
        users[admin_alias] = {"password": hash_password(admin_pw), "role": "admin"}
    return users


def load_users() -> Dict[str, Dict[str, Any]]:
    """Load users from disk and transparently upgrade any legacy plaintext passwords to PBKDF2."""
    path = _resolve_users_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            upgraded = False
            for uname, info in data.items():
                pw = info.get("password", "")
                if pw and not pw.startswith("pbkdf2_sha256$"):
                    info["password"] = hash_password(pw)
                    upgraded = True
            if upgraded:
                save_users(data)
            return data
        except Exception as exc:
            logger.error("Failed to load users from %s: %s", path, exc)

    users = _default_users_hashed()
    save_users(users)
    return users


def save_users(users: Dict[str, Dict[str, Any]]) -> None:
    path = _resolve_users_path()
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=4)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    except Exception as exc:
        logger.error("Failed to save users to %s: %s", path, exc)


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    padding = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + padding)


def create_access_token(username: str, role: str) -> str:
    """Create an HMAC-SHA256 signed JWT-compatible Bearer token."""
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode("utf-8"))
    now = int(time.time())
    payload = _b64url_encode(
        json.dumps(
            {
                "sub": username,
                "role": role,
                "iat": now,
                "exp": now + settings.TOKEN_TTL_SECONDS,
                "jti": secrets.token_hex(8),
            }
        ).encode("utf-8")
    )
    signing_input = f"{header}.{payload}".encode("utf-8")
    sig = hmac.new(settings.AUTH_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64url_encode(sig)}"


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        parts = token.strip().split(".")
        if len(parts) != 3:
            return None
        header_b, payload_b, sig_b = parts
        signing_input = f"{header_b}.{payload_b}".encode("utf-8")
        expected_sig = hmac.new(settings.AUTH_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(_b64url_encode(expected_sig), sig_b):
            return None
        payload = json.loads(_b64url_decode(payload_b).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_user_role: Optional[str] = Header(None),
) -> Dict[str, str]:
    """Extract and validate the authenticated user from Bearer token."""
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    elif request.query_params.get("token"):
        token = request.query_params.get("token", "").strip()

    if token:
        payload = decode_access_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid or expired session token")
        users = load_users()
        uname = payload.get("sub", "")
        if uname not in users:
            raise HTTPException(status_code=401, detail="User account no longer exists")
        return {"username": uname, "role": users[uname]["role"]}

    raise HTTPException(status_code=401, detail="Authentication required (Bearer token missing)")


def get_optional_user(
    authorization: Optional[str] = Header(None),
) -> Optional[Dict[str, str]]:
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        payload = decode_access_token(token)
        if payload:
            users = load_users()
            uname = payload.get("sub", "")
            if uname in users:
                return {"username": uname, "role": users[uname]["role"]}
    return None


def require_admin(user: Dict[str, str] = Depends(get_current_user)) -> Dict[str, str]:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required for this operation")
    return user


def mask_secret(value: str) -> str:
    if not value or len(value) < 6:
        return "******"
    return f"{value[:2]}***{value[-2:]}"

