"""
AI Job Search & Auto-Apply — Main Entry Point
================================================

Sends personalized, AI-generated job-application emails
to a list of recruiters using a local Ollama LLM.

Usage:
    python main.py

Requirements:
    - Ollama running locally with the deepseek-r1:1.5b model
    - A Gmail account with an App Password
    - The project installed in dev mode:  pip install -e ".[dev]"
"""

import os
import sys
from pathlib import Path
from getpass import getpass

# ---------------------------------------------------------------------------
# Ensure the src/ directory is importable when running directly from bin/.
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# ---------------------------------------------------------------------------
# Set the storage file path relative to this script's directory.
# ---------------------------------------------------------------------------
os.environ.setdefault(
    "EMAIL_STORAGE_FILE",
    str(Path(__file__).resolve().parent / "data" / "Email_Storage.json")
)

from config_loader import get_email_config, get_recipients  # noqa: E402
from email_sender.batch import run_email_batch  # noqa: E402


def main():
    """Run the batch email pipeline using configuration from data/config/."""

    # 1. Load static configuration from data/config
    email_cfg = get_email_config()
    recipients = get_recipients()

    sender_email = email_cfg.get("sender_email", "")
    resume_filename = email_cfg.get("resume_filename", "RAHUL_SINGH_3YR_EXPERIENCE_DATA_SCIENTIST_.pdf")
    resume_path = PROJECT_ROOT / resume_filename
    subject = email_cfg.get("subject", "")
    body = email_cfg.get("body_template", "")
    look_back = email_cfg.get("look_back", 1)
    look_back_format = email_cfg.get("look_back_format", "months")

    # 2. Validate configuration
    if not sender_email:
        print("ERROR: sender_email is not configured in data/config/email_config.json")
        sys.exit(1)

    if not recipients:
        print("ERROR: No recipients found in data/config/recipients.json")
        sys.exit(1)

    if not resume_path.is_file():
        print(f"ERROR: Resume not found at {resume_path}")
        sys.exit(1)

    print(f"Loaded configuration for sender: {sender_email}")
    print(f"Total recipients to process: {len(recipients)}")
    print(f"Resume verified: {resume_path.name}")

    # 3. Prompt for the Gmail App Password securely
    sender_password = getpass("Enter your Gmail App Password: ")

    if not sender_password.strip():
        print("ERROR: Password cannot be empty.")
        sys.exit(1)

    # 4. Run the batch pipeline
    results = run_email_batch(
        list_of_emails=recipients,
        subject=subject,
        body=body,
        sender_email=sender_email,
        sender_password=sender_password,
        attachments=str(resume_path),
        look_back=look_back,
        look_back_format=look_back_format,
    )

    print("\nBatch processing completed.")
    print(f"Total recipients processed: {len(results)}")


if __name__ == "__main__":
    main()
