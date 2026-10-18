from config_loader import get_candidate_profile


def build_candidate_profile_text() -> str:
    """Construct formatted candidate profile text from config."""
    profile = get_candidate_profile()

    name = profile.get("name", "")
    current_role = profile.get("current_role", "")
    previous_role = profile.get("previous_role", "")
    experience = profile.get("experience_summary", "")
    education = profile.get("education", "")

    skills = profile.get("technical_skills", [])
    skills_text = "\n".join(f"{i}. {skill}" for i, skill in enumerate(skills, start=1))

    projects = profile.get("projects", [])
    projects_text = "\n".join(f"{i}. {proj}" for i, proj in enumerate(projects, start=1))

    return f"""Name: {name}

Current Role: {current_role}
Previous Role: {previous_role}

Professional Experience:
{experience}

Education:
{education}

Technical Skills:

{skills_text}

Relevant Project Experience:

{projects_text}
"""


CANDIDATE_PROFILE = build_candidate_profile_text()
