"""Shared builders for 45-Day SRE Roadmap curriculum entries."""

from typing import Any, Dict, List, Optional

DEFAULT_STUDY_PLAN: List[Dict[str, str]] = [
    {"block": "Theory & Internals", "duration": "60 minutes"},
    {"block": "Command Practice (/lab)", "duration": "60 minutes"},
    {"block": "Production Scenarios", "duration": "30 minutes"},
    {"block": "Interview Preparation", "duration": "45 minutes"},
    {"block": "Assignment & Revision", "duration": "15 minutes"},
]


def qa(question: str, answer: str, level: str = "senior") -> Dict[str, str]:
    return {"q": question, "a": answer, "level": level}


def sec(
    title: str,
    explanation: str,
    *,
    bullets: Optional[List[str]] = None,
    table: Optional[Dict[str, Any]] = None,
    example: str = "",
    sre_example: str = "",
) -> Dict[str, Any]:
    return {
        "title": title,
        "explanation": explanation,
        "bullets": bullets or [],
        "table": table,
        "example": example,
        "sre_example": sre_example,
    }


def scenario(
    title: str,
    symptom: str,
    investigation: str,
    root_cause: str,
    resolution: str,
) -> Dict[str, str]:
    return {
        "title": title,
        "symptom": symptom,
        "investigation": investigation,
        "root_cause": root_cause,
        "resolution": resolution,
    }


def sim(prompt: str, hints: List[str]) -> Dict[str, Any]:
    return {"prompt": prompt, "hints": hints}


def make_day(
    day: int,
    phase: int,
    title: str,
    subtitle: str,
    goal: str,
    objective: str,
    concepts: List[str],
    deep_sections: List[Dict[str, Any]],
    architecture: str,
    commands: List[Dict[str, Any]],
    production_use_case: str,
    scenarios: List[Dict[str, str]],
    troubleshooting: List[str],
    interview_qa: List[Dict[str, str]],
    assignment_items: List[str],
    revision: List[str],
    interview_sim: List[Dict[str, Any]],
    study_plan: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    return {
        "day": day,
        "phase": phase,
        "title": title,
        "subtitle": subtitle,
        "goal": goal,
        "objective": objective,
        "study_plan": study_plan or DEFAULT_STUDY_PLAN,
        "concepts": concepts,
        "deep_sections": deep_sections,
        "architecture": architecture,
        "commands": commands,
        "production_use_case": production_use_case,
        "scenarios": scenarios,
        "troubleshooting": troubleshooting,
        "interview_qa": interview_qa,
        "assignment_items": assignment_items,
        "assignment": " | ".join(assignment_items[:3]) if assignment_items else goal,
        "revision": revision,
        "interview_sim": interview_sim,
    }

