"""
End-to-End Test Suite for AI Job Search & Auto-Apply
===================================================
Tests all core components:
1. Configuration Loader & Profile Fetching
2. Email Database Helper (Ingestion, Validation, Parsing, Backups, Domain Ops, Exports)
3. AI Email Writer (Recipient inference, System Prompt, Validator, Formatting, Offline Fallback)
4. Email Sender (Lookback date calculation, MIME Builder, Attachment Validator, Batch Streaming)
5. Streamlit App End-to-End Rendering (AppTest)
"""

import sys
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
import pytest

# Ensure src/ is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# ==============================================================================
# 1. Config Loader Tests
# ==============================================================================
def test_config_loader():
    from config_loader import (
        get_candidate_profile,
        get_email_config,
        get_model_config,
        get_smtp_config,
    )

    profile = get_candidate_profile()
    assert isinstance(profile, dict)
    assert "name" in profile or "current_role" in profile

    email_cfg = get_email_config()
    assert isinstance(email_cfg, dict)
    assert "subject" in email_cfg

    model_cfg = get_model_config()
    assert isinstance(model_cfg, dict)
    assert "model_name" in model_cfg

    smtp_cfg = get_smtp_config()
    assert isinstance(smtp_cfg, dict)
    assert smtp_cfg.get("port") in (587, 465, 25)


# ==============================================================================
# 2. Email Database Helper & Multi-Format Ingestion Tests
# ==============================================================================
def test_email_db_helper_operations():
    from email_db_helper import (
        is_valid_email,
        extract_emails_from_text,
        load_email_database,
        save_email_database,
        export_email_database,
        group_emails_by_domain,
        get_domain_statistics,
        delete_domain_from_database,
    )

    # Email validation & extraction
    assert is_valid_email("hr.recruiter@company.com") is True
    assert is_valid_email("invalid-email@.com") is False
    assert is_valid_email("user@domain..com") is False

    raw_text = """
    Contact us at hiring@google.com or careers@amazon.com for opportunities.
    Fake: hello@world. and test@example
    """
    extracted = extract_emails_from_text(raw_text)
    assert "hiring@google.com" in extracted
    assert "careers@amazon.com" in extracted
    assert len(extracted) == 2

    # Multi-format export tests
    sample_db = {
        "candidate@capgemini.com": "2026-03-01",
        "recruiter@ey.com": "Never",
        "hr@google.com": "2026-02-15",
    }
    csv_bytes = export_email_database(sample_db, "csv")
    assert b"candidate@capgemini.com" in csv_bytes

    json_bytes = export_email_database(sample_db, "json")
    assert b"recruiter@ey.com" in json_bytes

    txt_bytes = export_email_database(sample_db, "txt")
    assert b"hr@google.com" in txt_bytes

    xlsx_bytes = export_email_database(sample_db, "xlsx")
    assert len(xlsx_bytes) > 0

    # Domain Grouping & Analytics
    grouped = group_emails_by_domain(sample_db)
    assert "capgemini.com" in grouped
    assert "ey.com" in grouped
    assert "google.com" in grouped

    stats = get_domain_statistics(sample_db)
    assert stats["total_emails"] == 3
    assert stats["total_domains"] == 3
    assert stats["contacted_count"] == 2
    assert stats["uncontacted_count"] == 1

    # Domain Deletion
    updated, deleted_count = delete_domain_from_database(sample_db, "capgemini.com")
    assert deleted_count == 1
    assert "candidate@capgemini.com" not in updated
    assert len(updated) == 2


# ==============================================================================
# 3. AI Email Writer Components Tests
# ==============================================================================
def test_ai_email_writer_components():
    from ai_email_writer.recipient import infer_recipient_name
    from ai_email_writer.formatter import enforce_correct_greeting, format_email_body
    from ai_email_writer.validator import EmailValidator
    from ai_email_writer.prompts import build_generic_system_prompt

    # Recruiter Name inference
    name1 = infer_recipient_name("john.doe@techcorp.com")
    assert name1 == "John Doe"

    name2 = infer_recipient_name("hr@startup.io")
    assert name2 is None

    # Salutation / Greeting formatting
    formatted_greet = enforce_correct_greeting("I am applying for the role.", name1)
    assert formatted_greet.startswith("Hi John Doe,\n\n")

    # Complete formatting
    full_body = format_email_body(
        body_text="I am writing regarding the open position.",
        recipient_name=name1,
        candidate_name="Rahul Singh",
    )
    assert "Hi John Doe," in full_body
    assert "Rahul Singh" in full_body

    # Dynamic generic system prompt builder
    sys_prompt = build_generic_system_prompt()
    assert isinstance(sys_prompt, str)
    assert len(sys_prompt) > 50

    # Quality Validator
    validator = EmailValidator()
    good_body = """Hi John,

I am writing to express my enthusiasm for the Data Scientist position at Techcorp.
With 3 years of hands-on experience developing ML and GenAI architectures, I am eager to contribute.

Best regards,
Rahul Singh"""
    val_res = validator.validate(good_body)
    assert val_res.is_valid is True

    bad_body = "Hey check my resume. [Insert Company Name] here."
    val_bad = validator.validate(bad_body)
    assert val_bad.is_valid is False
    assert len(val_bad.issues) > 0


# ==============================================================================
# 4. Email Sender & Lookback Tests
# ==============================================================================
def test_email_sender_logic():
    from email_sender.date_utils import get_lookback_date
    from email_sender.builder import build_email_message
    from email_sender.batch import run_email_batch_stream

    # Lookback calculations
    today = datetime.now().date()
    one_month_ago = get_lookback_date(look_back=1, look_back_format="months")
    assert one_month_ago < today
    assert (today - one_month_ago).days >= 28

    # MIME Builder
    msg = build_email_message(
        sender_email="me@example.com",
        recipient_email="recruiter@target.com",
        subject="Application for AI Role",
        body="Dear Recruiter,\n\nPlease find my resume attached.\n\nBest,\nCandidate",
        attachments=None,
    )
    assert msg["From"] == "me@example.com"
    assert msg["To"] == "recruiter@target.com"
    assert msg["Subject"] == "Application for AI Role"

    # Batch Stream Generator Test (Headless init event)
    recipients = ["test1@domain.com", "test2@domain.com"]
    stream = run_email_batch_stream(
        list_of_emails=recipients,
        subject="AI Role Application",
        body="Hi,\n\nPlease review my application.\n\nBest regards,\nRahul",
        sender_email="me@example.com",
        sender_password="mock_test_password",
        attachments=None,
        look_back=1,
        look_back_format="months",
    )
    init_event = next(stream)
    assert init_event["event"] == "init"
    assert init_event["total_emails_in_db"] == 2
    assert init_event["remaining_to_send"] == 2


# ==============================================================================
# 5. Streamlit App End-to-End Rendering Test (No Exceptions)
# ==============================================================================
def test_streamlit_app_renders_without_exceptions():
    from streamlit.testing.v1 import AppTest

    app_path = PROJECT_ROOT / "bin" / "app.py"
    at = AppTest.from_file(str(app_path), default_timeout=30)
    at.run()
    # Confirm that there are no unhandled exceptions (such as nested expanders)
    assert len(at.exception) == 0, f"AppTest raised exceptions: {at.exception}"
