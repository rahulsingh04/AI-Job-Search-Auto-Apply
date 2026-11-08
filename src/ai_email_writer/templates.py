"""
Resume-Based Email Template Generator
====================================
Loads 5 generic templates from data/template/ (or data/config/template/)
and renders them dynamically with candidate profile placeholders ({candidate_name}, {name},
{current_role}, {previous_role}, {experience}, {experience_summary}, {key_skills},
{technical_skills}, {project}, {projects}, {education}).
"""

import re
from pathlib import Path
from typing import List, Dict, Any, Union

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATE_DIR_PRIMARY = PROJECT_ROOT / "data" / "config" / "template"
TEMPLATE_DIR_FALLBACK = PROJECT_ROOT / "data" / "template"

TEMPLATE_METADATA = [
    {"id": 1, "name": "template1", "title": "template1", "description": "Comprehensive & Structured Application", "filename": "template1.txt"},
    {"id": 2, "name": "template2", "title": "template2", "description": "Concise & Direct Inquiry", "filename": "template2.txt"},
    {"id": 3, "name": "template3", "title": "template3", "description": "Value Proposition & Hands-on Projects", "filename": "template3.txt"},
    {"id": 4, "name": "template4", "title": "template4", "description": "Skills & Experience Highlight", "filename": "template4.txt"},
    {"id": 5, "name": "template5", "title": "template5", "description": "Professional Background & Value Summary", "filename": "template5.txt"},
]


def _clean_str(val: Any, default: str = "") -> str:
    if val is None:
        return default
    s = str(val).strip()
    return s if s else default


def _extract_short_role(role_str: str) -> str:
    """Extract a concise job role title from potentially verbose headings."""
    if not role_str:
        return "AI Engineer & Data Scientist"
    parts = re.split(r"[—\-\|/,]", role_str)
    cleaned_parts = [p.strip() for p in parts if p.strip()]
    if not cleaned_parts:
        return "AI Engineer & Data Scientist"
    if len(cleaned_parts) == 1:
        return cleaned_parts[0]
    return f"{cleaned_parts[0]} / {cleaned_parts[1]}"


def _clean_bullet(item: str) -> str:
    """Format string into a clean item without bullet prefixes."""
    s = re.sub(r"^[•\-\*\d\.\s]+", "", str(item)).strip()
    return s.rstrip(".,;:")


def get_template_file_content(template_name_or_idx: Union[str, int]) -> str:
    """Read the raw template file from data/template/ or data/config/template/."""
    if isinstance(template_name_or_idx, int):
        filename = f"template{template_name_or_idx}.txt"
    else:
        name = str(template_name_or_idx).strip()
        filename = f"{name}.txt" if not name.endswith(".txt") else name

    path_primary = TEMPLATE_DIR_PRIMARY / filename
    if path_primary.is_file():
        return path_primary.read_text(encoding="utf-8").strip()

    path_fallback = TEMPLATE_DIR_FALLBACK / filename
    if path_fallback.is_file():
        return path_fallback.read_text(encoding="utf-8").strip()

    return ""


def load_and_render_body_template(template_name_or_idx: Union[str, int], profile_data: Union[Dict[str, Any], Any]) -> str:
    """
    Load a template (template1 to template5) and fill all placeholders:
    {candidate_name}, {name}, {current_role}, {previous_role}, {experience},
    {experience_summary}, {education}, {key_skills}, {technical_skills}, {project}, {projects}.
    """
    content = get_template_file_content(template_name_or_idx)
    if not content:
        return ""

    if hasattr(profile_data, "model_dump"):
        data = profile_data.model_dump()
    elif isinstance(profile_data, dict):
        data = profile_data
    else:
        data = {}

    name = _clean_str(data.get("name"), "Rahul Singh")
    raw_role = _clean_str(data.get("current_role"), "AI Engineer / Data Scientist")
    prev_role = _clean_str(data.get("previous_role"), "Associate Data Scientist")
    exp = _clean_str(data.get("experience_summary"), "3+ years")
    edu = _clean_str(data.get("education"), "B.Tech / Science Degree")

    # Clean skills into comma-separated text
    raw_skills = data.get("technical_skills") or []
    if isinstance(raw_skills, str):
        raw_skills = [raw_skills]
    cleaned_skills = [_clean_bullet(s) for s in raw_skills if _clean_bullet(s)]
    if not cleaned_skills:
        cleaned_skills = ["Python", "Machine Learning", "Generative AI", "SQL"]
    skills_str = ", ".join(cleaned_skills[:5])

    # Clean projects into comma-separated text
    raw_projs = data.get("projects") or []
    if isinstance(raw_projs, str):
        raw_projs = [raw_projs]
    cleaned_projs = [_clean_bullet(p) for p in raw_projs if _clean_bullet(p)]
    if not cleaned_projs:
        cleaned_projs = ["AI Visualizer LLM Agent", "Predictive Healthcare Modeling"]
    projs_str = ", ".join(cleaned_projs[:3])

    replacements = {
        "{candidate_name}": name,
        "{name}": name,
        "{current_role}": raw_role,
        "{previous_role}": prev_role,
        "{experience}": exp,
        "{experience_summary}": exp,
        "{education}": edu,
        "{key_skills}": skills_str,
        "{technical_skills}": skills_str,
        "{project}": projs_str,
        "{projects}": projs_str,
    }

    # If the file had a Subject: line, extract body only
    if content.startswith("Subject:"):
        parts = content.split("\n\n", 1)
        content = parts[1].strip() if len(parts) > 1 else ""

    rendered = content
    for ph, val in replacements.items():
        rendered = rendered.replace(ph, str(val))

    return rendered


def generate_resume_templates(profile_data: Union[Dict[str, Any], Any]) -> List[Dict[str, str]]:
    """Generate all 5 rendered templates for backwards compatibility and tests."""
    templates = []
    if hasattr(profile_data, "model_dump"):
        data = profile_data.model_dump()
    elif isinstance(profile_data, dict):
        data = profile_data
    else:
        data = {}

    name = _clean_str(data.get("name"), "Rahul Singh")
    role = _clean_str(data.get("current_role"), "AI Engineer / Data Scientist")
    short_role = _extract_short_role(role)
    exp = _clean_str(data.get("experience_summary"), "3+ years")

    subject_formats = [
        f"Application for {short_role} - {name} ({exp})",
        f"Experienced {short_role} ({exp}) - {name}",
        f"Inquiry: {short_role} Opportunity - {name}",
        f"{name} - {short_role} Candidate ({exp})",
        f"Exploring {short_role} Roles - {name}",
    ]

    for idx, meta in enumerate(TEMPLATE_METADATA):
        t_id = meta["id"]
        t_name = meta["name"]
        body = load_and_render_body_template(t_name, data)
        subject = subject_formats[idx] if idx < len(subject_formats) else f"Application for {short_role} - {name}"

        templates.append({
            "id": t_id,
            "name": t_name,
            "title": t_name,
            "description": meta.get("description", t_name),
            "subject": subject,
            "body": body,
        })

    return templates
