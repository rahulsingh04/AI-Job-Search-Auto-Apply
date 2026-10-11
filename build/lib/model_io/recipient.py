import re
from email.utils import parseaddr


GENERIC_EMAIL_NAMES = {
    "career", "careers", "hr", "jobs", "job",
    "recruitment", "recruiter", "hiring", "talent",
    "info", "contact", "support", "admin", "hello",
    "office", "team", "enquiry", "enquiries", "sales",
    "noreply", "notifications", "applications", "apply",
    "mail", "billing", "accounts", "service", "marketing",
    "help", "customerservice", "customer", "feedback",
    "jobsindia", "recruitmentteam", "careersindia",
    "example", "test", "username", "firstname", "lastname"
}


def format_person_name(name: str) -> str | None:
    """Clean and format a recognizable person's name."""

    name = re.sub(r"\s+", " ", name.strip().strip("\"'"))

    if not name:
        return None

    name = re.sub(r"[._-]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()

    words = name.split()

    if not words or len(words) > 4:
        return None

    for word in words:
        if not re.fullmatch(r"[A-Za-z]+(?:['’][A-Za-z]+)*", word):
            return None

    if any(
        word.lower() in GENERIC_EMAIL_NAMES
        for word in words
    ):
        return None

    if name.islower() or name.isupper():
        name = " ".join(word.capitalize() for word in words)

    return name


def infer_recipient_name(recipient_email: str) -> str | None:
    """
    Infer a recipient's name from a display name or email address.

    Examples:
        vishal.seth@capgemini.com -> Vishal Seth
        career@gmail.com -> None
        hr@company.com -> None
    """

    display_name, email_address = parseaddr(
        recipient_email.strip()
    )

    # Prefer an explicitly supplied display name.
    if display_name:
        cleaned_name = format_person_name(display_name)

        if cleaned_name:
            return cleaned_name

    if "@" not in email_address:
        return None

    local_part = email_address.split("@", 1)[0]
    local_part = local_part.split("+", 1)[0]

    name_parts = re.split(r"[._-]+", local_part)

    if not name_parts or len(name_parts) > 3:
        return None

    if any(
        not part.isalpha() or len(part) < 2
        for part in name_parts
    ):
        return None

    # Avoid guessing a full name from an ambiguous single token.
    if len(name_parts) == 1:
        return None

    return format_person_name(" ".join(name_parts))
