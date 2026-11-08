"""
Batch Email Sending Pipeline with Streaming Event Generation
============================================================
Checks history, generates personalized body (with graceful LLM fallback),
dispatches emails, and yields streaming progress updates.
Also provides parallel sending via adaptive worker pool.
"""

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Generator, Dict, Any, List, Optional, Union

from ai_email_writer.generator import (
    generate_professional_email,
    build_fallback_email,
    LLMUnavailableError,
    IncompleteEmailError,
)
from ai_email_writer.recipient import infer_recipient_name
from ai_email_writer.validator import email_validator
from config_loader import get_email_config
from resource_manager import get_safe_workers

from .date_utils import get_lookback_date
from .storage import load_email_storage
from .sender import send_email

LOOK_BACK = 1
LOOK_BACK_FORMAT = "months"

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

    last_sent = normalized_data.get(
        recipient_email.strip().lower()
    )
    if (
        last_sent is None
        or not last_sent.strip()
        or last_sent.lower() == "never"
    ):
        return False

    try:
        last_sent_date = datetime.strptime(
            last_sent.strip(), "%Y-%m-%d"
        ).date()
    except (ValueError, TypeError):
        return False

    return last_sent_date >= get_lookback_date(
        look_back, look_back_format
    )


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
    custom_db_path: Optional[Union[str, Path]] = None,
) -> Generator[Dict[str, Any], None, List[Dict[str, Any]]]:
    """
    Streaming generator for batch outreach.
    Yields event dicts at each step for live frontend rendering.
    """
    if not list_of_emails:
        raise ValueError("Recipient list cannot be empty.")
    if not subject or not subject.strip():
        raise ValueError("Subject cannot be empty.")
    if not body or not body.strip():
        raise ValueError("Email body cannot be empty.")

    if attachments is not None:
        paths = (
            [attachments]
            if isinstance(attachments, (str, Path))
            else attachments
        )
        for item in paths:
            path = Path(item).expanduser()
            if not path.is_file():
                raise FileNotFoundError(
                    f"Attachment not found: {path}"
                )
            if path.suffix.lower() != ".pdf":
                raise ValueError(
                    f"Only PDF files are supported: {path}"
                )

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

    already_contacted = []
    to_process = []

    for email in unique_emails:
        if was_recently_emailed(
            email, look_back, look_back_format
        ):
            already_contacted.append(email)
        else:
            to_process.append(email)

    total_in_db = len(list_of_emails)
    already_sent_count = len(already_contacted)
    remaining_count = len(to_process)

    yield {
        "event": "init",
        "total_emails_in_db": total_in_db,
        "already_sent_count": already_sent_count,
        "look_back": look_back,
        "look_back_format": look_back_format,
        "remaining_to_send": remaining_count,
    }

    results = []

    for skipped_email in already_contacted:
        results.append({
            "email": skipped_email,
            "status": "skipped_recently_contacted",
        })

    for inv in invalid_emails:
        results.append({
            "email": inv,
            "status": "invalid_email",
        })

    total_to_send = len(to_process)

    for index, email in enumerate(to_process, start=1):
        remaining_left = total_to_send - index

        yield {
            "event": "email_start",
            "index": index,
            "total": total_to_send,
            "email": email,
            "sender_email": sender_email,
            "generic_subject": subject,
            "generic_body": body,
        }

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
            recipient_name = infer_recipient_name(email)
            val_report = email_validator.validate(
                gen_res.body,
                recipient_name=recipient_name,
            )
            if not val_report.is_valid:
                raise IncompleteEmailError(
                    f"Completeness defects: "
                    f"{'; '.join(val_report.issues)}"
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

        except IncompleteEmailError as inc_err:
            llm_error_msg = str(inc_err)
            fallback_res = build_fallback_email(
                recipient_email=email,
                general_subject=subject,
                general_body=body,
            )
            final_body = fallback_res.body
            final_subject = fallback_res.subject or subject

            yield {
                "event": "llm_incomplete_fallback",
                "email": email,
                "used_llm": False,
                "reason": (
                    f"Incomplete AI generation "
                    f"({inc_err}). Switched to fallback."
                ),
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
                "reason": (
                    "No LLM detected (Ollama offline). "
                    "Switching to generic body."
                ),
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
                "event": "llm_incomplete_fallback",
                "email": email,
                "used_llm": False,
                "reason": (
                    f"AI generation issue ({gen_err}). "
                    f"Switched to fallback."
                ),
                "subject": final_subject,
                "body": final_body,
            }

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
                custom_db_path=custom_db_path,
            )
            status = (
                "sent_ai"
                if (success and used_llm)
                else ("sent_fallback" if success else "failed")
            )
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

        sent_date_str = (
            datetime.now().strftime("%Y-%m-%d")
            if success else None
        )
        yield {
            "event": "email_complete",
            "index": index,
            "total": total_to_send,
            "email": email,
            "status": status,
            "success": success,
            "sent_date": sent_date_str,
            "remaining_emails_left": remaining_left,
        }

    yield {
        "event": "batch_complete",
        "results": results,
        "sent_count": sum(
            1 for r in results
            if "sent" in r.get("status", "")
        ),
        "skipped_count": already_sent_count,
        "failed_count": sum(
            1 for r in results
            if r.get("status") in ("failed", "error")
        ),
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
    custom_db_path: Optional[Union[str, Path]] = None,
) -> List[Dict[str, Any]]:
    """Non-streaming wrapper — used by CLI and tests."""
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
        custom_db_path=custom_db_path,
    )
    final_results = []
    for event in stream:
        if event.get("event") == "batch_complete":
            final_results = event.get("results", [])
    return final_results


def run_email_batch_parallel(
    list_of_emails: List[str],
    subject: str,
    body: str,
    sender_email: str,
    sender_password: str,
    attachments=None,
    look_back: int = LOOK_BACK,
    look_back_format: str = LOOK_BACK_FORMAT,
    scraper_cfg: Optional[Dict[str, Any]] = None,
    custom_db_path: Optional[Union[str, Path]] = None,
) -> Generator[Dict[str, Any], None, None]:
    """
    Send emails in parallel using adaptive worker count.
    Template-only mode — no LLM for maximum speed.
    Yields same event format as run_email_batch_stream.
    """
    if not list_of_emails:
        raise ValueError("Recipient list cannot be empty.")
    if not subject or not subject.strip():
        raise ValueError("Subject cannot be empty.")
    if not body or not body.strip():
        raise ValueError("Email body cannot be empty.")

    cfg = scraper_cfg or {}
    workers = get_safe_workers(cfg)

    unique_emails: list[str] = []
    seen: set[str] = set()

    for item in list_of_emails:
        email = str(item).strip()
        if not EMAIL_PATTERN.fullmatch(email):
            continue
        key = email.lower()
        if key not in seen:
            seen.add(key)
            unique_emails.append(email)

    to_process = [
        email for email in unique_emails
        if not was_recently_emailed(
            email, look_back, look_back_format
        )
    ]

    yield {
        "event": "init",
        "total_emails_in_db": len(list_of_emails),
        "already_sent_count": (
            len(unique_emails) - len(to_process)
        ),
        "remaining_to_send": len(to_process),
        "workers": workers,
    }

    def _send_one(email: str) -> Dict[str, Any]:
        """Send a single email and return result dict."""
        try:
            success = send_email(
                recipient_email=email,
                subject=subject,
                body=body,
                sender_email=sender_email,
                sender_password=sender_password,
                attachments=attachments,
                look_back=look_back,
                look_back_format=look_back_format,
                custom_db_path=custom_db_path,
            )
            return {
                "email": email,
                "success": success,
                "sent_date": (
                    datetime.now().strftime("%Y-%m-%d")
                    if success else None
                ),
            }
        except Exception as error:
            return {
                "email": email,
                "success": False,
                "sent_date": None,
                "error": str(error),
            }

    sent_count = 0
    completed = 0

    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_email = {
            pool.submit(_send_one, email): email
            for email in to_process
        }

        for future in as_completed(future_to_email):
            completed += 1
            result = future.result()
            if result.get("success"):
                sent_count += 1
            yield {
                "event": "email_complete",
                "index": completed,
                "total": len(to_process),
                "email": result["email"],
                "success": result["success"],
                "sent_date": result.get("sent_date"),
                "remaining_emails_left": (
                    len(to_process) - completed
                ),
            }

    yield {
        "event": "batch_complete",
        "sent_count": sent_count,
        "workers_used": workers,
    }
