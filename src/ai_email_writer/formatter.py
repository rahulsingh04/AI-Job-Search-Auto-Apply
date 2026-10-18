import re


def enforce_correct_greeting(
    body_text: str,
    recipient_name: str | None
) -> str:
    """
    Remove an existing opening greeting and add the correct one.
    """

    text = body_text.strip()

    # Remove greetings such as:
    # Hi Rahul Singh,
    # Hello Vishal,
    # Dear Prashant,
    # Hi,
    greeting_pattern = (
        r"^\s*(?:hi|hello|dear|hey)\b[^,\n]{0,100},\s*"
    )

    text, substitutions = re.subn(
        greeting_pattern,
        "",
        text,
        count=1,
        flags=re.IGNORECASE
    )

    # Handle a greeting without a comma on its own line.
    if substitutions == 0:
        lines = text.splitlines()

        if lines:
            first_line = lines[0].strip()

            greeting_only_pattern = (
                r"^(?:hi|hello|dear|hey)"
                r"(?:\s+[^,\n]{1,80})?$"
            )

            if re.fullmatch(
                greeting_only_pattern,
                first_line,
                flags=re.IGNORECASE
            ):
                text = "\n".join(lines[1:]).lstrip()

    text = text.strip()

    if recipient_name:
        greeting = f"Hi {recipient_name},"
    else:
        greeting = "Hi,"

    if not text:
        return greeting

    return f"{greeting}\n\n{text}"


def format_numbered_skills(body_text: str) -> str:
    """
    Put numbered skill points on separate lines.

    Example:
        1. Python 2. SQL 3. Machine Learning

    Becomes:
        1. Python
        2. SQL
        3. Machine Learning
    """

    text = body_text.replace("\r\n", "\n").replace("\r", "\n")

    # Insert a newline before numbered points that appear
    # after another point on the same line.
    text = re.sub(
        r"[ \t]+(?=\d{1,2}\.\s+)",
        "\n",
        text
    )

    # Remove unnecessary spaces at the start of lines.
    lines = [line.strip() for line in text.split("\n")]

    # Keep paragraph separation and numbered points readable.
    return "\n".join(lines).strip()


def ensure_complete_closing(body_text: str, candidate_name: str = "Rahul Singh") -> str:
    """
    Ensure the email ends with a proper polite closing and candidate signature if missing.
    """
    text = body_text.strip()
    closing_patterns = [
        r"(?:best\s+regards|warm\s+regards|regards|sincerely|kind\s+regards|best|warmly)",
    ]
    has_closing = any(re.search(pat, text, flags=re.IGNORECASE) for pat in closing_patterns)
    has_signature = any(re.search(pat, text, flags=re.IGNORECASE) for pat in [r"rahul\s+kumar\s+singh", r"rahul\s+singh", r"rahul"])

    if not has_closing and not has_signature:
        return f"{text}\n\nBest regards,\n{candidate_name}"
    elif has_closing and not has_signature:
        return f"{text}\n{candidate_name}"
    return text


def format_email_body(
    body_text: str,
    recipient_name: str | None,
    candidate_name: str = "Rahul Singh"
) -> str:
    """
    Apply skill formatting first, add greeting, and ensure complete closing.
    """
    text = format_numbered_skills(body_text)
    text = enforce_correct_greeting(text, recipient_name)
    return ensure_complete_closing(text, candidate_name)

