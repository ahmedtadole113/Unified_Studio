"""AIOps, FAISS Playbooks, Gemini Copilot, SSDLC & SRE Curriculum Router (`/api/v1/aiops`, `/api/ai/copilot`)."""

from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core import database, security
from services import aiops_engine
from sre_content import curriculum_roadmap, devops_cheatsheet

router = APIRouter(tags=["AIOps & SRE Copilot"])


class CopilotRequest(BaseModel):
    service: str = "platform"
    action: str = "general"
    content: str
    api_key: Optional[str] = None


class PlaybookQueryRequest(BaseModel):
    text: str


class StudyProgressRequest(BaseModel):
    completed: bool
    notes: str = ""


class SsdlcGateUpdateRequest(BaseModel):
    status: str
    evidence: str


@router.get("/api/v1/aiops/overview")
async def aiops_overview(user: Dict[str, str] = Depends(security.get_current_user)):
    return await aiops_engine.get_aiops_insights()


@router.post("/api/v1/aiops/playbooks/search")
def search_playbooks(req: PlaybookQueryRequest, user: Dict[str, str] = Depends(security.get_current_user)):
    matches = aiops_engine.kb.search(req.text, top_k=3)
    return {"query": req.text, "matches": matches, "best": matches[0] if matches else {}}


@router.get("/api/v1/aiops/playbooks")
def list_playbooks(user: Dict[str, str] = Depends(security.get_current_user)):
    return {"playbooks": aiops_engine.PLAYBOOKS}


@router.post("/api/v1/aiops/copilot")
@router.post("/api/ai/copilot")
async def unified_copilot(req: CopilotRequest, user: Dict[str, str] = Depends(security.get_current_user)):
    return await aiops_engine.ask_copilot(
        prompt=req.content,
        mode=req.action,
        service=req.service,
        api_key=req.api_key,
    )


@router.get("/api/v1/aiops/ssdlc")
def get_ssdlc_gates(user: Dict[str, str] = Depends(security.get_current_user)):
    return {"gates": database.get_ssdlc_gates()}


@router.put("/api/v1/aiops/ssdlc/{gate_id}")
def update_ssdlc_gate(gate_id: str, req: SsdlcGateUpdateRequest, admin: Dict[str, str] = Depends(security.require_admin)):
    updated = database.update_ssdlc_gate(gate_id, req.status, req.evidence)
    if not updated:
        raise HTTPException(status_code=404, detail="SSDLC gate not found")
    return updated


@router.get("/api/v1/aiops/roadmap")
def get_sre_roadmap(user: Dict[str, str] = Depends(security.get_current_user)):
    return {
        "phases": curriculum_roadmap.PHASES,
        "study_structure": curriculum_roadmap.STUDY_STRUCTURE,
        "days": curriculum_roadmap.ROADMAP_DAYS,
        "progress": database.get_study_progress(),
    }


@router.put("/api/v1/aiops/roadmap/{day}/progress")
def update_roadmap_progress(day: int, req: StudyProgressRequest, user: Dict[str, str] = Depends(security.get_current_user)):
    if day < 1 or day > 45:
        raise HTTPException(status_code=400, detail="Day must be between 1 and 45")
    return database.upsert_study_progress(day, req.completed, req.notes)


@router.get("/api/v1/aiops/cheatsheet")
def get_devops_cheatsheet(user: Dict[str, str] = Depends(security.get_current_user)):
    return {"modules": devops_cheatsheet.CHEATSHEET_MODULES}

