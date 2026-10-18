"""
Batch Email Sending Pipeline with Streaming Event Generation
============================================================
Checks history, generates personalized body (with graceful LLM fallback),
dispatches emails, and yields streaming progress updates.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Generator, Dict, Any, List, Optional

from ai_email_writer.generator import (
    generate_professional_email,
    build_fallback_email,
    LLMUnavailableError,
)
from config_loader import get_email_config
from .date_utils import get_lookback_date
from .storage import load_email_storage
from .sender import send_email

_email_cfg = get_email_config()
LOOK_BACK = _email_cfg.get("look_back", 1)
LOOK_BACK_FORMAT = _email_cfg.get("look_back_format", "months")

EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$"
)


def was_recently_emailed(
    recipient_email: str,
    look_back: int = LOOK_BACK,
    look_back_format: str = LOOK_BACK_FORMAT,
) -> bool:
    """Check email history before invoking the LLM."""
    email_data = load_email_storage()

    normalized_data = {
        str(email).strip().lower(): sent_date
        for email, sent_date in email_data.items()
    }

    last_sent = normalized_data.get(recipient_email.strip().lower())
    if last_sent is None or not last_sent.strip() or last_sent.lower() == "never":
        return False

    try:
        last_sent_date = datetime.strptime(last_sent.strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return False

    return last_sent_date >= get_lookback_date(look_back, look_back_format)


def run_email_batch_stream(
    list_of_emails: List[str],
    subject: str,
    body: str,
    sender_email: str,
    sender_password: str,
    attachments=None,
    look_back: int = LOOK_BACK,
    look_back_format: str = LOOK_BACK_FORMAT,
    system_prompt: Optional[str] = None,
) -> Generator[Dict[str, Any], None, List[Dict[str, Any]]]:
    """
    Streaming generator for batch outreach:
    Yields event dicts at each step for live frontend rendering.
    """
    if not list_of_emails:
        raise ValueError("Recipient list cannot be empty.")
    if not subject or not subject.strip():
        raise ValueError("Subject cannot be empty.")
    if not body or not body.strip():
        raise ValueError("Email body cannot be empty.")

    # Validate attachment if present
    if attachments is not None:
        paths = [attachments] if isinstance(attachments, (str, Path)) else attachments
        for item in paths:
            path = Path(item).expanduser()
            if not path.is_file():
                raise FileNotFoundError(f"Attachment not found: {path}")
            if path.suffix.lower() != ".pdf":
                raise ValueError(f"Only PDF files are supported: {path}")

    # Deduplicate and validate input list
    unique_emails = []
    seen_emails = set()
    invalid_emails = []

    for item in list_of_emails:
        email = str(item).strip()
        if not EMAIL_PATTERN.fullmatch(email):
            invalid_emails.append(email)
            continue
        key = email.lower()
        if key not in seen_emails:
            seen_emails.add(key)
            unique_emails.append(email)

    # Calculate lookback counts
    already_contacted = []
    to_process = []

    for email in unique_emails:
        if was_recently_emailed(email, look_back, look_back_format):
            already_contacted.append(email)
        else:
            to_process.append(email)

    total_in_db = len(list_of_emails)
    already_sent_count = len(already_contacted)
    remaining_count = len(to_process)

    # 1. Yield initialization overview
    yield {
        "event": "init",
        "total_emails_in_db": total_in_db,
        "already_sent_count": already_sent_count,
        "look_back": look_back,
        "look_back_format": look_back_format,
        "remaining_to_send": remaining_count,
    }

    results = []

    # Record skipped already-contacted
    for skipped_email in already_contacted:
        results.append({
            "email": skipped_email,
            "status": "skipped_recently_contacted",
        })

    # Record invalid
    for inv in invalid_emails:
        results.append({
            "email": inv,
            "status": "invalid_email",
        })

    # Process remaining emails
    total_to_send = len(to_process)

    for index, email in enumerate(to_process, start=1):
        remaining_left = total_to_send - index

        # 2. Yield processing start
        yield {
            "event": "email_start",
            "index": index,
            "total": total_to_send,
            "email": email,
            "sender_email": sender_email,
            "generic_subject": subject,
            "generic_body": body,
        }

        # 3. Attempt generation with LLM or fallback
        final_subject = subject
        final_body = body
        used_llm = False
        llm_error_msg = None

        try:
            gen_res = generate_professional_email(
                recipient_email=email,
                general_subject=subject,
                general_body=body,
                system_prompt=system_prompt,
            )
            final_body = gen_res.body
            if gen_res.subject:
                final_subject = gen_res.subject
            used_llm = True

            yield {
                "event": "llm_success",
                "email": email,
                "used_llm": True,
                "subject": final_subject,
                "body": final_body,
            }

        except LLMUnavailableError as l_err:
            llm_error_msg = str(l_err)
            fallback_res = build_fallback_email(
                recipient_email=email,
                general_subject=subject,
                general_body=body,
            )
            final_body = fallback_res.body
            final_subject = fallback_res.subject or subject

            yield {
                "event": "llm_unavailable",
                "email": email,
                "used_llm": False,
                "reason": "Oops, sorry! No LLM detected (Ollama is offline or unreachable). Switching to the generic body.",
                "subject": final_subject,
                "body": final_body,
            }

        except Exception as gen_err:
            llm_error_msg = str(gen_err)
            fallback_res = build_fallback_email(
                recipient_email=email,
                general_subject=subject,
                general_body=body,
            )
            final_body = fallback_res.body
            final_subject = fallback_res.subject or subject

            yield {
                "event": "llm_unavailable",
                "email": email,
                "used_llm": False,
                "reason": f"AI generation encountered an issue ({gen_err}). Switching to the generic body.",
                "subject": final_subject,
                "body": final_body,
            }

        # 4. Dispatch Email via SMTP
        yield {
            "event": "sending",
            "email": email,
            "sender": sender_email,
            "subject": final_subject,
            "body": final_body,
        }

        try:
            success = send_email(
                recipient_email=email,
                subject=final_subject,
                body=final_body,
                sender_email=sender_email,
                sender_password=sender_password,
                attachments=attachments,
                look_back=look_back,
                look_back_format=look_back_format,
            )
            status = "sent_ai" if (success and used_llm) else ("sent_fallback" if success else "failed")
        except Exception as send_err:
            success = False
            status = "error"
            llm_error_msg = str(send_err)

        results.append({
            "email": email,
            "status": status,
            "subject": final_subject,
            "used_llm": used_llm,
        })

        # 5. Yield email completion status with remaining count
        yield {
            "event": "email_complete",
            "index": index,
            "total": total_to_send,
            "email": email,
            "status": status,
            "success": success,
            "remaining_emails_left": remaining_left,
        }

    # 6. Yield final batch complete
    yield {
        "event": "batch_complete",
        "results": results,
        "sent_count": sum(1 for r in results if "sent" in r.get("status", "")),
        "skipped_count": already_sent_count,
        "failed_count": sum(1 for r in results if r.get("status") in ("failed", "error")),
    }

    return results


def run_email_batch(
    list_of_emails: List[str],
    subject: str,
    body: str,
    sender_email: str,
    sender_password: str,
    attachments=None,
    look_back: int = LOOK_BACK,
    look_back_format: str = LOOK_BACK_FORMAT,
    system_prompt: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Non-streaming wrapper for run_email_batch_stream (used by CLI and tests)."""
    stream = run_email_batch_stream(
        list_of_emails=list_of_emails,
        subject=subject,
        body=body,
        sender_email=sender_email,
        sender_password=sender_password,
        attachments=attachments,
        look_back=look_back,
        look_back_format=look_back_format,
        system_prompt=system_prompt,
    )
    final_results = []
    for event in stream:
        if event.get("event") == "batch_complete":
            final_results = event.get("results", [])
    return final_results
