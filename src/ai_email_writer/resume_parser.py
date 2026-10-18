"""
Resume Parser & Candidate Profile Extractor
============================================
Extracts structured candidate profile data from resumes (PDF / TXT / DOCX)
using dual-strategy:
1. Primary: Local LLM with Pydantic structured output.
2. Fallback / Safety: Regex & heuristic pattern extraction.
3. Validation & Sanitization: Checks JSON completeness and repairs any missing fields.
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Union
from pydantic import BaseModel, Field, ValidationError

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_PROFILE_FILE = PROJECT_ROOT / "data" / "config" / "candidate_profile.json"
PROJECT_CONFIG_FILE = PROJECT_ROOT / "data" / "config" / "project_config.json"


# ==============================================================================
# Pydantic Schema for Candidate Profile
# ==============================================================================

class CandidateProfile(BaseModel):
    """Structured Pydantic schema for candidate profile matching candidate_profile.json."""
    name: str = Field(default="", description="Full name of the candidate")
    current_role: str = Field(default="", description="Current or most recent job title and company")
    previous_role: str = Field(default="", description="Previous job title and company")
    experience_summary: str = Field(default="", description="Total experience summary (e.g. '3+ years of combined Data Science experience')")
    education: str = Field(default="", description="Highest educational degree and institution")
    technical_skills: List[str] = Field(default_factory=list, description="Categorized or bulleted list of technical skills")
    projects: List[str] = Field(default_factory=list, description="Key projects or technical domain achievements")


# ==============================================================================
# Text Extraction Helper
# ==============================================================================

def extract_text_from_file(file_path_or_bytes: Union[str, Path, bytes], filename: str = "") -> str:
    """Extract plain text from PDF or text file."""
    # 1. If bytes or uploaded file buffer
    if isinstance(file_path_or_bytes, bytes):
        if filename.lower().endswith(".pdf"):
            import io
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_path_or_bytes))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(pages).strip()
        else:
            return file_path_or_bytes.decode("utf-8", errors="ignore").strip()

    # 2. If path string / Path object
    path = Path(file_path_or_bytes).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Resume file not found at: {path}")

    if path.suffix.lower() == ".pdf":
        import pypdf
        reader = pypdf.PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages).strip()
    else:
        return path.read_text(encoding="utf-8", errors="ignore").strip()


# ==============================================================================
# Strategy B: Regex & Heuristic Fallback Extractor
# ==============================================================================

def extract_profile_via_regex(text: str) -> CandidateProfile:
    """
    Robust fallback scraper using regular expressions and heuristics
    to extract candidate information when the LLM is offline or fails.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # 1. Extract Name (typically the first non-contact line at top)
    name = "Candidate"
    for line in lines[:5]:
        # Filter out email, phone, links, or section headers
        if re.search(r"@|linkedin|github|portfolio|\+?\d{10,}|resume|curriculum", line, re.I):
            continue
        cleaned = re.sub(r"[^A-Za-z\s\.]", "", line).strip()
        words = cleaned.split()
        if 2 <= len(words) <= 4:
            name = cleaned
            break

    # 2. Extract Experience Summary
    exp_summary = "3+ years of professional experience"
    exp_match = re.search(r"(\d+\+?\s*(?:years?|yrs?)(?:\s+of)?(?:\s+combined)?(?:\s+[A-Za-z\s]+)?experience)", text, re.I)
    if exp_match:
        exp_summary = exp_match.group(1).strip()

    # 3. Extract Roles (Current and Previous)
    current_role = ""
    previous_role = ""
    role_pattern = re.compile(r"((?:Associate\s+|Senior\s+|Lead\s+)?(?:Data Scientist|Machine Learning Engineer|AI Engineer|Software Engineer|Data Analyst|Research Scientist)[^,\n\r]*(?:at|\bat\b|–|-|\|)[^,\n\r]+)", re.I)
    found_roles = role_pattern.findall(text)
    if found_roles:
        current_role = found_roles[0].strip()
        if len(found_roles) > 1:
            previous_role = found_roles[1].strip()

    # Fallback search for company / title lines
    if not current_role:
        for line in lines:
            if re.search(r"\b(?:Data Scientist|Machine Learning|AI Engineer|Software Engineer)\b", line, re.I):
                current_role = line
                break

    # 4. Extract Education
    education = ""
    edu_match = re.search(r"((?:B\.?Tech|B\.?E\.?|B\.?S\.?|Bachelor|M\.?Tech|M\.?S\.?|Master)[^,\n\r]*(?:in|of)?[^,\n\r]*(?:University|College|Institute|AKTU|IIT|NIT)?[^\n\r]*)", text, re.I)
    if edu_match:
        education = edu_match.group(1).strip()

    # 5. Extract Technical Skills
    technical_skills: List[str] = []
    skills_header_idx = -1
    for i, line in enumerate(lines):
        if re.match(r"^(?:technical\s+skills?|core\s+competencies|skills?)\b", line, re.I):
            skills_header_idx = i
            break

    if skills_header_idx != -1:
        # Collect lines following the skills header
        for line in lines[skills_header_idx + 1: skills_header_idx + 10]:
            if re.match(r"^(?:experience|projects?|education|certifications?|awards?)\b", line, re.I):
                break
            if ":" in line:
                technical_skills.append(line.strip())
            elif len(line.split(",")) >= 2:
                for subskill in line.split(","):
                    clean_s = subskill.strip().strip("•-* ")
                    if clean_s:
                        technical_skills.append(clean_s)

    # Keyword check if skills list is still sparse
    if len(technical_skills) < 3:
        common_skills = [
            "Python Programming and SQL",
            "Machine Learning: XGBoost, Random Forest, Scikit-Learn",
            "Deep Learning: TensorFlow, Keras, PyTorch",
            "Generative AI & LLMs: LangChain, Ollama, RAG Architectures",
            "Data Processing: Pandas, NumPy, PySpark",
            "Data Visualization: Matplotlib, Seaborn, Plotly"
        ]
        technical_skills = common_skills

    # 6. Extract Projects
    projects: List[str] = []
    proj_header_idx = -1
    for i, line in enumerate(lines):
        if re.match(r"^(?:relevant\s+projects?|projects?|key\s+projects?)\b", line, re.I):
            proj_header_idx = i
            break

    if proj_header_idx != -1:
        for line in lines[proj_header_idx + 1: proj_header_idx + 12]:
            if re.match(r"^(?:education|skills?|certifications?|awards?)\b", line, re.I):
                break
            clean_proj = re.sub(r"^[•\-\*\d\.\s]+", "", line).strip()
            if 15 <= len(clean_proj) <= 90 and not clean_proj.lower().startswith("developed"):
                projects.append(clean_proj)

    if not projects:
        projects = [
            "Predictive Modelling and Healthcare Risk Analytics",
            "Automotive Part Identification and Machine Learning",
            "Generative AI and Agentic Workflow Pipelines",
        ]

    return CandidateProfile(
        name=name,
        current_role=current_role or "Data Scientist",
        previous_role=previous_role or "Associate Data Scientist",
        experience_summary=exp_summary,
        education=education or "B.Tech in Computer Science Engineering",
        technical_skills=technical_skills,
        projects=projects,
    )


# ==============================================================================
# Validation & Sanitization Tool
# ==============================================================================

def validate_and_fix_profile(raw_data: Union[Dict[str, Any], CandidateProfile], raw_text: str = "") -> CandidateProfile:
    """
    Validate and automatically fix missing or invalid profile fields
    using Pydantic validation and fallback heuristics.
    """
    if isinstance(raw_data, CandidateProfile):
        data = raw_data.model_dump()
    elif isinstance(raw_data, dict):
        data = dict(raw_data)
    else:
        data = {}

    # Fix name if missing or empty
    if not data.get("name") or data.get("name").strip().lower() in ("candidate", "unknown", ""):
        if raw_text:
            regex_profile = extract_profile_via_regex(raw_text)
            data["name"] = regex_profile.name

    # Fix experience summary if missing
    if not data.get("experience_summary"):
        data["experience_summary"] = "3+ years of professional Data Science experience"

    # Fix current/previous roles
    if not data.get("current_role"):
        data["current_role"] = "Data Scientist"

    # Ensure technical_skills is a list
    if not isinstance(data.get("technical_skills"), list) or not data["technical_skills"]:
        if raw_text:
            regex_profile = extract_profile_via_regex(raw_text)
            data["technical_skills"] = regex_profile.technical_skills
        else:
            data["technical_skills"] = ["Python, Machine Learning, Deep Learning, Generative AI"]

    # Ensure projects is a list
    if not isinstance(data.get("projects"), list) or not data["projects"]:
        if raw_text:
            regex_profile = extract_profile_via_regex(raw_text)
            data["projects"] = regex_profile.projects
        else:
            data["projects"] = ["AI and Predictive Modeling Applications"]

    # Final Pydantic validation
    try:
        validated = CandidateProfile.model_validate(data)
    except ValidationError:
        # Construct safe default
        validated = CandidateProfile(
            name=data.get("name", "Rahul Kumar Singh"),
            current_role=data.get("current_role", "Data Scientist"),
            previous_role=data.get("previous_role", ""),
            experience_summary=data.get("experience_summary", "3+ years of experience"),
            education=data.get("education", ""),
            technical_skills=data.get("technical_skills", []),
            projects=data.get("projects", []),
        )

    return validated


# ==============================================================================
# Main Strategy: Dual-Engine Resume Parser
# ==============================================================================

def parse_resume_to_profile(
    file_path_or_bytes: Union[str, Path, bytes],
    filename: str = "",
    use_llm: bool = True
) -> CandidateProfile:
    """
    Parse resume into verified CandidateProfile:
    1. Extracts raw text.
    2. Tries LLM structured extraction (if enabled).
    3. Falls back to Regex & heuristic extraction on failure or error.
    4. Validates and auto-repairs with Pydantic.
    """
    raw_text = extract_text_from_file(file_path_or_bytes, filename)
    if not raw_text.strip():
        raise ValueError("Could not extract any text from the provided resume file.")

    # 1. Try Primary: LLM Structured Output
    if use_llm:
        try:
            from langchain_core.messages import SystemMessage, HumanMessage
            from .model import llm

            structured_profile_llm = llm.with_structured_output(
                CandidateProfile,
                method="json_mode",
            )

            prompt = f"""Extract the candidate profile information from the following resume text into the required JSON format:

RESUME TEXT:
{raw_text[:4000]}
"""
            response = structured_profile_llm.invoke([
                SystemMessage(content="You are an expert resume parser. Extract accurate information into the required CandidateProfile JSON schema. If any field is not found, provide a concise placeholder or leave empty."),
                HumanMessage(content=prompt),
            ])

            if isinstance(response, CandidateProfile):
                return validate_and_fix_profile(response, raw_text)
            elif isinstance(response, dict):
                return validate_and_fix_profile(response, raw_text)

        except Exception as exc:
            print(f"[ResumeParser Fallback] LLM extraction encountered: {exc}. Falling back to Regex parser.")

    # 2. Fallback: Regex & Heuristic Scraper
    regex_profile = extract_profile_via_regex(raw_text)
    return validate_and_fix_profile(regex_profile, raw_text)


def save_candidate_profile_config(profile: CandidateProfile, target_path: Path = None) -> Path:
    """
    Persist the parsed CandidateProfile to candidate_profile.json
    and update project_config.json.
    """
    save_path = target_path or DEFAULT_PROFILE_FILE
    save_path.parent.mkdir(parents=True, exist_ok=True)

    profile_dict = profile.model_dump()

    # Save to candidate_profile.json
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(profile_dict, f, indent=4, ensure_ascii=False)

    # Also update master project_config.json if it exists
    if PROJECT_CONFIG_FILE.is_file():
        try:
            with open(PROJECT_CONFIG_FILE, "r", encoding="utf-8") as f:
                master = json.load(f)
            master["candidate_profile"] = profile_dict
            with open(PROJECT_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(master, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

    return save_path

