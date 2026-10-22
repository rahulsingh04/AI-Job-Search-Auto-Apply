from datetime import date, datetime

from .date_utils import get_lookback_date
from .builder import build_email_message
from .smtp import send_via_gmail
from .storage import load_email_storage, save_email_storage


def send_email(
    recipient_email: str,
    subject: str,
    body: str,
    sender_email: str,
    sender_password: str,
    attachments=None,
    look_back: int = 0,
    look_back_format: str = "day"
) -> bool:
    """
    Send an email with optional PDFs and duplicate-send protection.

    Returns True if SMTP sending succeeds, otherwise False.
    """

    try:
        # Validate the look-back period.
        lookback_date = get_lookback_date(
            look_back,
            look_back_format
        )

        if not recipient_email or not recipient_email.strip():
            raise ValueError("Recipient email cannot be empty.")

        if not sender_email or not sender_email.strip():
            raise ValueError("Sender email cannot be empty.")

        if not sender_password:
            raise ValueError("Sender password cannot be empty.")

        if not subject or not subject.strip():
            raise ValueError("Subject cannot be empty.")

        if not body or not body.strip():
            raise ValueError("Email body cannot be empty.")

        # Load the existing history.
        email_data = load_email_storage()
        today = date.today()

        # Check whether this recipient was emailed recently.
        # Match the recipient case-insensitively and repair recognized date formats.
        recipient_key = next(
            (
                stored_email
                for stored_email in email_data
                if str(stored_email).strip().lower() == recipient_email.strip().lower()
            ),
            recipient_email,
        )
        last_sent_string = email_data.get(recipient_key)
        raw_last_sent = (
            str(last_sent_string).strip()
            if last_sent_string is not None
            else ""
        )

        # Blank or "Never" means the recipient has not been emailed before.
        if raw_last_sent and raw_last_sent.lower() != "never":
            last_sent_date = None

            try:
                # Accept ISO dates and ISO timestamps.
                last_sent_date = datetime.fromisoformat(
                    raw_last_sent.replace("Z", "+00:00")
                ).date()
            except (ValueError, TypeError):
                # Try common date formats, prioritizing day/month/year.
                for date_format in (
                    "%d/%m/%Y",
                    "%d-%m-%Y",
                    "%d.%m.%Y",
                    "%Y/%m/%d",
                    "%Y.%m.%d",
                    "%d/%m/%y",
                    "%d-%m-%y",
                    "%d.%m.%y",
                    "%d-%b-%Y",
                    "%d %b %Y",
                    "%d %B %Y",
                    "%B %d, %Y",
                    "%b %d, %Y",
                ):
                    try:
                        last_sent_date = datetime.strptime(
                            raw_last_sent, date_format
                        ).date()
                        break
                    except ValueError:
                        continue

            if last_sent_date is None:
                raise ValueError(
                    f"Invalid stored date for {recipient_email}: "
                    f"{last_sent_string!r}. Automatic repair failed. "
                    "Supported formats include YYYY-MM-DD, DD/MM/YYYY, "
                    "DD-MM-YYYY, DD.MM.YYYY, and ISO timestamps."
                )

            normalized_date = last_sent_date.strftime("%Y-%m-%d")

            # Persist the repair immediately, even if sending is skipped below.
            if raw_last_sent != normalized_date:
                email_data[recipient_key] = normalized_date
                save_email_storage(email_data)
                print(
                    f"[Email Storage] Repaired date for {recipient_key}: "
                    f"{raw_last_sent!r} -> {normalized_date}"
                )

            if last_sent_date >= lookback_date:
                print(
                    f"[Email] Skipping {recipient_email}: already emailed on "
                    f"{normalized_date}, within the lookback period."
                )
                return False

        # Build the message and validate attachments before connecting.
        message = build_email_message(
            recipient_email=recipient_email,
            subject=subject,
            body=body,
            sender_email=sender_email,
            attachments=attachments
        )

        # Send via Gmail.
        send_via_gmail(
            message=message,
            sender_email=sender_email,
            sender_password=sender_password,
            recipient_email=recipient_email
        )

    except ValueError as exc:
        if str(exc).startswith("Invalid stored date for "):
            raise
        print(f"Email sending failed: {exc}")
        return False
    except Exception as exc:
        print(f"Email sending failed: {exc}")
        return False

    # SMTP send succeeded. Save the history separately so a storage
    # failure is not incorrectly reported as a failed email send.
    email_data[recipient_email] = today.strftime("%Y-%m-%d")

    try:
        save_email_storage(email_data)

    except Exception as exc:
        print(
            f"Email was sent to {recipient_email}, but the history "
            f"could not be saved: {exc}"
        )
        return True

    print(f"Email sent successfully to {recipient_email}.")
    print(f"Email history updated for {today}.")

    return True

