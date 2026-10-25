"""
AI Job Search & Auto-Apply — Streamlit Dashboard & Chat Interface
==================================================================
Run command:
    streamlit run app.py
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime
import json
import pandas as pd
import streamlit as st

# Setup import path for src/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config_loader import (
    get_email_config,
    save_email_config,
    get_model_config,
    save_model_config,
    get_smtp_config,
    get_candidate_profile,
)
from email_db_helper import (
    DEFAULT_STORAGE_FILE,
    DEFAULT_STORAGE_DIR,
    extract_emails_from_text,
    load_email_database,
    save_email_database,
    parse_email_database_content,
    load_database_from_location,
    open_database_file_dialog,
    export_email_database,
    export_and_save_database_files,
    save_email_database_with_timestamp,
    ingest_and_save_emails,
    group_emails_by_domain,
    get_domain_statistics,
    filter_grouped_domains,
    filter_database_by_query,
    delete_emails_from_database,
    delete_domain_from_database,
    update_email_in_database,
    resolve_database_path,
    is_valid_email,
)
from email_sender.storage import (
    load_email_storage,
    save_email_storage,
    record_successful_send,
    get_storage_file,
)
from email_sender.batch import run_email_batch_stream, was_recently_emailed
from ai_email_writer.recipient import get_greeting_name, infer_recipient_name
from ai_email_writer.formatter import enforce_correct_greeting
from ai_email_writer.validator import email_validator
from ai_email_writer.prompts import build_generic_system_prompt, get_active_system_prompt
from ai_email_writer.resume_parser import (
    parse_resume_to_profile,
    save_candidate_profile_config,
    CandidateProfile,
)
from ai_email_writer.templates import (
    generate_resume_templates,
    load_and_render_body_template,
)

# Set page config
st.set_page_config(
    page_title="AI Job Search & Auto-Apply",
    page_icon="📬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for styling
st.markdown("""
<style>
    .main-title { font-size: 2.2rem; font-weight: 700; color: #1E3A8A; margin-bottom: 0.2rem; }
    .sub-title { font-size: 1.02rem; color: #4B5563; margin-bottom: 1.2rem; }
    .badge { background-color: #E0E7FF; color: #3730A3; padding: 4px 10px; border-radius: 9999px; font-weight: 600; font-size: 0.85rem; }
    .card { background-color: #F9FAFB; padding: 1.2rem; border-radius: 10px; border: 1px solid #E5E7EB; margin-bottom: 1rem; }
    .stButton > button { border-radius: 8px; font-weight: 600; }
    .confirm-box { background-color: #FEF2F2; border: 1px solid #F87171; border-radius: 8px; padding: 14px; margin-top: 10px; margin-bottom: 15px; }
    .stream-card { background-color: #F8FAFC; border-left: 4px solid #3B82F6; padding: 12px; margin-bottom: 10px; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session State Initialization (Synchronized Shared Database Across Sections)
# ---------------------------------------------------------------------------
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = [
        {
            "role": "assistant",
            "content": "👋 **Hello! I am your AI Job Application Assistant.**\n\nPlease **select a body_template** on the left or customize your body below to get started with auto-applying to recruiters."
        }
    ]

# 1. Shared Database: Single source of truth across all sections
if "memory_database" not in st.session_state or st.session_state.memory_database is None:
    if DEFAULT_STORAGE_FILE.is_file():
        parsed_db, _ = load_database_from_location(DEFAULT_STORAGE_FILE)
        st.session_state.memory_database = parsed_db or {}
    else:
        st.session_state.memory_database = {}

if "active_db_path" not in st.session_state or not st.session_state.active_db_path:
    st.session_state.active_db_path = str(DEFAULT_STORAGE_FILE)

if "user_loaded_db_path" not in st.session_state or not st.session_state.user_loaded_db_path:
    st.session_state.user_loaded_db_path = str(DEFAULT_STORAGE_FILE)

# State for delete confirmations
if "pending_delete_email" not in st.session_state:
    st.session_state.pending_delete_email = None

if "pending_delete_domain" not in st.session_state:
    st.session_state.pending_delete_domain = None

if "last_ingested_text_cache" not in st.session_state:
    st.session_state.last_ingested_text_cache = ""

# 2. Resume & Candidate Profile Initialization
if "uploaded_resume_path" not in st.session_state:
    cfg = get_email_config()
    resume_name = cfg.get("resume_filename", "RAHUL_SINGH_3YR_EXPERIENCE_DATA_SCIENTIST_.pdf")
    default_resume = PROJECT_ROOT / resume_name
    st.session_state.uploaded_resume_path = str(default_resume) if default_resume.is_file() else None

if "candidate_profile_data" not in st.session_state:
    st.session_state.candidate_profile_data = get_candidate_profile()

if "selected_body_template" not in st.session_state:
    st.session_state.selected_body_template = "template1"

if "body_version" not in st.session_state:
    st.session_state.body_version = 0


def apply_body_template(template_name: str) -> None:
    """Synchronize the selected body template across sidebar, frontend buttons, and generic body."""
    st.session_state.selected_body_template = template_name
    cand_p = st.session_state.get("candidate_profile_data") or get_candidate_profile()
    rendered = load_and_render_body_template(template_name, cand_p)
    if rendered:
        st.session_state.generic_body = rendered
    st.session_state.body_version = st.session_state.get("body_version", 0) + 1


# 3. Synchronized Subject Line and Generic Body
if "subject_line" not in st.session_state:
    cfg = get_email_config()
    cfg_subj = cfg.get("subject", "")
    st.session_state.subject_line = cfg_subj or "AI Engineer | Data Scientist | 3+ Years Experience"

if "generic_body" not in st.session_state or not st.session_state.generic_body:
    cand_p = st.session_state.get("candidate_profile_data") or get_candidate_profile()
    rendered_body = load_and_render_body_template(st.session_state.selected_body_template, cand_p)
    if rendered_body:
        st.session_state.generic_body = rendered_body
    else:
        cfg = get_email_config()
        st.session_state.generic_body = cfg.get("body_template", "")


# Helper to sync updates to shared database
def sync_database_update(email: str, sent_date: str) -> None:
    """Synchronize an email record update across session state and Email_Storage.json on disk."""
    clean_email = email.strip().lower()
    if st.session_state.memory_database is None:
        st.session_state.memory_database = {}
    st.session_state.memory_database[clean_email] = sent_date
    record_successful_send(clean_email, sent_date, custom_path=st.session_state.get("active_db_path"))


# ---------------------------------------------------------------------------
# Sidebar: Settings & Configuration (Left Side)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### ⚙️ Sender & Email Settings")
    email_cfg = get_email_config()
    smtp_cfg = get_smtp_config()
    model_cfg = get_model_config()

    sender_email = st.text_input("Gmail Address", value=email_cfg.get("sender_email", "javarahul04@gmail.com"))
    
    sender_password = st.text_input(
        "Gmail App Password",
        type="password",
        help="16-character Google App Password generated from your Google Account security settings."
    )
    st.markdown(
        """
        🔗 **[Get your Gmail App Password here](https://myaccount.google.com/apppasswords?rapt=AEjHL4OxjMhR8sHJ0zDg_QESBF0hz-FbIdCGL5w8_Z3ANcLxtBpaXoyvsshRYbMjzGsKw8wCMWqG6bWL8TtMHNNUutxlbtvTngrfFjkaeqgP69mxLVTlA14)**
        """,
        unsafe_allow_html=True
    )

    sidebar_subject = st.text_input("Subject Line", value=st.session_state.subject_line, key="sidebar_subject_line")
    if sidebar_subject != st.session_state.subject_line:
        st.session_state.subject_line = sidebar_subject

    col_lb1, col_lb2 = st.columns(2)
    with col_lb1:
        look_back = st.number_input("Look-back", min_value=0, max_value=365, value=int(email_cfg.get("look_back", 1)))
    with col_lb2:
        look_back_format = st.selectbox("Unit", ["months", "days", "years"], index=0)

    # body_template selectbox (just like Unit button)
    template_choices = ["template1", "template2", "template3", "template4", "template5"]
    current_tmpl = st.session_state.get("selected_body_template", "template1")
    current_tmpl_idx = template_choices.index(current_tmpl) if current_tmpl in template_choices else 0

    selected_body_template = st.selectbox(
        "body_template",
        template_choices,
        index=current_tmpl_idx,
        key=f"sidebar_body_template_selector_{current_tmpl}",
        help="Choose a generic template (template1 to template5). Placeholders are automatically replaced with candidate profile details.",
    )

    # Trigger body re-render whenever body_template selection changes
    if selected_body_template != st.session_state.selected_body_template:
        apply_body_template(selected_body_template)
        st.rerun()

    st.markdown("---")
    st.markdown("### 📁 Resume & Storage Files")
    resume_status = "✅ Resume linked" if st.session_state.uploaded_resume_path else "⚠️ Resume not selected"
    st.caption(f"Status: {resume_status}")
    if st.session_state.uploaded_resume_path:
        st.caption(f"Path: `{Path(st.session_state.uploaded_resume_path).name}`")

    active_db_file = Path(st.session_state.active_db_path)
    current_stored_count = len(st.session_state.memory_database) if st.session_state.memory_database else 0
    st.caption(f"Active Shared Database: `{active_db_file.name}` ({current_stored_count} contacts)")
    try:
        st.caption(f"Storage Directory: `{active_db_file.parent.relative_to(PROJECT_ROOT)}`")
    except ValueError:
        st.caption(f"Storage Directory: `{active_db_file.parent}`")


# ---------------------------------------------------------------------------
# Top Header
# ---------------------------------------------------------------------------
st.markdown('<div class="main-title">📬 AI Job Search & Auto-Apply</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Personalized cold outreach with local LLM, automated validator, deduplication, and synchronized database manager.</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Main Tabs
# ---------------------------------------------------------------------------
tab_chat, tab_prompt_inspect, tab_db, tab_domains = st.tabs([
    "💬 Chat & Auto-Email",
    "🔍 Subject, Body & System Prompt",
    "🗄️ Database Manager (Modify & Delete)",
    "🌐 Domain-Wise Email Viewer"
])


# ===========================================================================
# TAB 1: Chat Interface & Auto-Email
# ===========================================================================
with tab_chat:
    st.markdown("### 🤖 Application Assistant")

    # Display conversation messages
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 1. Dedicated Resume Upload & Profile Extractor (Option to view and edit extracted details)
    with st.expander("📄 Upload Resume & Extract Candidate Profile", expanded=True):
        uploaded_resume_file = st.file_uploader(
            "Upload Resume (PDF, Word, or TXT)",
            type=["pdf", "docx", "doc", "txt"],
            key="chat_resume_uploader",
            help="Upload your resume in PDF, Word (.docx, .doc), or Text (.txt) format. Candidate profile details will be extracted and can be reviewed or edited below.",
        )

        if uploaded_resume_file is not None:
            save_dest = PROJECT_ROOT / uploaded_resume_file.name
            with open(save_dest, "wb") as f:
                f.write(uploaded_resume_file.getbuffer())
            st.session_state.uploaded_resume_path = str(save_dest)

            cache_key = f"parsed_{uploaded_resume_file.name}"
            if cache_key not in st.session_state:
                with st.spinner("Extracting candidate profile (Pydantic LLM with Regex Fallback)..."):
                    try:
                        parsed_profile = parse_resume_to_profile(
                            file_path_or_bytes=save_dest,
                            filename=uploaded_resume_file.name,
                            use_llm=True,
                        )
                        saved_cfg = save_candidate_profile_config(parsed_profile)
                        st.session_state[cache_key] = parsed_profile.model_dump()
                        st.session_state.candidate_profile_data = parsed_profile.model_dump()
                        
                        # Re-render current body_template with newly uploaded resume
                        apply_body_template(st.session_state.selected_body_template)

                        method_used = getattr(parsed_profile, "extraction_method", "Regex Fallback")
                        if "LLM" in method_used:
                            st.success(f"🤖 **Profile Extracted via Pydantic LLM** for **{parsed_profile.name}**! Saved to `{saved_cfg.name}`.")
                        else:
                            st.info(f"⚡ **Profile Extracted via Regex Fallback** for **{parsed_profile.name}** (Ollama offline/bypassed). Saved to `{saved_cfg.name}`.")
                    except Exception as err:
                        st.error(f"Error extracting resume profile: {err}")

        # Show extracted candidate profile details & provide option to edit details
        pdata = st.session_state.get("candidate_profile_data") or {}
        if pdata:
            st.markdown("##### 👤 Extracted Candidate Profile Details")
            tab_p_view, tab_p_edit = st.tabs(["👁️ View Profile Details", "✏️ Edit Profile Details"])

            # View Details Tab
            with tab_p_view:
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    st.markdown(f"**Candidate Name:** `{pdata.get('name', 'N/A')}`")
                    st.markdown(f"**Current Role:** `{pdata.get('current_role', 'N/A')}`")
                    st.markdown(f"**Previous Role:** `{pdata.get('previous_role') or 'Associate Data Scientist'}`")
                    st.markdown(f"**Experience:** `{pdata.get('experience_summary', 'N/A')}`")
                    st.caption(f"Extraction Mode: `{pdata.get('extraction_method', 'Auto-Extracted')}`")
                with col_p2:
                    st.markdown(f"**Education:** `{pdata.get('education') or 'B.Tech / Science Degree'}`")
                    skills_list = pdata.get("technical_skills") or []
                    st.markdown(f"**Key Skills Identified:** ({len(skills_list)} items)")
                    if skills_list:
                        sample_skills = ", ".join(s.lstrip("•- ") for s in skills_list[:4])
                        st.caption(f"{sample_skills}...")
                    projects_list = pdata.get("projects") or []
                    st.markdown(f"**Projects Identified:** ({len(projects_list)} items)")
                    if projects_list:
                        sample_projs = "; ".join(p.lstrip("•- ") for p in projects_list[:2])
                        st.caption(f"{sample_projs}")

                with st.expander("🔍 View Complete Extracted Skills & Projects", expanded=False):
                    col_sk, col_pr = st.columns(2)
                    with col_sk:
                        st.markdown("**Technical Skills:**")
                        for s in pdata.get("technical_skills", []):
                            st.markdown(f"- {s.lstrip('•- ')}")
                    with col_pr:
                        st.markdown("**Key Projects:**")
                        for p in pdata.get("projects", []):
                            st.markdown(f"- {p.lstrip('•- ')}")

            # Edit Details Tab
            with tab_p_edit:
                st.caption("You can modify the candidate details extracted from your resume below. Saving will immediately update your candidate profile, template placeholders, and system prompt.")
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    inp_name = st.text_input("Candidate Name:", value=pdata.get("name", ""), key="edit_cand_name")
                    inp_curr_role = st.text_input("Current Role / Title:", value=pdata.get("current_role", ""), key="edit_cand_role")
                    inp_prev_role = st.text_input("Previous Role:", value=pdata.get("previous_role", ""), key="edit_cand_prev_role")
                with col_e2:
                    inp_exp = st.text_input("Experience Summary:", value=pdata.get("experience_summary", ""), key="edit_cand_exp")
                    inp_edu = st.text_input("Education:", value=pdata.get("education", ""), key="edit_cand_edu")

                raw_skills_val = "\n".join(s.lstrip("•- ") for s in pdata.get("technical_skills", []))
                inp_skills = st.text_area("Technical Skills (one per line):", value=raw_skills_val, height=110, key="edit_cand_skills")

                raw_projects_val = "\n".join(p.lstrip("•- ") for p in pdata.get("projects", []))
                inp_projects = st.text_area("Key Projects (one per line):", value=raw_projects_val, height=100, key="edit_cand_projects")

                if st.button("💾 Save Profile Changes", type="primary", key="save_profile_edits_btn"):
                    updated_skills = [s.strip() for s in inp_skills.splitlines() if s.strip()]
                    updated_projects = [p.strip() for p in inp_projects.splitlines() if p.strip()]

                    new_profile = CandidateProfile(
                        name=inp_name.strip(),
                        current_role=inp_curr_role.strip(),
                        previous_role=inp_prev_role.strip(),
                        experience_summary=inp_exp.strip(),
                        education=inp_edu.strip(),
                        technical_skills=updated_skills,
                        projects=updated_projects,
                        extraction_method="User-Edited",
                    )
                    save_candidate_profile_config(new_profile)
                    st.session_state.candidate_profile_data = new_profile.model_dump()
                    
                    # Update body with new placeholders using current selected_body_template
                    apply_body_template(st.session_state.selected_body_template)

                    st.success("✅ Profile changes saved! Body placeholders and system prompt updated with your details.")
                    st.rerun()

    # 2. Database Location & Email Ingestion
    with st.expander("📍 Recipient Database Location & Email Ingestion", expanded=True):
        st.write("Specify your database file location (.json, .csv, .xlsx, .txt) or add emails and job descriptions below.")

        col_db_loc, col_db_paste = st.columns([1, 1])

        # 2.1 Location of the Database File
        with col_db_loc:
            st.markdown("##### 📍 Database File Location & Navigation")

            default_loc_text = st.session_state.user_loaded_db_path or str(DEFAULT_STORAGE_FILE.name)
            db_loc_input = st.text_input(
                "Location of Database File (.txt, .json, .csv, .xlsx):",
                value=default_loc_text,
                placeholder="e.g. Email_Storage.json, Email_Storage.csv, or full path",
                key="chat_db_loc_input",
                help="Enter path or click 'Browse File' below to browse."
            )

            col_btn_nav, col_btn_load, col_btn_reset = st.columns([1, 1, 1])

            # 1. Button to navigate and choose file location using native file explorer dialog
            with col_btn_nav:
                if st.button("🗂️ Browse File", use_container_width=True, help="Open file explorer window to navigate and choose your database file"):
                    chosen_file = open_database_file_dialog()
                    if chosen_file:
                        cand_path = Path(chosen_file).resolve()
                        if cand_path.is_file():
                            if "requirements.txt" in cand_path.name.lower():
                                st.error("❌ 'requirements.txt' is a Python package requirements file, NOT a recipient database. Please choose a valid email database (.json, .csv, .xlsx, .txt).")
                            else:
                                parsed_db, load_msg = load_database_from_location(cand_path)
                                if not parsed_db:
                                    st.warning(f"⚠️ No valid email addresses found in `{cand_path.name}`. Please choose a file containing recipient email addresses.")
                                else:
                                    st.session_state.user_loaded_db_path = str(cand_path)
                                    st.session_state.active_db_path = str(cand_path)
                                    st.session_state.memory_database = parsed_db
                                    st.success(f"✅ Selected `{cand_path.name}`! {load_msg} into memory.")
                                    st.rerun()

            # 2. Button to load directly from the typed/specified location into memory
            with col_btn_load:
                load_btn_clicked = st.button("📂 Load Location", type="primary", use_container_width=True, help="Load recipient emails from this location into memory")

            # 3. Button to reset back to default Email_Storage.json
            with col_btn_reset:
                if st.button("🔄 Reset to Default DB", use_container_width=True, help="Reset back to default Email_Storage.json"):
                    st.session_state.user_loaded_db_path = str(DEFAULT_STORAGE_FILE)
                    st.session_state.active_db_path = str(DEFAULT_STORAGE_FILE)
                    if DEFAULT_STORAGE_FILE.is_file():
                        parsed_db, _ = load_database_from_location(DEFAULT_STORAGE_FILE)
                        st.session_state.memory_database = parsed_db
                    st.success(f"✅ Reset back to `{DEFAULT_STORAGE_FILE.name}`.")
                    st.rerun()

            # 4. Browser-native file navigation chooser
            uploaded_nav_file = st.file_uploader(
                "Or navigate & choose file via browser:",
                type=["txt", "json", "csv", "xlsx", "xls"],
                key="chat_db_file_nav_picker",
                help="Click 'Browse files' to navigate through your folders and choose your recipient database file."
            )

            if uploaded_nav_file is not None:
                if "requirements.txt" in uploaded_nav_file.name.lower():
                    st.error("❌ 'requirements.txt' is a Python package requirements file, NOT an email recipient database. Please choose a file containing recipient emails.")
                else:
                    save_path = PROJECT_ROOT / uploaded_nav_file.name
                    with open(save_path, "wb") as f:
                        f.write(uploaded_nav_file.getbuffer())
                    parsed_db, load_msg = load_database_from_location(save_path)
                    if not parsed_db:
                        st.warning(f"⚠️ No email addresses found in `{uploaded_nav_file.name}`. The file must contain valid recipient email addresses.")
                    else:
                        st.session_state.user_loaded_db_path = str(save_path)
                        st.session_state.active_db_path = str(save_path)
                        st.session_state.memory_database = parsed_db
                        st.success(f"✅ Chosen `{uploaded_nav_file.name}`! Loaded {len(parsed_db)} emails into memory.")

            # Execute loading when "📂 Load Location" is clicked
            if load_btn_clicked:
                clean_input = db_loc_input.strip() if db_loc_input else ""
                if "requirements.txt" in clean_input.lower():
                    st.error("❌ 'requirements.txt' is a Python package requirements file, NOT an email recipient database. Please specify a valid database file (.json, .csv, .xlsx, .txt).")
                else:
                    cand_path = resolve_database_path(clean_input if clean_input else None)
                    if cand_path.is_file():
                        parsed_db, load_msg = load_database_from_location(cand_path)
                        if not parsed_db:
                            st.warning(f"⚠️ No valid email addresses found in `{cand_path.name}`. Please specify a file with email contacts.")
                        else:
                            st.session_state.memory_database = parsed_db
                            st.session_state.user_loaded_db_path = str(cand_path)
                            st.session_state.active_db_path = str(cand_path)
                            st.success(f"✅ {load_msg}! Emails are now loaded into memory ready for sending.")
                            st.rerun()
                    else:
                        st.error(f"❌ File not found at `{cand_path}`. Please verify the location path.")

            # Display currently loaded state in memory
            if st.session_state.get("memory_database"):
                mem_db = st.session_state.memory_database
                loaded_file_obj = Path(st.session_state.user_loaded_db_path or st.session_state.active_db_path)
                st.caption(f"🧠 **In-Memory Ready:** `{loaded_file_obj.name}` ({len(mem_db)} emails loaded)")
                if hasattr(st, "popover"):
                    with st.popover(f"👁️ View {len(mem_db)} Emails Loaded in Memory", use_container_width=True):
                        st.code("\n".join(mem_db.keys()), language="text")
                else:
                    if st.checkbox(f"👁️ View {len(mem_db)} Emails Loaded in Memory", value=False, key="chat_view_loaded_emails_chk"):
                        st.code("\n".join(mem_db.keys()), language="text")
            elif st.session_state.user_loaded_db_path:
                cand_path = resolve_database_path(st.session_state.user_loaded_db_path)
                if cand_path.is_file() and "requirements.txt" not in cand_path.name.lower():
                    parsed_db, _ = load_database_from_location(cand_path)
                    if parsed_db:
                        st.session_state.memory_database = parsed_db
                        st.caption(f"🧠 **In-Memory Ready:** `{cand_path.name}` ({len(parsed_db)} emails loaded)")
            else:
                st.caption("ℹ️ Click **'🗂️ Browse File'** or **'📂 Load Location'** to load recipient emails into memory.")


        # 2.2 Box: Add Email(s) / Paste Job Description Script
        with col_db_paste:
            st.markdown("##### ✍️ Add Email(s) / Paste Job Description Script")
            quick_script_input = st.text_area(
                "Add Email(s) / Paste Job Description Script:",
                placeholder="Paste single email, multiple emails, strings, or job posting scripts with emails...",
                height=130,
                key="chat_quick_script_box",
            )
            col_add_btn, _ = st.columns([2, 1])
            with col_add_btn:
                extract_btn_clicked = st.button("➕ Extract & Add to Database", type="primary", use_container_width=True)

            if extract_btn_clicked or (quick_script_input.strip() and quick_script_input.strip() != st.session_state.last_ingested_text_cache):
                if quick_script_input.strip():
                    with st.spinner("Extracting emails, creating backup in same location, and updating database..."):
                        target_loc_str = st.session_state.user_loaded_db_path or db_loc_input or str(DEFAULT_STORAGE_FILE)
                        target_db_dest = resolve_database_path(target_loc_str)
                        res = ingest_and_save_emails(
                            raw_input=quick_script_input.strip(),
                            custom_save_path=target_db_dest,
                            create_timestamped_backup=True,
                        )
                        st.session_state.last_ingested_text_cache = quick_script_input.strip()

                        # Update memory immediately with the updated database
                        if "updated_db" in res:
                            st.session_state.memory_database = res["updated_db"]
                            st.session_state.user_loaded_db_path = str(target_db_dest)
                            st.session_state.active_db_path = str(target_db_dest)

                        if res["valid_scraped"] > 0:
                            backup_name = Path(res['timestamped_file']).name if res['timestamped_file'] else ""
                            backup_info = f" | Backup saved in same directory: `{backup_name}`" if backup_name else ""
                            st.success(f"✅ Extracted **{res['valid_scraped']}** valid emails! Added **{res['added_count']}** new unique addresses into `{target_db_dest.name}` (Total in DB: **{res['total_in_db']}**){backup_info}.")
                        else:
                            st.info("No valid email addresses found in the input text.")

        # Export & Download Section
        st.markdown("###### 💾 Export & Download Current Database:")
        active_target_loc = st.session_state.user_loaded_db_path or str(DEFAULT_STORAGE_FILE)
        active_path_obj = resolve_database_path(active_target_loc)
        current_db_records = st.session_state.memory_database if st.session_state.get("memory_database") else load_email_database(active_path_obj)
        db_dir = active_path_obj.parent
        db_dir.mkdir(parents=True, exist_ok=True)

        col_save_auto, _ = st.columns([3, 1])
        with col_save_auto:
            if st.button("💾 Save Export Snapshots & Backup to Directory", help="Saves Email_Storage (.csv, .xlsx, .txt, .json) and timestamped backup Email_Storage_<date>_<time>.json in the same database directory without asking."):
                saved_exports = export_and_save_database_files(
                    data=current_db_records,
                    target_dir=db_dir,
                    formats=["csv", "xlsx", "txt", "json"],
                )
                backup_name = saved_exports.get("backup").name if "backup" in saved_exports else "backup"
                st.success(f"✅ Saved exported snapshots and backup `{backup_name}` directly to `{db_dir}` without asking!")

        col_exp1, col_exp2, col_exp3, col_exp4 = st.columns(4)

        with col_exp1:
            csv_bytes = export_email_database(current_db_records, "csv")
            if st.download_button("📥 Download / Save CSV", data=csv_bytes, file_name="Email_Storage.csv", mime="text/csv", use_container_width=True):
                export_and_save_database_files(current_db_records, target_dir=db_dir, formats=["csv"])
        with col_exp2:
            xlsx_bytes = export_email_database(current_db_records, "xlsx")
            if st.download_button("📥 Download / Save Excel", data=xlsx_bytes, file_name="Email_Storage.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True):
                export_and_save_database_files(current_db_records, target_dir=db_dir, formats=["xlsx"])
        with col_exp3:
            txt_bytes = export_email_database(current_db_records, "txt")
            if st.download_button("📥 Download / Save TXT", data=txt_bytes, file_name="Email_Storage.txt", mime="text/plain", use_container_width=True):
                export_and_save_database_files(current_db_records, target_dir=db_dir, formats=["txt"])
        with col_exp4:
            json_bytes = export_email_database(current_db_records, "json")
            if st.download_button("📥 Download / Save JSON", data=json_bytes, file_name="Email_Storage.json", mime="application/json", use_container_width=True):
                export_and_save_database_files(current_db_records, target_dir=db_dir, formats=["json"])

    st.markdown("---")

    # 3. Outreach Message Body (Dynamically synchronized with body_template & candidate profile)
    st.markdown("#### 📝 Outreach Message Body")

    # Dynamic template switcher right above "Add a generic body"
    st.caption("Select template (dynamically synchronized with sidebar and profile placeholders):")
    tmpl_cols = st.columns(5)
    for i, t_name in enumerate(["template1", "template2", "template3", "template4", "template5"]):
        with tmpl_cols[i]:
            is_active = (t_name == st.session_state.selected_body_template)
            btn_type = "primary" if is_active else "secondary"
            if st.button(f"📄 {t_name}", key=f"tab1_btn_{t_name}", type=btn_type, use_container_width=True):
                apply_body_template(t_name)
                st.rerun()

    text_area_key = f"tab1_user_body_input_v{st.session_state.get('body_version', 0)}"
    user_body_input = st.text_area(
        label="Add a generic body",
        value=st.session_state.generic_body,
        placeholder="Add or edit your outreach body...",
        height=220,
        key=text_area_key,
        help="This body will be sent to recruiters (or further personalized by the local LLM if online). You can edit any part of it before sending.",
    )

    if user_body_input != st.session_state.generic_body:
        st.session_state.generic_body = user_body_input

    # Preview & Target Selection Logic (Synchronized with Shared Database)
    db_contacts = st.session_state.memory_database or {}
    db_source_name = Path(st.session_state.user_loaded_db_path or DEFAULT_STORAGE_FILE).name

    cached_pasted = quick_script_input.strip() if quick_script_input else st.session_state.get("last_ingested_text_cache", "")
    pasted_contacts = sorted(list(set(extract_emails_from_text(cached_pasted)))) if cached_pasted else []

    # Dynamic source selector in the frontend
    if db_contacts and pasted_contacts:
        col_src, _ = st.columns([2, 1])
        with col_src:
            chosen_source = st.radio(
                "🎯 Target Recipient Source:",
                [
                    f"Database: {db_source_name} ({len(db_contacts)} emails)",
                    f"Pasted Text ({len(pasted_contacts)} emails)",
                ],
                horizontal=True,
                key="chat_target_source_radio"
            )
        if "Database" in chosen_source:
            current_target_emails = list(db_contacts.keys())
            target_mode_desc = f"database `{db_source_name}`"
        else:
            current_target_emails = pasted_contacts
            target_mode_desc = "pasted job description / email section"
    elif db_contacts:
        current_target_emails = list(db_contacts.keys())
        target_mode_desc = f"database `{db_source_name}`"
    elif pasted_contacts:
        current_target_emails = pasted_contacts
        target_mode_desc = "pasted job description / email section"
    else:
        current_target_emails = []
        target_mode_desc = "no recipient emails found"

    total_recipients = len(current_target_emails)

    col_send1, col_send2 = st.columns([3, 1])
    with col_send1:
        st.caption(f"Currently targeting **{total_recipients}** recipient email(s) from **{target_mode_desc}**.")

    with col_send2:
        send_btn = st.button("🚀 Send Automatic Email", type="primary", use_container_width=True)

    # 4. Streaming Execution when "Send Automatic Email" is clicked
    if send_btn:
        recipients_list = current_target_emails
        send_source_label = target_mode_desc
        active_subject = st.session_state.subject_line
        active_body = st.session_state.generic_body

        if not sender_email or not sender_password:
            st.error("Please provide both your **Gmail Address** and **App Password** in the sidebar.")
        elif not active_body.strip():
            st.error("Please enter or select an email body template before sending.")
        elif not st.session_state.uploaded_resume_path or not Path(st.session_state.uploaded_resume_path).is_file():
            st.error("Please upload or select a valid resume file (PDF, Word, or TXT).")
        elif not recipients_list:
            st.error("No recipient emails found! Please paste emails in the box above or load a valid database file (.json, .csv, .xlsx, .txt).")
        else:
            st.session_state.chat_messages.append({
                "role": "user",
                "content": f"🚀 **Start Automatic Outreach** | Target: {len(recipients_list)} emails ({send_source_label}) | Subject: *'{active_subject}'*"
            })

            # Real-time streaming output container
            stream_container = st.container()

            with stream_container:
                st.markdown("### 📡 Live Outreach Streaming Progress")
                progress_bar = st.progress(0.0)
                metrics_placeholder = st.empty()
                active_card_placeholder = st.empty()
                log_table_placeholder = st.empty()

                # Get custom system prompt if set
                custom_sys_prompt = model_cfg.get("system_prompt", "")

                try:
                    stream_generator = run_email_batch_stream(
                        list_of_emails=recipients_list,
                        subject=active_subject,
                        body=active_body,
                        sender_email=sender_email,
                        sender_password=sender_password,
                        attachments=st.session_state.uploaded_resume_path,
                        look_back=look_back,
                        look_back_format=look_back_format,
                        system_prompt=custom_sys_prompt,
                        custom_db_path=st.session_state.get("active_db_path"),
                    )

                    curr_state = {}
                    processed_log = []
                    sent_total = 0
                    failed_total = 0

                    def _render_active_card(placeholder, s):
                        if not s:
                            return
                        with placeholder.container():
                            st.markdown("---")
                            st.markdown(f"#### 🔄 [{s['index']}/{s['total']}] Processing email: `{s['email']}`")
                            st.markdown(f"**From**: `{s['sender']}` ➡️ **To**: `{s['email']}` | **Subject**: *'{s['subject']}'*")
                            
                            with st.expander("📄 This is the template body", expanded=False):
                                st.text(s["gen_body"])

                            mode = s.get("mode")
                            if mode == "llm_success":
                                st.success(f"🤖 **Personalized by AI for recipient!** Subject: *'{s['subject']}'*")
                                with st.expander("📄 This is the personalized body", expanded=True):
                                    st.text(s["ai_body"])
                            elif mode == "llm_unavailable":
                                reason = s.get("reason", "No LLM detected")
                                st.warning(f"⚠️ **Oops, sorry! No LLM detected.** ({reason})\n\nSwitching to the template body...")
                                with st.expander("📄 This is the body (Fallback)", expanded=True):
                                    st.text(s["ai_body"])
                            elif mode == "llm_incomplete_fallback":
                                reason = s.get("reason", "Incomplete email detected")
                                st.warning(f"⚠️ **Incomplete / Defective email detected.** ({reason})\n\nApplying robust fallback: Switching to template body with personalized salutation & closing.")
                                with st.expander("📄 This is the body (Fallback Applied)", expanded=True):
                                    st.text(s["ai_body"])

                            status = s.get("status")
                            if status == "sending":
                                st.caption(f"📤 Sending email to `{s['email']}`...")
                            elif status == "sent":
                                st.success(f"✅ **Email sent successfully to `{s['email']}`! Immediately updated Email_Storage.json.**")
                                st.write(f"⏳ **Remaining email(s) left:** `{s.get('remaining', 0)}`")
                            elif status and status.startswith("failed"):
                                st.error(f"❌ **Failed to send email to `{s['email']}` ({status}).**")
                                st.write(f"⏳ **Remaining email(s) left:** `{s.get('remaining', 0)}`")

                    for event in stream_generator:
                        ev_type = event.get("event")

                        # 1) Database overview
                        if ev_type == "init":
                            t_db = event["total_emails_in_db"]
                            sent_cnt = event["already_sent_count"]
                            rem_cnt = event["remaining_to_send"]
                            lb_val = event["look_back"]
                            lb_unit = event["look_back_format"]

                            st.info(f"""
📊 **1. In your database you have `{t_db}` email(s).**  
⏱️ **2. From the last `{lb_val} {lb_unit}` you have already sent `{sent_cnt}` email(s).**  
📬 **3. Remaining email(s) to process: `{rem_cnt}`.**
""")
                            if rem_cnt == 0:
                                st.warning("All recipients have been recently contacted within your look-back period. No new emails to dispatch.")
                                break

                        # 2) Email start
                        elif ev_type == "email_start":
                            idx = event["index"]
                            tot = event["total"]
                            e_target = event["email"]
                            gen_body = event["generic_body"]
                            gen_subj = event["generic_subject"]
                            s_from = event["sender_email"]

                            curr_state = {
                                "index": idx,
                                "total": tot,
                                "email": e_target,
                                "sender": s_from,
                                "subject": gen_subj,
                                "gen_body": gen_body,
                                "ai_body": None,
                                "mode": None,
                                "reason": None,
                                "status": "generating",
                                "remaining": tot - idx,
                            }
                            _render_active_card(active_card_placeholder, curr_state)

                        # 3) LLM Success
                        elif ev_type == "llm_success":
                            curr_state["subject"] = event["subject"]
                            curr_state["ai_body"] = event["body"]
                            curr_state["mode"] = "llm_success"
                            _render_active_card(active_card_placeholder, curr_state)

                        # 4) Oops no LLM detected / Fallback
                        elif ev_type == "llm_unavailable":
                            curr_state["subject"] = event["subject"]
                            curr_state["ai_body"] = event["body"]
                            curr_state["mode"] = "llm_unavailable"
                            curr_state["reason"] = event.get("reason", "No LLM detected")
                            _render_active_card(active_card_placeholder, curr_state)

                        elif ev_type == "llm_incomplete_fallback":
                            curr_state["subject"] = event["subject"]
                            curr_state["ai_body"] = event["body"]
                            curr_state["mode"] = "llm_incomplete_fallback"
                            curr_state["reason"] = event.get("reason", "Incomplete email detected")
                            _render_active_card(active_card_placeholder, curr_state)

                        # 5) Sending
                        elif ev_type == "sending":
                            curr_state["status"] = "sending"
                            _render_active_card(active_card_placeholder, curr_state)

                        # 6) Email Complete
                        elif ev_type == "email_complete":
                            idx = event["index"]
                            tot = event["total"]
                            rem_left = event["remaining_emails_left"]
                            status = event["status"]
                            is_succ = event["success"]
                            target_e = event["email"]

                            progress_bar.progress(idx / tot)
                            if is_succ:
                                sent_total += 1
                                curr_state["status"] = "sent"
                                sent_date_val = event.get("sent_date") or datetime.now().strftime("%Y-%m-%d")
                                
                                # Immediately update shared database in memory and on disk
                                sync_database_update(target_e, sent_date_val)
                            else:
                                failed_total += 1
                                curr_state["status"] = f"failed: {status}"

                            curr_state["remaining"] = rem_left
                            _render_active_card(active_card_placeholder, curr_state)

                            # Record in live audit log
                            mode_label = "🤖 AI Personalized" if curr_state.get("mode") == "llm_success" else "📄 Template Fallback"
                            processed_log.append({
                                "#": idx,
                                "Recipient Email": target_e,
                                "Subject": curr_state.get("subject", active_subject),
                                "Status": "✅ Sent" if is_succ else f"❌ {status}",
                                "Mode": mode_label,
                            })

                            # Update metrics row
                            metrics_placeholder.markdown(
                                f"**Processed:** `{idx}/{tot}` | **Sent:** `{sent_total}` | **Failed:** `{failed_total}` | **Remaining:** `{rem_left}`"
                            )

                            # Update live audit log table
                            log_df = pd.DataFrame(processed_log)
                            log_table_placeholder.dataframe(log_df, use_container_width=True, height=220)

                        # 7) Batch Complete
                        elif ev_type == "batch_complete":
                            s_cnt = event["sent_count"]
                            sk_cnt = event["skipped_count"]
                            f_cnt = event["failed_count"]
                            tot_p = len(event["results"])

                            summary_msg = f"""
### 🎉 Batch Outreach Finished!
- **Total Processed**: `{tot_p}`
- **Successfully Sent**: `{s_cnt}`
- **Skipped (Already Contacted)**: `{sk_cnt}`
- **Failed**: `{f_cnt}`
- **Database Status**: `Email_Storage.json` synchronized immediately!
"""
                            st.balloons()
                            st.markdown(summary_msg)
                            st.session_state.chat_messages.append({
                                "role": "assistant",
                                "content": summary_msg
                            })

                except Exception as e:
                    st.error(f"Batch execution error: {e}")
                    st.session_state.chat_messages.append({"role": "assistant", "content": f"❌ Error: {e}"})


# ===========================================================================
# TAB 2: Dynamic Subject, Body & System Prompt Inspector
# ===========================================================================
with tab_prompt_inspect:
    st.markdown("### 🔍 Subject, Body & Dynamic System Prompt")
    st.write("Inspect and dynamically configure the outreach subject, selected template body, and the system prompt governing your local reasoning model.")

    col_chk1, col_chk2 = st.columns(2)

    # 1. Subject Line Check (Synchronized with current subject)
    with col_chk1:
        st.markdown("#### 1️⃣ Dynamic Subject Line")
        active_subj = st.session_state.subject_line
        st.markdown(f"**Current Subject Line:** `{active_subj}`")
        s_len = len(active_subj.strip())
        s_words = len(active_subj.strip().split())

        if s_len == 0:
            st.error("❌ Subject line is empty.")
        elif s_len < 15:
            st.warning(f"⚠️ Subject line is short ({s_len} chars). Include role and key strengths.")
        elif s_len > 60:
            st.info(f"ℹ️ Subject length is {s_len} chars. On mobile email clients, subject lines over 60 characters may be truncated.")
        else:
            st.success(f"✅ Subject line length is optimal ({s_len} chars, {s_words} words).")

    # 2. General Body Quality Check (Synchronized with current body)
    with col_chk2:
        st.markdown("#### 2️⃣ Body Quality Validation")
        curr_body = st.session_state.generic_body
        body_words = len(curr_body.strip().split())
        cand_name = (st.session_state.get("candidate_profile_data") or {}).get("name", "Rahul Singh")
        body_report = email_validator.validate(curr_body, recipient_name="Recruiter", candidate_name=cand_name)

        if body_report.is_valid:
            st.success(f"✅ Current body passed quality check ({body_words} words). Has proper greeting, closing, and candidate signature.")
        else:
            st.warning(f"⚠️ Current body validation notes ({body_words} words):")
            for issue in body_report.issues:
                st.write(f"- {issue}")

    st.markdown("---")

    # 3. Sender and Receiver Email Only (Synchronized with Shared Database)
    st.markdown("#### 📬 Sender & Receiver Email Details")

    shared_db = st.session_state.memory_database or {}
    current_rec_list = list(shared_db.keys())
    rec_source_tag = f"from shared database `Email_Storage.json` ({len(current_rec_list)} contacts)"

    col_sr1, col_sr2 = st.columns(2)
    with col_sr1:
        st.markdown(f"**Sender Email:** `{sender_email or 'Not configured'}`")
    with col_sr2:
        if current_rec_list:
            st.markdown(f"**Receiver Email(s) ({len(current_rec_list)} total, {rec_source_tag}):**")
            st.code("\n".join(current_rec_list), language="text")
        else:
            st.markdown(f"**Receiver Email(s):** *None ({rec_source_tag})*")

    st.markdown("---")

    # 4. Dynamic System Prompt with candidate_profile.json Access
    st.markdown("#### 3️⃣ System Prompt for Local LLM (DeepSeek-R1 / Ollama)")
    st.write("If no custom prompt is supplied, the system automatically uses the **Generic System Prompt** generated dynamically from `candidate_profile.json`.")

    generic_prompt_dynamic = build_generic_system_prompt()
    saved_sys_prompt = model_cfg.get("system_prompt", "")

    col_p_opts1, col_p_opts2 = st.columns([3, 1])
    with col_p_opts2:
        if st.button("🔄 Reset to Generic Prompt", use_container_width=True):
            saved_sys_prompt = generic_prompt_dynamic
            model_cfg["system_prompt"] = generic_prompt_dynamic
            save_model_config(model_cfg)
            st.rerun()

    active_prompt_display = saved_sys_prompt if saved_sys_prompt.strip() else generic_prompt_dynamic

    edited_sys_prompt = st.text_area(
        "Active System Prompt (Editable with direct candidate profile integration):",
        value=active_prompt_display,
        height=340,
        key="edit_system_prompt_area",
        help="Instructs the LLM on respectful tone, double newlines (\\n\\n) between paragraphs, bullet points (•) for skills, and zero bracketed placeholders."
    )

    col_pr1, col_pr2 = st.columns([3, 1])
    with col_pr2:
        if st.button("💾 Save System Prompt", type="primary", use_container_width=True):
            model_cfg["system_prompt"] = edited_sys_prompt.strip()
            save_model_config(model_cfg)
            st.success("✅ System prompt updated in `model_config.json`!")


# ===========================================================================
# TAB 3: Database Manager (Modify & Delete - Synchronized with Shared Database)
# ===========================================================================
with tab_db:
    st.markdown("### 🗄️ Database Manager — Modify & Delete")

    # Use the shared database as single source of truth across all sections
    active_db = st.session_state.memory_database or {}
    active_db_target = Path(st.session_state.user_loaded_db_path or DEFAULT_STORAGE_FILE)
    st.info(f"📂 Currently managing shared database: `{DEFAULT_STORAGE_FILE.name}` ({len(active_db)} contacts)")

    all_emails = list(active_db.keys())
    col_mod, col_del = st.columns(2)

    # 1. Modify Existing Record
    with col_mod:
        st.markdown("#### ✏️ Modify Contact Record")
        if not all_emails:
            st.info("Shared database is currently empty.")
        else:
            selected_edit_email = st.selectbox("Select email to modify:", options=all_emails, key="mod_select_email")
            current_date_val = active_db.get(selected_edit_email, "")

            new_email_val = st.text_input("Email Address:", value=selected_edit_email, key="mod_email_val")
            new_date_val = st.text_input("Last Contacted Date (YYYY-MM-DD or leave blank):", value=current_date_val, key="mod_date_val")

            if st.button("💾 Update Contact in Database", key="mod_save_btn", type="primary"):
                if not is_valid_email(new_email_val):
                    st.error("Please enter a valid email address.")
                else:
                    updated_db = update_email_in_database(
                        active_db,
                        old_email=selected_edit_email,
                        new_email=new_email_val,
                        new_date=new_date_val,
                    )
                    # Save immediately to Email_Storage.json and update session state
                    save_email_database(updated_db, DEFAULT_STORAGE_FILE)
                    if active_db_target.resolve() != DEFAULT_STORAGE_FILE.resolve():
                        save_email_database(updated_db, active_db_target)
                    st.session_state.memory_database = updated_db
                    st.success(f"Contact updated successfully in `{DEFAULT_STORAGE_FILE.name}`!")
                    st.rerun()

    # 2. Delete Record(s)
    with col_del:
        st.markdown("#### 🗑️ Delete Contact Record(s)")
        if not all_emails:
            st.info("No records to delete.")
        else:
            selected_to_delete = st.multiselect(
                "Select email(s) to remove:",
                options=all_emails,
                key="del_multiselect"
            )

            delete_scrape_text = st.text_area(
                "Or paste text/script to scrape and remove matching emails:",
                placeholder="Paste emails or text containing addresses you want removed...",
                height=90,
                key="del_text_area",
            )

            if st.button("🗑️ Delete Selected Contacts", type="secondary", key="del_action_btn"):
                targets = set(selected_to_delete)
                if delete_scrape_text.strip():
                    targets.update(extract_emails_from_text(delete_scrape_text))

                if not targets:
                    st.warning("No emails selected or found in text to delete.")
                else:
                    updated_db, count_deleted = delete_emails_from_database(active_db, list(targets))
                    # Save immediately to Email_Storage.json and update session state
                    save_email_database(updated_db, DEFAULT_STORAGE_FILE)
                    if active_db_target.resolve() != DEFAULT_STORAGE_FILE.resolve():
                        save_email_database(updated_db, active_db_target)
                    st.session_state.memory_database = updated_db
                    st.success(f"Deleted **{count_deleted}** contact(s) from `{DEFAULT_STORAGE_FILE.name}`.")
                    st.rerun()

    st.markdown("---")
    st.markdown(f"#### 📋 Current Shared Database Table: `{DEFAULT_STORAGE_FILE.name}`")
    if active_db:
        df_display = pd.DataFrame([
            {"#": i + 1, "Email": k, "Domain": k.split("@")[-1] if "@" in k else "unknown", "Last Contacted Date": v or "Never Contacted"}
            for i, (k, v) in enumerate(active_db.items())
        ])
        st.dataframe(df_display, use_container_width=True, height=280)
    else:
        st.info("The database is currently empty.")


# ===========================================================================
# TAB 4: Domain-Wise Email Viewer (Search by full email or domain)
# ===========================================================================
with tab_domains:
    st.markdown("### 🌐 Domain-Wise Email Viewer & Advanced Analytics")
    st.write("Analyze and manage your recruiter network grouped by company domain. Synchronized in real-time with `Email_Storage.json`.")

    # Synchronized with shared database
    db_for_domains = st.session_state.memory_database or {}

    if not db_for_domains:
        st.info("ℹ️ No emails in database. Please add emails or load a database file in Tab 1.")
    else:
        stats = get_domain_statistics(db_for_domains)
        grouped = stats["grouped"]

        # 1. Advanced Metrics Row
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Total Stored Emails", stats["total_emails"])
        col_m2.metric("Total Unique Domains", stats["total_domains"])
        col_m3.metric("Contacted", stats["contacted_count"])
        col_m4.metric("Pending / Never Contacted", stats["uncontacted_count"])

        # 2. Domain & Email Search
        st.markdown("#### 🔍 Filter & Domain Operations")
        col_d_search, col_d_export = st.columns([3, 2])

        with col_d_search:
            search_query = st.text_input(
                "Filter by email address or domain name:",
                placeholder="e.g. akash.sirohi@hireoneshot.com, capgemini.com, @fractal.ai, or name",
                key="domain_filter_bar",
                help="Search by full email address, username/prefix, domain name, or domain with @"
            )

        with col_d_export:
            all_domain_csv = export_email_database(db_for_domains, "csv")
            st.download_button("📥 Export All Domains (CSV)", data=all_domain_csv, file_name="domains_all.csv", mime="text/csv")

        # 3. Confirmation Dialog for Individual Contact Deletion
        if st.session_state.pending_delete_email:
            target_del = st.session_state.pending_delete_email
            st.markdown(f"""
            <div class="confirm-box">
                <span style="font-weight:700; color:#B91C1C;">⚠️ SECOND-CHECK CONFIRMATION REQUIRED:</span><br/>
                Are you sure you want to permanently delete <code>{target_del}</code> from the database?
            </div>
            """, unsafe_allow_html=True)
            col_c1, col_c2, _ = st.columns([1, 1, 4])
            with col_c1:
                if st.button("✅ Yes, Delete Permanently", type="primary", key="confirm_del_btn"):
                    updated_db, count = delete_emails_from_database(db_for_domains, [target_del])
                    save_email_database(updated_db, DEFAULT_STORAGE_FILE)
                    st.session_state.memory_database = updated_db
                    st.session_state.pending_delete_email = None
                    st.success(f"Deleted `{target_del}` successfully!")
                    st.rerun()
            with col_c2:
                if st.button("❌ Cancel", key="cancel_del_btn"):
                    st.session_state.pending_delete_email = None
                    st.rerun()

        # 4. Confirmation Dialog for Bulk Domain Deletion
        if st.session_state.pending_delete_domain:
            target_del_dom = st.session_state.pending_delete_domain
            dom_count = len(grouped.get(target_del_dom, []))
            st.markdown(f"""
            <div class="confirm-box">
                <span style="font-weight:700; color:#B91C1C;">⚠️ BULK DELETE CONFIRMATION:</span><br/>
                Are you sure you want to permanently delete ALL <b>{dom_count}</b> contact(s) under <code>@{target_del_dom}</code>?
            </div>
            """, unsafe_allow_html=True)
            col_dc1, col_dc2, _ = st.columns([1, 1, 4])
            with col_dc1:
                if st.button("✅ Yes, Delete Entire Domain", type="primary", key="confirm_del_dom_btn"):
                    updated_db, count = delete_domain_from_database(db_for_domains, target_del_dom)
                    save_email_database(updated_db, DEFAULT_STORAGE_FILE)
                    st.session_state.memory_database = updated_db
                    st.session_state.pending_delete_domain = None
                    st.success(f"Deleted {count} contacts from `@{target_del_dom}`!")
                    st.rerun()
            with col_dc2:
                if st.button("❌ Cancel Domain Delete", key="cancel_del_dom_btn"):
                    st.session_state.pending_delete_domain = None
                    st.rerun()

        st.markdown("---")
        st.markdown("#### 🏢 Company Domains")

        # 5. Filter domains using filter_grouped_domains
        filtered_domains = filter_grouped_domains(grouped, search_query)

        if search_query.strip():
            matched_emails_total = sum(len(elst) for elst in filtered_domains.values())
            st.info(f"🔍 Search results for **'{search_query.strip()}'**: Found **{len(filtered_domains)}** matching domain(s) and **{matched_emails_total}** matching email(s).")

        if not filtered_domains:
            st.info("No email addresses or domains match your search query.")
        else:
            for domain, emails in filtered_domains.items():
                contacted_in_dom = sum(1 for e in emails if e["last_sent"] != "Never")
                with st.expander(f"🏢 **@{domain}** — ({len(emails)} contact{'s' if len(emails) != 1 else ''} | {contacted_in_dom} contacted)"):
                    
                    # Domain actions toolbar
                    col_dt1, col_dt2 = st.columns([3, 1])
                    with col_dt1:
                        dom_emails_dict = {item["email"]: item["last_sent"] for item in emails}
                        dom_csv = export_email_database(dom_emails_dict, "csv")
                        st.download_button(
                            f"📥 Export @{domain} (CSV)",
                            data=dom_csv,
                            file_name=f"{domain}_contacts.csv",
                            mime="text/csv",
                            key=f"exp_{domain}",
                        )
                    with col_dt2:
                        if st.button(f"🗑️ Delete All @{domain}", key=f"del_all_{domain}"):
                            st.session_state.pending_delete_domain = domain
                            st.rerun()

                    st.markdown("###### Contacts:")
                    for idx, item in enumerate(emails):
                        e_addr = item["email"]
                        e_date = item["last_sent"]
                        is_contacted = (e_date != "Never" and bool(e_date.strip()))

                        col_row1, col_row2, col_row3 = st.columns([5, 3, 2])
                        with col_row1:
                            st.markdown(f"📧 **`{e_addr}`**")
                        with col_row2:
                            badge_color = "🟢" if is_contacted else "⚪"
                            st.caption(f"{badge_color} Last Contacted: `{e_date}`")
                        with col_row3:
                            if st.button("🗑️ Delete", key=f"del_{domain}_{idx}_{e_addr}"):
                                st.session_state.pending_delete_email = e_addr
                                st.rerun()
