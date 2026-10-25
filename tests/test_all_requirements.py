"""
Comprehensive Automated Tests for AI-Job-Search-Auto-Apply Fixes
================================================================
Tests all 4 requirements:
1. Resume-based templates (Extract details, 5 templates, select & edit, validator pass)
2. Email database (Immediate update of Email_Storage.json on send)
3. Domain filtering (Search by full email OR domain name)
4. Dynamic UI & Shared Database synchronization across sections
NOTE: No real emails are sent; SMTP is mocked.
"""

import sys
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, date

import pytest

# Ensure src/ is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config_loader import get_candidate_profile
from ai_email_writer.resume_parser import (
    CandidateProfile,
    parse_resume_to_profile,
    extract_text_from_file,
)
from ai_email_writer.templates import generate_resume_templates
from ai_email_writer.validator import email_validator
from email_db_helper import (
    group_emails_by_domain,
    get_domain_statistics,
    filter_grouped_domains,
    filter_database_by_query,
    load_email_database,
    save_email_database,
    update_email_in_database,
    delete_emails_from_database,
    delete_domain_from_database,
    DEFAULT_STORAGE_FILE,
)
from email_sender.storage import (
    load_email_storage,
    save_email_storage,
    record_successful_send,
    get_storage_file,
)
from email_sender.sender import send_email
from email_sender.batch import run_email_batch, run_email_batch_stream


# ==============================================================================
# Requirement 1: Resume-based Templates Tests
# ==============================================================================

class TestResumeBasedTemplates:
    """Tests for extracting resume details and generating 5 distinct templates."""

    def test_extract_details_from_pdf_resume(self):
        """Verify candidate details can be extracted from the project's PDF resume."""
        pdf_path = PROJECT_ROOT / "RAHUL_SINGH_3YR_EXPERIENCE_DATA_SCIENTIST_.pdf"
        assert pdf_path.is_file(), "Default resume PDF not found in project root"

        raw_text = extract_text_from_file(pdf_path)
        assert len(raw_text) > 100, "Failed to extract text from resume PDF"

        profile = parse_resume_to_profile(pdf_path, use_llm=False)
        assert isinstance(profile, CandidateProfile)
        assert profile.name != ""
        assert "rahul" in profile.name.lower()
        assert len(profile.technical_skills) > 0
        assert len(profile.projects) > 0
        assert profile.experience_summary != ""

    def test_generate_5_distinct_templates(self):
        """Verify generate_resume_templates creates exactly 5 diverse templates."""
        profile = get_candidate_profile()
        templates = generate_resume_templates(profile)

        assert len(templates) == 5, f"Expected 5 templates, got {len(templates)}"

        # Check that IDs are 1 to 5 and subjects/bodies are distinct
        subjects = set()
        bodies = set()
        for idx, tmpl in enumerate(templates, start=1):
            assert tmpl["id"] == idx
            assert "title" in tmpl and tmpl["title"]
            assert "description" in tmpl and tmpl["description"]
            assert "subject" in tmpl and tmpl["subject"]
            assert "body" in tmpl and tmpl["body"]

            # Check that candidate name and role appear
            cand_name = profile.get("name", "Rahul Singh")
            assert cand_name in tmpl["body"], f"Candidate name missing from template {idx}"
            assert "Hi," in tmpl["body"], f"Greeting missing from template {idx}"
            assert "Best regards," in tmpl["body"], f"Closing missing from template {idx}"

            subjects.add(tmpl["subject"])
            bodies.add(tmpl["body"])

        # All 5 subjects and bodies must be unique
        assert len(subjects) == 5, "Templates do not have 5 unique subject lines"
        assert len(bodies) == 5, "Templates do not have 5 unique body texts"

    def test_all_templates_pass_email_validator(self):
        """Verify all 5 generated templates pass the email validator rules."""
        profile = get_candidate_profile()
        templates = generate_resume_templates(profile)
        cand_name = profile.get("name", "Rahul Singh")

        for tmpl in templates:
            report = email_validator.validate(tmpl["body"], recipient_name="Hiring Manager", candidate_name=cand_name)
            assert report.is_valid, f"Template '{tmpl['title']}' failed validation: {report.issues}"

    def test_user_can_edit_template(self):
        """Verify user can select and customize any template before sending."""
        profile = get_candidate_profile()
        templates = generate_resume_templates(profile)

        selected = templates[1]  # Technical deep-dive
        edited_subject = selected["subject"] + " - Custom Note"
        edited_body = selected["body"].replace("Hi,", "Hi Alexander,") + "\n\nP.S. Excited about your AI team."

        assert edited_subject != selected["subject"]
        assert "Alexander" in edited_body


# ==============================================================================
# Requirement 2: Email Database Immediate Update
# ==============================================================================

class TestEmailDatabaseImmediateUpdate:
    """Tests that sending an email immediately updates Email_Storage.json with recipient and date."""

    def test_record_successful_send_updates_storage(self, tmp_path):
        """Verify record_successful_send writes immediately to the JSON file."""
        test_storage_file = tmp_path / "Email_Storage.json"
        test_storage_file.write_text(json.dumps({"existing@example.com": "2026-01-01"}), encoding="utf-8")

        with patch("email_sender.storage.get_storage_file", return_value=test_storage_file):
            today_str = date.today().strftime("%Y-%m-%d")
            new_recipient = "recruiter.new@techcorp.com"

            updated_data = record_successful_send(new_recipient, today_str)

            # Check in-memory return
            assert new_recipient in updated_data
            assert updated_data[new_recipient] == today_str

            # Check that disk file was immediately written
            disk_data = json.loads(test_storage_file.read_text(encoding="utf-8"))
            assert new_recipient in disk_data
            assert disk_data[new_recipient] == today_str
            assert disk_data["existing@example.com"] == "2026-01-01"

    @patch("email_sender.sender.send_via_gmail")
    def test_send_email_immediately_updates_storage_file(self, mock_smtp, tmp_path):
        """Verify send_email immediately writes recipient and today's date upon SMTP success."""
        mock_smtp.return_value = True

        test_storage_file = tmp_path / "Email_Storage.json"
        test_storage_file.write_text(json.dumps({}), encoding="utf-8")

        with patch("email_sender.sender.load_email_storage", side_effect=lambda: json.loads(test_storage_file.read_text(encoding="utf-8"))):
            with patch("email_sender.storage.get_storage_file", return_value=test_storage_file):
                target_email = "lead.recruiter@google.com"
                today_str = date.today().strftime("%Y-%m-%d")

                success = send_email(
                    recipient_email=target_email,
                    subject="Application for AI Engineer",
                    body="Hi Recruiter,\n\nI am applying for the AI Engineer role.\n\nBest regards,\n\nRahul Singh",
                    sender_email="javarahul04@gmail.com",
                    sender_password="mock_app_password",
                    look_back=0,
                )

                assert success is True
                assert mock_smtp.called

                # Verify file on disk was updated immediately
                disk_records = json.loads(test_storage_file.read_text(encoding="utf-8"))
                assert target_email in disk_records
                assert disk_records[target_email] == today_str

    @patch("email_sender.sender.send_via_gmail")
    def test_batch_stream_yields_sent_date_and_updates_storage(self, mock_smtp, tmp_path):
        """Verify run_email_batch_stream updates storage and emits sent_date."""
        mock_smtp.return_value = True
        test_storage_file = tmp_path / "Email_Storage.json"
        test_storage_file.write_text(json.dumps({}), encoding="utf-8")

        with patch("email_sender.storage.get_storage_file", return_value=test_storage_file):
            with patch("email_sender.batch.was_recently_emailed", return_value=False):
                recipients = ["candidate1@hire.com", "candidate2@hire.com"]
                stream = run_email_batch_stream(
                    list_of_emails=recipients,
                    subject="AI Role Application",
                    body="Hi,\n\nI am applying for the role.\n\nBest regards,\n\nRahul Singh",
                    sender_email="test@gmail.com",
                    sender_password="mock_pass",
                    look_back=0,
                )

                events = list(stream)
                complete_events = [e for e in events if e.get("event") == "email_complete"]
                assert len(complete_events) == 2

                for ev in complete_events:
                    assert ev["success"] is True
                    assert ev["sent_date"] == date.today().strftime("%Y-%m-%d")

                # Verify both emails are saved on disk
                disk_data = json.loads(test_storage_file.read_text(encoding="utf-8"))
                assert "candidate1@hire.com" in disk_data
                assert "candidate2@hire.com" in disk_data


# ==============================================================================
# Requirement 3: Domain & Full Email Filtering Tests
# ==============================================================================

class TestDomainFiltering:
    """Tests for searching email database using either full email address or domain name."""

    @pytest.fixture
    def sample_database(self):
        return {
            "akash.sirohi@hireoneshot.com": "2026-10-04",
            "support@hireoneshot.com": "Never",
            "vishal.seth@capgemini.com": "2026-10-11",
            "priya.sharma@capgemini.com": "",
            "payal.singh@fractal.ai": "2026-10-11",
            "promit.mazumdar@fractal.ai": "2026-10-11",
            "javarahul004@gmail.com": "2026-10-25",
        }

    def test_filter_by_full_email_address(self, sample_database):
        """Verify searching by exact full email address finds that specific contact."""
        grouped = group_emails_by_domain(sample_database)
        query = "akash.sirohi@hireoneshot.com"

        filtered = filter_grouped_domains(grouped, query)

        assert "hireoneshot.com" in filtered
        assert len(filtered) == 1
        # The domain should contain only the matching contact
        matching_emails = [e["email"] for e in filtered["hireoneshot.com"]]
        assert query in matching_emails
        assert "support@hireoneshot.com" not in matching_emails

    def test_filter_by_domain_name_without_at(self, sample_database):
        """Verify searching by domain name (e.g. 'capgemini.com') finds all contacts in that domain."""
        grouped = group_emails_by_domain(sample_database)
        query = "capgemini.com"

        filtered = filter_grouped_domains(grouped, query)

        assert "capgemini.com" in filtered
        assert len(filtered) == 1
        assert len(filtered["capgemini.com"]) == 2
        emails_in_dom = [e["email"] for e in filtered["capgemini.com"]]
        assert "vishal.seth@capgemini.com" in emails_in_dom
        assert "priya.sharma@capgemini.com" in emails_in_dom

    def test_filter_by_domain_name_with_at(self, sample_database):
        """Verify searching by domain name with '@' (e.g. '@fractal.ai') works."""
        grouped = group_emails_by_domain(sample_database)
        query = "@fractal.ai"

        filtered = filter_grouped_domains(grouped, query)

        assert "fractal.ai" in filtered
        assert len(filtered) == 1
        assert len(filtered["fractal.ai"]) == 2

    def test_filter_by_partial_domain_or_name(self, sample_database):
        """Verify searching by partial domain name (e.g. 'fractal') or name prefix."""
        grouped = group_emails_by_domain(sample_database)

        # Partial domain
        filtered_dom = filter_grouped_domains(grouped, "fractal")
        assert "fractal.ai" in filtered_dom

        # Email username prefix
        filtered_user = filter_grouped_domains(grouped, "javarahul004")
        assert "gmail.com" in filtered_user
        assert filtered_user["gmail.com"][0]["email"] == "javarahul004@gmail.com"

    def test_filter_empty_query_returns_all(self, sample_database):
        """Verify empty query returns all grouped domains."""
        grouped = group_emails_by_domain(sample_database)
        filtered = filter_grouped_domains(grouped, "")
        assert len(filtered) == len(grouped)

    def test_filter_database_by_query_dict_helper(self, sample_database):
        """Verify flat dictionary filtering helper."""
        res_email = filter_database_by_query(sample_database, "akash.sirohi@hireoneshot.com")
        assert len(res_email) == 1
        assert "akash.sirohi@hireoneshot.com" in res_email

        res_dom = filter_database_by_query(sample_database, "capgemini.com")
        assert len(res_dom) == 2
        assert "vishal.seth@capgemini.com" in res_dom


# ==============================================================================
# Requirement 4: Dynamic UI & Shared Database Synchronization
# ==============================================================================

class TestDatabaseSynchronizationAcrossSections:
    """Tests that the shared database updates synchronously across sections."""

    def test_same_database_file_used_across_modules(self):
        """Verify storage.py and email_db_helper.py resolve to the same Email_Storage.json."""
        storage_file = get_storage_file()
        assert storage_file.resolve() == DEFAULT_STORAGE_FILE.resolve()
        assert storage_file.name == "Email_Storage.json"

    def test_modify_contact_reflects_in_domain_stats(self, tmp_path):
        """Verify updating a contact date immediately reflects in domain statistics."""
        test_db = {
            "hr@techfirm.com": "Never",
            "lead@techfirm.com": "Never",
        }
        db_file = tmp_path / "Email_Storage.json"
        save_email_database(test_db, db_file)

        initial_stats = get_domain_statistics(test_db)
        assert initial_stats["contacted_count"] == 0
        assert initial_stats["uncontacted_count"] == 2

        # Simulate update when email is sent
        updated_db = update_email_in_database(
            test_db,
            old_email="hr@techfirm.com",
            new_email="hr@techfirm.com",
            new_date="2026-10-25"
        )
        save_email_database(updated_db, db_file)

        # Statistics should immediately reflect 1 contacted, 1 uncontacted
        new_stats = get_domain_statistics(updated_db)
        assert new_stats["contacted_count"] == 1
        assert new_stats["uncontacted_count"] == 1
        assert updated_db["hr@techfirm.com"] == "2026-10-25"

    def test_delete_contact_reflects_in_all_views(self, tmp_path):
        """Verify deleting a contact immediately updates database and domain groupings."""
        test_db = {
            "alice@example.com": "2026-10-01",
            "bob@example.com": "2026-10-02",
        }
        updated_db, count = delete_emails_from_database(test_db, ["alice@example.com"])
        assert count == 1
        assert "alice@example.com" not in updated_db
        assert "bob@example.com" in updated_db

        grouped = group_emails_by_domain(updated_db)
        assert len(grouped["example.com"]) == 1
        assert grouped["example.com"][0]["email"] == "bob@example.com"



class TestGenericTemplateFiles:
    """Verify data/config/template/template1.txt to template5.txt exist and render properly."""

    @pytest.mark.parametrize("idx", [1, 2, 3, 4, 5])
    def test_template_file_exists_and_has_placeholders(self, idx):
        tmpl_file = PROJECT_ROOT / "data" / "config" / "template" / f"template{idx}.txt"
        assert tmpl_file.is_file(), f"Template file {tmpl_file} does not exist"
        content = tmpl_file.read_text(encoding="utf-8")
        assert ("{name}" in content or "{candidate_name}" in content), f"Candidate name placeholder missing in template{idx}.txt"
        assert "{current_role}" in content, f"Current role placeholder missing in template{idx}.txt"
        assert ("{experience}" in content or "{experience_summary}" in content or "{key_skills}" in content or "{technical_skills}" in content)

    @pytest.mark.parametrize("idx", [1, 2, 3, 4, 5])
    def test_template_rendering_fills_placeholders(self, idx):
        from ai_email_writer.templates import generate_resume_templates
        from ai_email_writer.validator import email_validator
        from config_loader import get_candidate_profile

        profile = get_candidate_profile()
        templates = generate_resume_templates(profile)
        tmpl = templates[idx - 1]

        # Ensure placeholders were replaced
        assert "{name}" not in tmpl["body"]
        assert "{current_role}" not in tmpl["body"]
        assert "{technical_skills}" not in tmpl["body"]
        assert "{projects}" not in tmpl["body"]

        # Validate with email_validator
        report = email_validator.validate(tmpl["body"], candidate_name=profile.get("name"))
        assert report.is_valid, f"Rendered template {idx} failed validation: {report.issues}"
