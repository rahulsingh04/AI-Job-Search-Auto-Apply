"""AI-powered professional email writer using local Ollama models."""

__all__ = [
    "generate_professional_email",
    "EmailResponse",
    "get_greeting_name",
    "infer_recipient_name",
    "CandidateProfile",
    "parse_resume_to_profile",
    "save_candidate_profile_config",
]


def __getattr__(name):
    """Lazy imports to avoid pulling in heavy dependencies at package level."""

    if name == "generate_professional_email":
        from .generator import generate_professional_email
        return generate_professional_email

    if name == "EmailResponse":
        from .schemas import EmailResponse
        return EmailResponse

    if name == "get_greeting_name":
        from .recipient import get_greeting_name
        return get_greeting_name

    if name == "infer_recipient_name":
        from .recipient import infer_recipient_name
        return infer_recipient_name

    if name in ("CandidateProfile", "parse_resume_to_profile", "save_candidate_profile_config"):
        from .resume_parser import (
            CandidateProfile,
            parse_resume_to_profile,
            save_candidate_profile_config,
        )
        if name == "CandidateProfile":
            return CandidateProfile
        elif name == "parse_resume_to_profile":
            return parse_resume_to_profile
        return save_candidate_profile_config

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
