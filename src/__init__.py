"""AI Job Search and Auto Apply package."""

from .config_loader import (
    load_project_config,
    get_candidate_profile,
    get_email_config,
    get_model_config,
    get_smtp_config,
    get_recipients,
    get_generic_email_prefixes,
)

__all__ = [
    "load_project_config",
    "get_candidate_profile",
    "get_email_config",
    "get_model_config",
    "get_smtp_config",
    "get_recipients",
    "get_generic_email_prefixes",
]

