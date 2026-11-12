"""Audit logging helpers for RBAC and infrastructure operations."""

from typing import Any, Dict, List

from core import database


def record_audit(user: Dict[str, str], action: str, resource: str, detail: str, status: str = "success") -> None:
    database.insert_audit_log(
        username=user.get("username", "system"),
        role=user.get("role", "system"),
        action=action,
        resource=resource,
        detail=detail,
        status=status,
    )


def list_audits(limit: int = 100) -> List[Dict[str, Any]]:
    return database.get_audit_logs(limit=limit)

