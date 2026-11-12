"""Authentication & RBAC User Management Router (`/api/auth` and `/api/v1/auth`)."""

from typing import Dict
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core import audit, security
from core.config import settings

router = APIRouter(tags=["Authentication & RBAC"])


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: str = "user"


def _login_impl(req: LoginRequest) -> Dict:
    users = security.load_users()
    u = req.username.strip()
    p = req.password.strip()

    if u in users and security.verify_password(p, users[u].get("password", "")):
        role = users[u]["role"]
        token = security.create_access_token(u, role)
        audit.record_audit({"username": u, "role": role}, "auth.login", f"user:{u}", "User signed in")
        return {
            "status": "success",
            "username": u,
            "role": role,
            "access_token": token,
            "token_type": "bearer",
            "expires_in": settings.TOKEN_TTL_SECONDS,
        }

    audit.record_audit({"username": u or "anonymous", "role": "none"}, "auth.login", f"user:{u}", "Invalid credentials", status="denied")
    raise HTTPException(status_code=401, detail="Invalid username or password")


@router.post("/api/auth/login")
@router.post("/api/v1/auth/login")
def login(req: LoginRequest):
    return _login_impl(req)


@router.get("/api/v1/auth/me")
def whoami(user: Dict[str, str] = Depends(security.get_current_user)):
    return user


@router.get("/api/auth/users")
@router.get("/api/v1/auth/users")
def list_users(admin: Dict[str, str] = Depends(security.require_admin)):
    users = security.load_users()
    return [{"username": uname, "role": info["role"], "hashed": str(info.get("password", "")).startswith("pbkdf2_sha256$")} for uname, info in users.items()]


@router.post("/api/auth/users")
@router.post("/api/v1/auth/users")
def create_user(req: UserCreateRequest, admin: Dict[str, str] = Depends(security.require_admin)):
    users = security.load_users()
    non_admin_users = [u for u, info in users.items() if info["role"] != "admin"]
    if req.role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'user'")
    if req.role != "admin" and len(non_admin_users) >= 20:
        raise HTTPException(status_code=400, detail="Limit of 20 limited access users reached")

    u = req.username.strip()
    if not u or len(req.password.strip()) < 4:
        raise HTTPException(status_code=400, detail="Username required and password must be at least 4 characters")
    if u in users:
        raise HTTPException(status_code=400, detail="User already exists")

    users[u] = {"password": security.hash_password(req.password.strip()), "role": req.role}
    security.save_users(users)
    audit.record_audit(admin, "auth.create_user", f"user:{u}", f"Created user with role={req.role}")
    return {"status": "success", "message": f"User {u} created successfully"}


@router.delete("/api/auth/users/{username}")
@router.delete("/api/v1/auth/users/{username}")
def delete_user(username: str, admin: Dict[str, str] = Depends(security.require_admin)):
    users = security.load_users()
    u = username.strip()
    if u not in users:
        raise HTTPException(status_code=404, detail="User not found")
    if u in (settings.BOOTSTRAP_ADMIN_USER, settings.BOOTSTRAP_ADMIN_ALIAS):
        raise HTTPException(status_code=400, detail="Cannot delete bootstrap admin users")
    del users[u]
    security.save_users(users)
    audit.record_audit(admin, "auth.delete_user", f"user:{u}", "Deleted user")
    return {"status": "success", "message": f"User {u} deleted successfully"}

