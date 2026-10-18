"""
Email Body Validator Tool
=========================
Validates whether a generated email body is complete, properly formatted,
and professional before sending. Returns specific feedback if validation fails
so the LLM can regenerate an improved version.
"""

import re
from dataclasses import dataclass
from typing import List


@dataclass
class ValidationReport:
    """Result of validating an email body."""
    is_valid: bool
    issues: List[str]

    @property
    def feedback(self) -> str:
        """Formatted feedback message for prompt corrections."""
        if not self.issues:
            return ""
        items = "\n".join(f"- {issue}" for issue in self.issues)
        return f"CORRECTION REQUIRED:\nThe previous email failed validation due to the following defects:\n{items}\nPlease completely regenerate the email body resolving all of these defects."


class EmailValidator:
    """Tool to inspect and validate email bodies for completeness and formatting."""

    # Unacceptable placeholder tokens that LLMs sometimes leave
    PLACEHOLDER_PATTERNS = [
        r"\[(?:insert|company|name|recipient|date|your name|role|job title)[^\]]*\]",
        r"<(?:insert|company|name|recipient|date)[^>]*>",
        r"\b(?:TODO|TBD|N/A|XXXX)\b",
    ]

    # Markers that indicate candidate profile was dumped instead of tailored
    PROFILE_DUMP_MARKERS = [
        "current organization:",
        "previous organization:",
        "technical skills:",
        "relevant project experience:",
        "professional experience:",
        "education:",
        "candidate profile:",
    ]

    # Required closing phrases
    CLOSING_PATTERNS = [
        r"(?:best\s+regards|warm\s+regards|regards|sincerely|kind\s+regards|best|warmly)",
    ]

    # Required sign-off names
    SIGNATURE_PATTERNS = [
        r"(?:rahul\s+kumar\s+singh|rahul\s+singh|rahul)",
    ]

    def validate(self, body_text: str, recipient_name: str | None = None) -> ValidationReport:
        """
        Run comprehensive validation checks on the email body text.
        """
        issues: List[str] = []

        if not body_text or not body_text.strip():
            return ValidationReport(is_valid=False, issues=["Email body is completely empty."])

        text = body_text.strip()

        # 1. Check for raw code fences, JSON or markdown artifacts
        if "```" in text or '{"body":' in text or '"body":' in text:
            issues.append("Email contains raw markdown code fences (```) or JSON formatting. Return plain email text only.")

        # 2. Check length and word count
        words = text.split()
        if len(words) < 35:
            issues.append(f"Email is too brief and incomplete ({len(words)} words). Provide a complete, substantive outreach message.")
        elif len(text) > 2500 or len(words) > 350:
            issues.append("Email is excessively long or repetitive. Keep it concise (approx. 90-150 words).")

        # 3. Check for leftover placeholders
        for pattern in self.PLACEHOLDER_PATTERNS:
            if re.search(pattern, text, flags=re.IGNORECASE):
                issues.append("Email contains unresolved placeholders (e.g. [Company Name], [Name], TODO). Use natural phrasing without bracketed placeholders.")
                break

        # 4. Check for profile dumping
        text_lower = text.lower()
        dump_count = sum(marker in text_lower for marker in self.PROFILE_DUMP_MARKERS)
        if dump_count >= 2:
            issues.append("Email copies raw resume/profile headings (e.g. 'Relevant Project Experience', 'Education'). Write a natural conversational message instead of pasting resume sections.")

        # 5. Check proper greeting
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        first_line = lines[0] if lines else ""
        if not re.match(r"^(?:hi|hello|dear|hey)\b", first_line, flags=re.IGNORECASE):
            issues.append(f"Email is missing a proper greeting at the start (e.g. 'Hi {recipient_name or ''},').")

        # 6. Check closing and sign-off
        closing_found = any(re.search(pat, text, flags=re.IGNORECASE) for pat in self.CLOSING_PATTERNS)
        signature_found = any(re.search(pat, text, flags=re.IGNORECASE) for pat in self.SIGNATURE_PATTERNS)

        if not closing_found:
            issues.append("Email is missing a polite closing (e.g. 'Best regards,').")

        if not signature_found:
            issues.append("Email is missing the candidate signature 'Rahul Singh' or 'Rahul Kumar Singh'.")

        # 7. Check for incomplete or cut-off sentences
        # Inspect the last paragraph before the sign-off
        if len(lines) >= 2:
            # Find candidate body paragraphs before closing
            body_lines = [
                l for l in lines[1:]
                if not any(re.search(p, l, flags=re.IGNORECASE) for p in self.CLOSING_PATTERNS)
                and not any(re.search(p, l, flags=re.IGNORECASE) for p in self.SIGNATURE_PATTERNS)
            ]
            if body_lines:
                last_body_line = body_lines[-1].strip()
                # Check if it ends abruptly with comma, hyphen, colon or trailing conjunction
                if re.search(r"[,;:\-–—\(\[\{]\s*$", last_body_line) or re.search(r"\b(?:and|or|with|to|that|because|as)\s*$", last_body_line, flags=re.IGNORECASE):
                    issues.append("Email body appears truncated or cut off mid-sentence before the closing.")

        return ValidationReport(is_valid=(len(issues) == 0), issues=issues)


# Shared global validator instance
email_validator = EmailValidator()

