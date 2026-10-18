import re
from datetime import datetime
from pathlib import Path

from ai_email_writer.generator import generate_professional_email
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

    last_sent = normalized_data.get(
        recipient_email.strip().lower()
    )

    if last_sent is None:
        return False

    try:
        last_sent_date = datetime.strptime(
            last_sent, "%Y-%m-%d"
        ).date()
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"Invalid stored date for {recipient_email}: {last_sent!r}"
        ) from exc

    return last_sent_date >= get_lookback_date(
        look_back, look_back_format
    )


def run_email_batch(
    list_of_emails: list[str],
    subject: str,
    body: str,
    sender_email: str,
    sender_password: str,
    attachments=None,
    look_back: int = LOOK_BACK,
    look_back_format: str = LOOK_BACK_FORMAT,
) -> list[dict]:
    """
    Check history -> generate personalized body -> send email.

    The subject remains fixed. Recently contacted recipients
    are skipped before any LLM call.
    """

    if not list_of_emails:
        raise ValueError("Recipient list cannot be empty.")

    if not subject or not subject.strip():
        raise ValueError("Subject cannot be empty.")

    if not body or not body.strip():
        raise ValueError("Email body cannot be empty.")

    # Validate attachments before processing recipients.
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

    results = []
    unique_emails = []
    seen_emails = set()

    # Validate and deduplicate the input list.
    for item in list_of_emails:
        if not isinstance(item, str):
            results.append({
                "email": str(item),
                "status": "invalid_email",
            })
            continue

        email = item.strip()

        if not EMAIL_PATTERN.fullmatch(email):
            results.append({
                "email": email,
                "status": "invalid_email",
            })
            continue

        key = email.lower()

        if key in seen_emails:
            results.append({
                "email": email,
                "status": "duplicate_in_input",
            })
            continue

        seen_emails.add(key)
        unique_emails.append(email)

    total = len(unique_emails)

    for index, email in enumerate(unique_emails, start=1):
        print(f"\n[{index}/{total}] Processing: {email}")

        try:
            # 1. Check history BEFORE calling the LLM.
            if was_recently_emailed(
                email, look_back, look_back_format
            ):
                print("Skipped: recently contacted.")

                results.append({
                    "email": email,
                    "status": "skipped_recently_contacted",
                })
                continue

            # 2. Generate the personalized email body.
            result = generate_professional_email(
                recipient_email=email,
                general_subject=subject,
                general_body=body,
            )

            if not result.body.strip():
                raise ValueError("Generated email body is empty.")

            # 3. Send the email with the fixed subject.
            success = send_email(
                recipient_email=email,
                subject=subject,
                body=result.body,
                sender_email=sender_email,
                sender_password=sender_password,
                attachments=attachments,
                look_back=look_back,
                look_back_format=look_back_format,
            )

            status = "sent" if success else "failed"

            results.append({
                "email": email,
                "status": status,
            })

            print(f"Result: {status}")

        except Exception as exc:
            print(f"Error for {email}: {exc}")

            results.append({
                "email": email,
                "status": "error",
                "error": str(exc),
            })

    print("\n========== BATCH SUMMARY ==========")

    for status in (
        "sent",
        "skipped_recently_contacted",
        "duplicate_in_input",
        "invalid_email",
        "failed",
        "error",
    ):
        count = sum(
            item["status"] == status
            for item in results
        )
        print(f"{status}: {count}")

    return results

