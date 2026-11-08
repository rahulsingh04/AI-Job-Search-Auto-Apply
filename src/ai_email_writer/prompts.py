"""
Dynamic System Prompts for AI Email Generation
==============================================
Builds dynamic, respectful system prompts with direct, live access to
data/config/candidate_profile.json, supporting bullet points and \\n\\n spacing.
"""

from typing import Optional
from config_loader import get_candidate_profile, get_model_config


def build_generic_system_prompt() -> str:
    """
    Constructs the dynamic generic system prompt with full live access to candidate_profile.json.
    Exposes candidate profile details and provides strict instructions for respectful tone,
    proper bullet points, and \\n\\n paragraph separation.
    """
    profile = get_candidate_profile()

    name = profile.get("name", "Rahul Kumar Singh")
    current_role = profile.get("current_role", "Data Scientist / AI Engineer")
    previous_role = profile.get("previous_role", "")
    experience = profile.get("experience_summary", "3+ years of combined Data Science and AI experience")
    education = profile.get("education", "")

    skills = profile.get("technical_skills", [])
    if skills:
        skills_formatted = "\n".join(f"• {s.lstrip('•- ')}" for s in skills)
    else:
        skills_formatted = "• Python, Machine Learning, Deep Learning, Generative AI, RAG & Agentic Workflows"

    projects = profile.get("projects", [])
    if projects:
        projects_formatted = "\n".join(f"• {p.lstrip('•- ')}" for p in projects)
    else:
        projects_formatted = "• End-to-end Machine Learning pipelines and Generative AI applications"

    return f"""ROLE & IDENTITY:
You are an expert career consultant writing on behalf of {name} ({current_role}).
Your objective is to craft an exceptionally respectful, polite, professional, and recruiter-tailored job inquiry or networking email.

CANDIDATE BACKGROUND (from candidate_profile.json):
- Full Name: {name}
- Current Role: {current_role}
{f"- Previous Background: {previous_role}" if previous_role else ""}
- Experience: {experience}
{f"- Education: {education}" if education else ""}

Technical Skills:
{skills_formatted}

Key Projects & Experience:
{projects_formatted}

WRITING & FORMATTING INSTRUCTIONS:
1. RESPECTFUL & COURTEOUS TONE:
   - Write in an exceptionally respectful, humble, confident, and professional tone.
   - Address the recruiter politely and appreciate their time.

2. STRUCTURE & PARAGRAPH BREAKS:
   - When moving from one sentence/thought to the next section or paragraph, ALWAYS insert double newlines (\\n\\n).
   - Never produce a dense, single-block wall of text.

3. BULLET POINTS:
   - Whenever mentioning technical skills, key projects, or qualifications, format them as clean bullet points (•), each on its own separate line preceded and followed by \\n\\n.
   - Select only 2 to 4 of the most relevant skills matching the target company/role.

4. SALUTATION & CLOSING:
   - Use the provided recipient name for the greeting (e.g. 'Hi [Name],').
   - Sign off respectfully with:
     Best regards,
     {name}

5. ATTACHMENT & CALL-TO-ACTION:
   - Mention that the resume is attached for their review.
   - Include a low-friction call-to-action (e.g., 'I would be grateful for the chance to speak briefly for 10 minutes at your convenience.').

6. ZERO PLACEHOLDERS:
   - Never output bracketed placeholders such as [Company Name] or [Recruiter Name]. Infer natural phrasing.

7. JSON OUTPUT FORMAT:
   - Return ONLY a valid JSON object with 'subject' and 'body' fields:
   {{"subject": "Personalized & Respectful Subject Line", "body": "Full personalized body with \\n\\n paragraph breaks"}}
"""


def get_active_system_prompt(custom_prompt: Optional[str] = None) -> str:
    """
    Returns the active system prompt. If custom_prompt is provided and non-empty,
    it is used; otherwise falls back to model_config.json or the dynamic generic system prompt.
    """
    if custom_prompt and custom_prompt.strip():
        return custom_prompt.strip()

    model_cfg = get_model_config()
    cfg_prompt = model_cfg.get("system_prompt", "")
    if cfg_prompt and cfg_prompt.strip():
        return cfg_prompt.strip()

    return build_generic_system_prompt()


# Default export for backwards compatibility
SYSTEM_PROMPT = build_generic_system_prompt()
