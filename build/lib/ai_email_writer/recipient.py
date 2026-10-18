import re
from email.utils import parseaddr
from config_loader import get_generic_email_prefixes

GENERIC_EMAIL_NAMES = set(get_generic_email_prefixes())


def clean_name_token(token: str) -> str:
    """Remove numbers and special symbols from a name token."""
    token = re.sub(r"\d+", "", token).strip()
    return token


def format_person_name(name: str) -> str | None:
    """Clean and format a recognizable person's name."""
    name = re.sub(r"\s+", " ", name.strip().strip("\"'"))

    if not name:
        return None

    # Replace separators with space
    name = re.sub(r"[._-]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()

    raw_words = name.split()
    if not raw_words or len(raw_words) > 4:
        return None

    words = []
    for w in raw_words:
        cleaned = clean_name_token(w)
        if cleaned and len(cleaned) >= 2:
            if re.fullmatch(r"[A-Za-z]+(?:[''][A-Za-z]+)*", cleaned):
                words.append(cleaned)

    if not words:
        return None

    # Skip generic mailbox prefixes like hr, careers, info, team
    if any(word.lower() in GENERIC_EMAIL_NAMES for word in words):
        return None

    formatted = " ".join(word.capitalize() for word in words)
    return formatted


def infer_recipient_name(recipient_email: str) -> str | None:
    """
    Infer a recipient's human name from a display name or email address.

    Examples:
        vishal.seth@capgemini.com -> Vishal Seth
        akanksha.tiwari01@nagarro.com -> Akanksha Tiwari
        anjul@ringg.ai -> Anjul
        yashika@vitric.in -> Yashika
        careers@company.com -> None
        hr@company.com -> None
    """
    if not recipient_email or not recipient_email.strip():
        return None

    display_name, email_address = parseaddr(recipient_email.strip())

    # 1. Prefer an explicitly supplied display name: "John Doe <john@...>"
    if display_name:
        cleaned_name = format_person_name(display_name)
        if cleaned_name:
            return cleaned_name

    if "@" not in email_address:
        return None

    local_part = email_address.split("@", 1)[0]
    local_part = local_part.split("+", 1)[0]

    # Split into parts by dot, underscore, dash
    tokens = re.split(r"[._-]+", local_part)

    clean_tokens = []
    for token in tokens:
        cleaned = clean_name_token(token)
        # Keep alphabetic tokens of length >= 2
        if cleaned and len(cleaned) >= 2 and cleaned.isalpha():
            clean_tokens.append(cleaned)

    if not clean_tokens or len(clean_tokens) > 3:
        return None

    # Reject if any token is a known generic role/department
    if any(token.lower() in GENERIC_EMAIL_NAMES for token in clean_tokens):
        return None

    return " ".join(token.capitalize() for token in clean_tokens)


def get_greeting_name(recipient_email: str) -> str | None:
    """
    Get the preferred greeting name (first name) for email salutation: 'Hi [Name],'.

    Examples:
        vishal.seth@capgemini.com -> Vishal
        anjul@ringg.ai -> Anjul
        careers@company.com -> None
    """
    full_name = infer_recipient_name(recipient_email)
    if not full_name:
        return None

    # Extract first name for personal, natural email greeting
    first_name = full_name.split()[0]
    return first_name
