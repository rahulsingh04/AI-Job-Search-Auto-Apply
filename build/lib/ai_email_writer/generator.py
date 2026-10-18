from pydantic import ValidationError
from langchain_core.messages import SystemMessage, HumanMessage

from .schemas import EmailResponse
from .prompts import SYSTEM_PROMPT
from .recipient import infer_recipient_name
from .formatter import format_email_body
from .model import structured_llm


# =========================================================
# 1. Validate generated email
# =========================================================

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

    if len(text) > 2500:
        return True

    return False


# =========================================================
# 2. Generate a professional email
# =========================================================

def generate_professional_email(
    recipient_email: str,
    general_subject: str,
    general_body: str
) -> EmailResponse:
    """
    Rewrite an email using the local Ollama model.

    Returns:
        EmailResponse containing only the formatted email body.
    """

    # Validate inputs
    if not recipient_email or not recipient_email.strip():
        raise ValueError("Recipient email cannot be empty.")

    if not general_subject or not general_subject.strip():
        raise ValueError("General subject cannot be empty.")

    if not general_body or not general_body.strip():
        raise ValueError("General body cannot be empty.")

    # Detect recipient name, if recognizable
    recipient_name = infer_recipient_name(recipient_email)

    recipient_name_context = (
        recipient_name
        if recipient_name
        else "Not identifiable; use a generic greeting"
    )

    user_prompt = f"""
Rewrite the original email professionally.

RECIPIENT EMAIL (context only):
{recipient_email}

RECIPIENT NAME:
{recipient_name_context}

ORIGINAL SUBJECT (context only):
{general_subject}

ORIGINAL EMAIL BODY:
{general_body}

INSTRUCTIONS:
- Preserve the original purpose and intent.
- Use the candidate profile only when relevant.
- Do not copy the entire profile into the email.
- Do not generate a subject.
- Do not include an opening greeting; Python adds it.
- Include only relevant skills.
- Format relevant technical skills as numbered points,
  one point per line, when appropriate.
- Do not invent achievements or claim an attachment exists
  unless the original body explicitly mentions one.
- Return valid JSON with exactly one key: "body".
"""

    last_error = None
    last_raw_output = ""

    # Retry once if output is invalid
    for attempt in range(2):

        current_prompt = user_prompt

        if attempt == 1:
            current_prompt += """

CORRECTION:
The previous response did not satisfy the requirements.
Return a concise, complete email message and closing.
Do not copy the candidate profile or system instructions.
Do not add a greeting or subject.
Use numbered skill points on separate lines when relevant.
Return JSON containing only the "body" field.
"""

        response = structured_llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=current_prompt),
        ])

        raw_message = response.get("raw")
        last_raw_output = (
            str(raw_message.content)
            if raw_message is not None
            else ""
        )

        # JSON/Pydantic parsing failed
        if response.get("parsing_error") is not None:
            last_error = (
                "JSON/Pydantic parsing failed: "
                f"{response['parsing_error']}"
            )
            continue

        result = response.get("parsed")

        try:
            if isinstance(result, dict):
                result = EmailResponse.model_validate(result)

            if not isinstance(result, EmailResponse):
                raise ValueError(
                    "The model did not return an EmailResponse."
                )

        except (ValidationError, ValueError) as exc:
            last_error = str(exc)
            continue

        # Reject copied profiles and incomplete output
        if is_invalid_email(result.body):
            last_error = (
                "The model copied profile information or "
                "returned an unexpectedly long response."
            )
            continue

        # Correct greeting and format line breaks
        formatted_body = format_email_body(
            body_text=result.body,
            recipient_name=recipient_name,
        )

        return EmailResponse(body=formatted_body)

    raise ValueError(
        "Could not generate a valid email after two attempts.\n"
        f"Last issue: {last_error}\n"
        f"Last raw response excerpt:\n{last_raw_output[:1000]}"
    )
