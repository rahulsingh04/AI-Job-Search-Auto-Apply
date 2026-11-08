"""
Email Generator with LLM Personalization and Fallback
=====================================================
Orchestrates AI rewriting using local Ollama models, enforces salutation,
bullet points, and \\n\\n spacing, and handles graceful fallback when no
LLM is detected. Also provides template-only generation utilities.
"""

import random
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

try:
    from langchain_core.messages import (
        SystemMessage,
        HumanMessage,
    )
    from .model import structured_llm
    LANGCHAIN_AVAILABLE = True
except (ImportError, Exception):
    SystemMessage = None
    HumanMessage = None
    structured_llm = None
    LANGCHAIN_AVAILABLE = False

from .schemas import EmailResponse
from .prompts import get_active_system_prompt
from .recipient import infer_recipient_name
from .formatter import (
    format_email_body,
    enforce_correct_greeting,
)
from .validator import email_validator, ValidationReport

_TEMPLATE_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "template"
)


class LLMUnavailableError(Exception):
    """Raised when Ollama server is offline or unreachable."""
    pass


class IncompleteEmailError(Exception):
    """Raised when generated email fails quality validation."""
    pass


def is_invalid_email(body_text: str) -> bool:
    """Detect empty, oversized, or copied-profile responses."""
    text = body_text.strip().lower()

    if not text:
        return True

    profile_markers = [
        "current organization:",
        "previous organization:",
        "technical skills:",
        "relevant project experience:",
        "professional experience:",
        "education:",
    ]

    marker_count = sum(
        marker in text for marker in profile_markers
    )

    if marker_count >= 2:
        return True

    if len(text) > 3000:
        return True

    return False


def generate_professional_email(
    recipient_email: str,
    general_subject: str,
    general_body: str,
    system_prompt: Optional[str] = None,
) -> EmailResponse:
    """
    Rewrite an email using the local Ollama model.
    Raises LLMUnavailableError if server is unreachable.
    """
    if not recipient_email or not recipient_email.strip():
        raise ValueError(
            "Recipient email cannot be empty."
        )

    if not general_subject or not general_subject.strip():
        raise ValueError("General subject cannot be empty.")

    if not general_body or not general_body.strip():
        raise ValueError("General body cannot be empty.")

    recipient_name = infer_recipient_name(recipient_email)
    recipient_name_context = (
        recipient_name
        if recipient_name
        else (
            "Not identifiable; use a polite general greeting"
        )
    )

    active_prompt = get_active_system_prompt(system_prompt)

    user_prompt = f"""
Please rewrite the following email for the recipient \
respectfully and professionally.

RECIPIENT EMAIL:
{recipient_email}

RECIPIENT NAME:
{recipient_name_context}

ORIGINAL SUBJECT:
{general_subject}

ORIGINAL GENERIC BODY:
{general_body}

INSTRUCTIONS:
- Write in a highly respectful, humble, and polite tone.
- Use double newlines (\\n\\n) between paragraphs.
- Present key skills as bullet points (•).
- Mention the attached resume.
- Sign off respectfully.
- Return ONLY valid JSON with 'subject' and 'body' fields.
"""

    if (
        not LANGCHAIN_AVAILABLE
        or structured_llm is None
        or SystemMessage is None
        or HumanMessage is None
    ):
        raise LLMUnavailableError(
            "No LLM detected. Switching to generic body."
        )

    last_error = None

    for attempt in range(2):
        current_prompt = user_prompt
        if attempt == 1:
            current_prompt += """

CORRECTION:
The previous response did not satisfy requirements.
Ensure respectful tone, double newlines (\\n\\n) between
sections, and clean bullet points (•).
Return ONLY JSON with 'subject' and 'body'.
"""

        try:
            response = structured_llm.invoke([
                SystemMessage(content=active_prompt),
                HumanMessage(content=current_prompt),
            ])
        except Exception as exc:
            err_str = str(exc).lower()
            if any(
                term in err_str
                for term in [
                    "connect", "refused", "unavailable",
                    "timeout", "offline", "not found",
                ]
            ):
                raise LLMUnavailableError(
                    f"Ollama connection failed: {exc}"
                ) from exc
            raise

        raw_message = response.get("raw")
        _ = (
            str(raw_message.content)
            if raw_message is not None
            else ""
        )

        if response.get("parsing_error") is not None:
            last_error = (
                f"JSON/Pydantic parsing failed: "
                f"{response['parsing_error']}"
            )
            continue

        result = response.get("parsed")

        try:
            if isinstance(result, dict):
                result = EmailResponse.model_validate(
                    result
                )
            if not isinstance(result, EmailResponse):
                raise ValueError(
                    "Model did not return EmailResponse."
                )
        except (ValidationError, ValueError) as exc:
            last_error = str(exc)
            continue

        if is_invalid_email(result.body):
            last_error = (
                "Model copied profile info or returned "
                "an overly long response."
            )
            continue

        formatted_body = format_email_body(
            body_text=result.body,
            recipient_name=recipient_name,
        )

        final_subject = (
            result.subject.strip()
            if (result.subject and result.subject.strip())
            else general_subject
        )

        val_report = email_validator.validate(
            formatted_body,
            recipient_name=recipient_name,
        )
        if not val_report.is_valid:
            last_error = (
                f"Incomplete email defects: "
                f"{'; '.join(val_report.issues)}"
            )
            if attempt == 0:
                current_prompt += (
                    f"\n\n{val_report.feedback}"
                )
            continue

        return EmailResponse(
            subject=final_subject,
            body=formatted_body,
        )

    raise IncompleteEmailError(
        f"AI generated an incomplete email ({last_error})."
    )


def build_fallback_email(
    recipient_email: str,
    general_subject: str,
    general_body: str,
) -> EmailResponse:
    """
    Build formatted fallback email using static body.
    No LLM involved — pure string formatting.
    """
    recipient_name = infer_recipient_name(recipient_email)
    formatted = format_email_body(
        general_body, recipient_name
    )
    normalized = formatted.replace("\r\n", "\n")
    return EmailResponse(
        subject=general_subject,
        body=normalized,
    )


def generate_email_with_fallback(
    recipient_email: str,
    general_subject: str,
    general_body: str,
    system_prompt: Optional[str] = None,
) -> tuple[EmailResponse, bool, str]:
    """
    Safely generate outreach email with LLM fallback.
    Returns (EmailResponse, used_llm, status_reason).
    """
    try:
        res = generate_professional_email(
            recipient_email=recipient_email,
            general_subject=general_subject,
            general_body=general_body,
            system_prompt=system_prompt,
        )
        return res, True, "Personalized by AI for recipient"
    except LLMUnavailableError as err:
        fallback = build_fallback_email(
            recipient_email, general_subject, general_body
        )
        return (
            fallback,
            False,
            f"LLM offline ({err}). Using fallback.",
        )
    except IncompleteEmailError as err:
        fallback = build_fallback_email(
            recipient_email, general_subject, general_body
        )
        return (
            fallback,
            False,
            f"Incomplete AI generation ({err}). Fallback.",
        )
    except Exception as err:
        fallback = build_fallback_email(
            recipient_email, general_subject, general_body
        )
        return (
            fallback,
            False,
            f"AI generation error ({err}). Fallback.",
        )


# ---------------------------------------------------------------------------
# Template-only utilities (no LLM)
# ---------------------------------------------------------------------------

def get_available_templates() -> list[int]:
    """
    Dynamically read template folder.
    Returns sorted list of available template indices.
    Never hardcoded — reads from data/template/ folder.
    """
    if not _TEMPLATE_DIR.is_dir():
        return []
    indices = []
    for f in _TEMPLATE_DIR.glob("template*.txt"):
        stem = f.stem.replace("template", "")
        if stem.isdigit():
            indices.append(int(stem))
    return sorted(indices)


def get_template_sequence(
    count: int,
    template_cfg: dict,
) -> list[int]:
    """
    Generate template index sequence for N recipients.
    mode='fixed'  → all use fixed_template_index
    mode='random' → no two consecutive same template
    """
    mode = template_cfg.get("mode", "random")
    fixed_index = template_cfg.get("fixed_template_index")
    no_repeat = template_cfg.get(
        "no_consecutive_repeat", True
    )
    templates = get_available_templates()

    if not templates:
        return [1] * count

    if mode == "fixed" and fixed_index is not None:
        return [int(fixed_index)] * count

    sequence: list[int] = []
    last: int | None = None

    for _ in range(count):
        if no_repeat and last is not None:
            available = (
                [t for t in templates if t != last]
                or templates
            )
        else:
            available = templates

        chosen = random.choice(available)
        sequence.append(chosen)
        last = chosen

    return sequence


def fill_template(
    template_index: int,
    profile: dict,
    recipient_name: str,
) -> str:
    """
    Load template{n}.txt and fill all placeholders
    from candidate profile. No LLM — pure substitution.
    """
    template_file = (
        _TEMPLATE_DIR / f"template{template_index}.txt"
    )

    if not template_file.is_file():
        return ""

    content = template_file.read_text(encoding="utf-8")

    skills = profile.get("technical_skills", [])
    skills_str = (
        ", ".join(skills)
        if isinstance(skills, list)
        else str(skills)
    )

    projects = profile.get("projects", [])
    projects_str = (
        "\n• ".join(projects)
        if isinstance(projects, list)
        else str(projects)
    )

    replacements = {
        "{name}": recipient_name or "there",
        "{candidate_name}": profile.get("name", ""),
        "{current_role}": profile.get(
            "current_role", ""
        ),
        "{experience}": profile.get(
            "experience_summary", ""
        ),
        "{experience_summary}": profile.get(
            "experience_summary", ""
        ),
        "{technical_skills}": skills_str,
        "{key_skills}": skills_str,
        "{projects}": projects_str,
        "{education}": profile.get("education", ""),
        "{email}": profile.get("email", ""),
        "{phone}": profile.get("phone", ""),
        "{linkedin}": profile.get("linkedin_url", ""),
    }

    for placeholder, value in replacements.items():
        content = content.replace(
            placeholder, str(value)
        )

    return content
