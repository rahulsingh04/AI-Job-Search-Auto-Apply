import smtplib
import ssl


def send_via_gmail(
    message,
    sender_email: str,
    sender_password: str,
    recipient_email: str
) -> None:
    """Send an email using Gmail SMTP and an App Password."""

    with smtplib.SMTP(
        "smtp.gmail.com",
        587,
        timeout=30
    ) as server:
        server.ehlo()

        server.starttls(
            context=ssl.create_default_context()
        )

        server.ehlo()
        server.login(sender_email, sender_password)

        server.send_message(
            message,
            from_addr=sender_email,
            to_addrs=[recipient_email]
        )
