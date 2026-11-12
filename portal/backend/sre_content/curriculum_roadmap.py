"""45-Day SRE Roadmap (Phases 1-10) with deep theory, examples, scenarios, live /lab commands & interview sims."""

from typing import Dict, List

from sre_content.roadmap_phases.phase1_linux_a import DAYS_1_TO_5
from sre_content.roadmap_phases.phase1_linux_b import DAYS_6_TO_10
from sre_content.roadmap_phases.phase2_networking import DAYS_11_TO_15
from sre_content.roadmap_phases.phase3_git import DAYS_16_TO_18
from sre_content.roadmap_phases.phase4_docker import DAYS_19_TO_22
from sre_content.roadmap_phases.phase5_k8s_a import DAYS_23_TO_26
from sre_content.roadmap_phases.phase5_k8s_b import DAYS_27_TO_29
from sre_content.roadmap_phases.phase6_cicd import DAYS_30_TO_33
from sre_content.roadmap_phases.phase7_terraform import DAYS_34_TO_36
from sre_content.roadmap_phases.phase8_monitoring import DAYS_37_TO_39
from sre_content.roadmap_phases.phase9_logging import DAYS_40_TO_41
from sre_content.roadmap_phases.phase10_scenarios import DAYS_42_TO_45

PHASES: List[Dict] = [
    {"id": 1, "days": "1-10", "title": "Phase 1: Linux (Basic -> Advanced)", "goal": "Strong OS foundation"},
    {"id": 2, "days": "11-15", "title": "Phase 2: Networking", "goal": "Understand infrastructure"},
    {"id": 3, "days": "16-18", "title": "Phase 3: Git & GitHub", "goal": "Version Control"},
    {"id": 4, "days": "19-22", "title": "Phase 4: Docker", "goal": "Containerization"},
    {"id": 5, "days": "23-29", "title": "Phase 5: Kubernetes", "goal": "Container Orchestration"},
    {"id": 6, "days": "30-33", "title": "Phase 6: Jenkins & CI/CD", "goal": "CI/CD"},
    {"id": 7, "days": "34-36", "title": "Phase 7: Terraform & IaC", "goal": "Infrastructure as Code"},
    {"id": 8, "days": "37-39", "title": "Phase 8: Prometheus + Grafana", "goal": "Monitoring"},
    {"id": 9, "days": "40-41", "title": "Phase 9: Splunk & Logging", "goal": "Logging"},
    {"id": 10, "days": "42-45", "title": "Phase 10: Production Scenarios + Interview", "goal": "Real-world SRE"},
]

STUDY_STRUCTURE: List[Dict[str, str]] = [
    {"duration": "60 min", "activity": "Theory & internal architecture"},
    {"duration": "60 min", "activity": "Hands-on lab & executable commands in /lab"},
    {"duration": "30 min", "activity": "Real production scenarios & troubleshooting"},
    {"duration": "45 min", "activity": "4-year SRE interview Q&A + simulation"},
    {"duration": "15 min", "activity": "Assignment checklist & revision notes"},
]

ROADMAP_DAYS: List[Dict] = sorted(
    [
        *DAYS_1_TO_5,
        *DAYS_6_TO_10,
        *DAYS_11_TO_15,
        *DAYS_16_TO_18,
        *DAYS_19_TO_22,
        *DAYS_23_TO_26,
        *DAYS_27_TO_29,
        *DAYS_30_TO_33,
        *DAYS_34_TO_36,
        *DAYS_37_TO_39,
        *DAYS_40_TO_41,
        *DAYS_42_TO_45,
    ],
    key=lambda d: d["day"],
)
