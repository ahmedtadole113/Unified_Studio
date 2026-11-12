"""FinOps & Capacity Management Router (`/api/v1/finops`)."""

from typing import Dict

from fastapi import APIRouter, Depends

from core import security
from services import finops_engine

router = APIRouter(prefix="/api/v1/finops", tags=["FinOps & Capacity"])


@router.get("/overview")
def finops_overview(user: Dict[str, str] = Depends(security.get_current_user)):
    return finops_engine.get_finops_overview()

