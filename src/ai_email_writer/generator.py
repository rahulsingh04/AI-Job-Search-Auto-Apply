"""
Email Generator with LLM Personalization and Fallback
=====================================================
Orchestrates AI rewriting using local Ollama models, enforces salutation,
bullet points, and \\n\\n spacing, and handles graceful fallback when no LLM is detected.
"""

from typing import Optional
from pydantic import ValidationError

try:
    from langchain_core.messages import SystemMessage, HumanMessage
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
from .formatter import format_email_body, enforce_correct_greeting
from .validator import email_validator, ValidationReport


class LLMUnavailableError(Exception):
    """Raised when Ollama server is offline or unreachable."""
    pass


class IncompleteEmailError(Exception):
    """Raised when generated email is incomplete or fails quality validation."""
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

    marker_count = sum(marker in text for marker in profile_markers)

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
    If the LLM server is unreachable, raises LLMUnavailableError so the caller can switch to fallback.

    Returns:
        EmailResponse containing the tailored subject (if generated) and formatted body.
    """
    if not recipient_email or not recipient_email.strip():
        raise ValueError("Recipient email cannot be empty.")

    if not general_subject or not general_subject.strip():
        raise ValueError("General subject cannot be empty.")

    if not general_body or not general_body.strip():
        raise ValueError("General body cannot be empty.")

    recipient_name = infer_recipient_name(recipient_email)
    recipient_name_context = recipient_name if recipient_name else "Not identifiable; use a polite general greeting"

    active_prompt = get_active_system_prompt(system_prompt)

    user_prompt = f"""
Please rewrite the following email for the recipient respectfully and professionally.

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
- When transitioning from one thought/sentence to the next paragraph, use double newlines (\\n\\n).
- Present key skills or achievements as bullet points (•) on separate lines with \\n\\n spacing.
- Mention the attached resume.
- Sign off respectfully.
- Return ONLY valid JSON with 'subject' and 'body' fields.
"""

    if not LANGCHAIN_AVAILABLE or structured_llm is None or SystemMessage is None or HumanMessage is None:
        raise LLMUnavailableError("No LLM detected (LangChain/Ollama libraries not initialized). Switching to generic body.")

    last_error = None
    last_raw_output = ""


    for attempt in range(2):
        current_prompt = user_prompt
        if attempt == 1:
            current_prompt += """

CORRECTION:
The previous response did not satisfy requirements.
Ensure respectful tone, double newlines (\\n\\n) between sections, and clean bullet points (•).
Return ONLY JSON with 'subject' and 'body'.
"""

        try:
            response = structured_llm.invoke([
                SystemMessage(content=active_prompt),
                HumanMessage(content=current_prompt),
            ])
        except Exception as exc:
            # Detect connection or server unavailable errors
            err_str = str(exc).lower()
            if any(term in err_str for term in ["connect", "refused", "unavailable", "timeout", "offline", "not found"]):
                raise LLMUnavailableError(f"No LLM detected or Ollama server connection failed: {exc}") from exc
            raise

        raw_message = response.get("raw")
        last_raw_output = str(raw_message.content) if raw_message is not None else ""

        if response.get("parsing_error") is not None:
            last_error = f"JSON/Pydantic parsing failed: {response['parsing_error']}"
            continue

        result = response.get("parsed")

        try:
            if isinstance(result, dict):
                result = EmailResponse.model_validate(result)

            if not isinstance(result, EmailResponse):
                raise ValueError("The model did not return a valid EmailResponse.")

        except (ValidationError, ValueError) as exc:
            last_error = str(exc)
            continue

        if is_invalid_email(result.body):
            last_error = "The model copied profile info or returned an overly long response."
            continue

        # Format greeting, spacing, and ensure signature
        formatted_body = format_email_body(
            body_text=result.body,
            recipient_name=recipient_name,
        )

        final_subject = result.subject.strip() if (result.subject and result.subject.strip()) else general_subject

        # Validate completeness with email_validator
        val_report = email_validator.validate(formatted_body, recipient_name=recipient_name)
        if not val_report.is_valid:
            last_error = f"Incomplete email defects: {'; '.join(val_report.issues)}"
            if attempt == 0:
                current_prompt += f"\n\n{val_report.feedback}"
            continue

        return EmailResponse(
            subject=final_subject,
            body=formatted_body,
        )

    # If retry attempts exhausted without producing a complete email, raise IncompleteEmailError
    raise IncompleteEmailError(f"AI generated an incomplete email ({last_error}).")


def build_fallback_email(
    recipient_email: str,
    general_subject: str,
    general_body: str,
) -> EmailResponse:
    """
    Builds the formatted fallback email using the static/generic body
    with correct recipient greeting, complete closing, and double newline paragraph breaks.
    """
    recipient_name = infer_recipient_name(recipient_email)
    formatted = format_email_body(general_body, recipient_name)
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
    Safely generates outreach email for a recipient:
    1. Attempts AI personalization with local LLM.
    2. If LLM is offline, times out, throws errors, or produces incomplete output,
       it automatically falls back to the formatted generic/static body.

    Returns:
        tuple of (EmailResponse, used_llm: bool, status_reason: str)
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
        fallback = build_fallback_email(recipient_email, general_subject, general_body)
        return fallback, False, f"LLM offline or unreachable ({err}). Using generic body fallback."
    except IncompleteEmailError as err:
        fallback = build_fallback_email(recipient_email, general_subject, general_body)
        return fallback, False, f"Incomplete AI generation ({err}). Using generic body fallback."
    except Exception as err:
        fallback = build_fallback_email(recipient_email, general_subject, general_body)
        return fallback, False, f"AI generation error ({err}). Using generic body fallback."


