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
        last_sent_string = email_data.get(recipient_email)

        if last_sent_string is not None:
            try:
                last_sent_date = datetime.strptime(
                    last_sent_string,
                    "%Y-%m-%d"
                ).date()

            except (ValueError, TypeError) as exc:
                # Fail safely rather than risk a duplicate send
                # because the stored date is invalid.
                raise ValueError(
                    f"Invalid stored date for {recipient_email}: "
                    f"{last_sent_string!r}. Correct the history "
                    "before sending."
                ) from exc

            if last_sent_date >= lookback_date:
                print(
                    f"Email NOT sent to {recipient_email}. "
                    f"Last sent on {last_sent_date}; this is "
                    f"within the configured look-back period "
                    f"of {look_back} {look_back_format}."
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

