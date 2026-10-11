from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .attachments import attach_pdf_files


def build_email_message(
    recipient_email: str,
    subject: str,
    body: str,
    sender_email: str,
    attachments=None
) -> MIMEMultipart:
    """Construct an email with an optional PDF attachment."""

    message = MIMEMultipart()

    message["From"] = sender_email
    message["To"] = recipient_email
    message["Subject"] = subject

    message.attach(
        MIMEText(body, "plain", "utf-8")
    )

    attach_pdf_files(message, attachments)

    return message
