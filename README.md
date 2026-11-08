# AI Job Search & Auto-Apply

AI-powered cold email outreach and job application automation platform.
Crafts personalized recruiter emails using a local LLM (DeepSeek-R1 via
Ollama), validates quality before dispatch, attaches your PDF resume, and
tracks outreach history to prevent duplicate sends.

**v0.4.0** — LinkedIn Post Email Scraper, parallel SMTP sending, adaptive
resource management, and full config-driven zero-hardcoding architecture.

---

## Table of Contents

1. [Prerequisites](#-prerequisites)
2. [Tutorial — Run the App](#-tutorial--run-the-app)
   - [Option A — Shell Launcher (Recommended)](#option-a--shell-launcher-recommended)
   - [Option B — Manual Python](#option-b--manual-python)
   - [Option C — CLI Batch Mode](#option-c--cli-batch-mode)
3. [First-Time Setup Walkthrough](#-first-time-setup-walkthrough)
4. [Dashboard Tabs Guide](#-dashboard-tabs-guide)
5. [System Architecture](#-system-architecture)
6. [Project Structure](#-project-structure)
7. [Configuration Files](#-configuration-files)
8. [Dependencies](#-dependencies)
9. [Reliability & Safety](#-reliability--safety)

---

## ✅ Prerequisites

Before running the app, make sure you have the following:

| Requirement | Version | Notes |
|---|---|---|
| Python | >= 3.10 | [python.org/downloads](https://www.python.org/downloads/) |
| Git Bash / WSL | any | Required to run `.sh` launcher on Windows |
| Microsoft Edge | any | Required for LinkedIn scraper tab only |
| Ollama | latest | Optional — for AI email personalization |
| Gmail App Password | 16 chars | Required for SMTP sending |

---

## 🚀 Tutorial — Run the App

### Option A — Shell Launcher (Recommended)

The shell launcher auto-detects your Python environment, installs
dependencies, configures Ollama, and starts Streamlit — all in one command.

**Step 1.** Open Git Bash (or WSL) and navigate to the project folder:

```bash
cd /path/to/AI-Job-Search-Auto-Apply
```

**Step 2.** Run the main launcher:

```bash
bash run/main_runner.sh
```

**Step 3.** The launcher will walk you through 5 steps automatically:

```
[STEP 1/5] Checking Ollama installation and local models...
[STEP 2/5] Checking Python requirements and environment...
[STEP 3/5] Updating model configuration...
[STEP 4/5] Installing/verifying project dependencies...
[STEP 5/5] Starting Streamlit application...
```

**Step 4.** At Step 1, choose your LLM mode when prompted:

```
Choose how to run the application:
  1) Continue with an installed model (choose from the list)
  2) Download another model and use it
  3) Continue without local LLM (use fallback processing)

Enter 1, 2, or 3:
```

- Enter `1` if you already have a model installed (e.g. `deepseek-r1:1.5b`)
- Enter `2` to download a model now (e.g. type `deepseek-r1:1.5b`)
- Enter `3` to skip LLM — the app will use static email templates

**Step 5.** Once Streamlit starts, open your browser at:

```
http://localhost:8501
```

**Step 6.** When you press `Ctrl+C` to stop the app, the launcher
automatically runs cleanup — normalizes email history, purges pip/conda
cache, and removes Python bytecode.

---

### Option B — Manual Python

Use this if you prefer not to use the shell launcher.

**Step 1.** Install dependencies:

```bash
pip install .
```

**Step 2.** (Optional) Start Ollama and pull a model:

```bash
ollama pull deepseek-r1:1.5b
ollama serve
```

**Step 3.** Launch the Streamlit dashboard:

```bash
python -m streamlit run app.py
```

**Step 4.** Open your browser at `http://localhost:8501`.

---

### Option C — CLI Batch Mode

Run email sending in headless batch mode without the Streamlit UI:

```bash
python bin/main.py
```

---

### Run Tests

```bash
pytest tests/test_all_requirements.py -v
```

---

## 🗺️ First-Time Setup Walkthrough

Follow these steps the very first time you use the app.

### 1. Get a Gmail App Password

The app sends emails via Gmail SMTP. You need a 16-character App Password
(not your regular Gmail password).

1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Select app: **Mail** → device: **Windows Computer**
3. Click **Generate** — copy the 16-character password
4. Paste it into the **Gmail App Password** field in the sidebar

> Your password is never stored to disk. It lives only in the Streamlit
> session for the duration of the app run.

### 2. Upload Your Resume

1. Open **Tab 1 — Chat & Auto-Email**
2. Click **Upload Resume** and select your PDF, DOCX, or TXT resume
3. The app extracts your candidate profile automatically (name, role,
   skills, projects, education)
4. Review the extracted profile in the **View Profile Details** tab
5. Edit anything incorrect in the **Edit Profile Details** tab and click
   **Save Profile Changes**

### 3. Load Your Recipient Database

Your recipient database is a file containing recruiter email addresses.
Supported formats: `.json`, `.csv`, `.xlsx`, `.txt`.

**Option A — Paste emails directly:**
- In the **Add Email(s) / Paste Job Description Script** box, paste any
  text containing email addresses (job postings, LinkedIn posts, etc.)
- Click **Extract & Add to Database** — emails are extracted, deduplicated,
  and saved automatically

**Option B — Load an existing file:**
- Click **Browse File** to open a file picker, or type the path in the
  **Location of Database File** box and click **Load Location**

**Option C — Use the default database:**
- The app automatically loads `Email_Storage.json` from the project root
  on startup if it exists

### 4. Choose an Email Template

1. Use the **body_template** dropdown in the sidebar to pick a template
   (`template1` through `template5`)
2. Or click the template buttons above the body text area in Tab 1
3. The body is automatically filled with your candidate profile details
4. Edit the body text directly if you want to customize it further

### 5. Send Emails

1. Enter your **Gmail Address** and **App Password** in the sidebar
2. Set the **Look-back** period (e.g. `1 month`) — recipients contacted
   within this window are automatically skipped
3. Click **🚀 Send Automatic Email**
4. Watch the live streaming progress — each email shows its status,
   the body used, and whether AI personalization was applied
5. `Email_Storage.json` is updated immediately after each successful send

### 6. Use the LinkedIn Scraper (Tab 5)

1. Open **Tab 5 — LinkedIn Scraper**
2. (Optional) Enter job title(s) in the **Job Search** box and click
   **Open Job Search in Edge** to navigate to relevant posts
3. Click **🚀 Launch Edge & Start Scraping**
4. The app takes screenshots of your Edge browser, runs OCR, and extracts
   email addresses from LinkedIn posts automatically
5. Found emails appear in the **Found This Session** list
6. Select a template mode (Random or Specific) and click
   **📤 Send via Template & Save to DB** to send and save

---

## 🖥️ Dashboard Tabs Guide

### 💬 Tab 1 — Chat & Auto-Email

| Feature | Description |
|---|---|
| Resume Upload | PDF/DOCX/TXT → auto-extracts candidate profile |
| Profile Editor | View and edit extracted name, role, skills, projects |
| Database Loader | Browse, load, or paste recipient emails |
| Export | Download database as CSV, Excel, TXT, or JSON |
| Template Switcher | 5 templates, dynamically filled with profile data |
| Send Button | AI-personalized sending with live streaming progress |

### 🔍 Tab 2 — Subject, Body & System Prompt

| Feature | Description |
|---|---|
| Subject Validator | Checks length and quality of subject line |
| Body Validator | Checks greeting, closing, and candidate signature |
| System Prompt Editor | Edit the LLM instruction prompt live |
| Reset Prompt | Restore the auto-generated prompt from profile |

### 🗄️ Tab 3 — Database Manager

| Feature | Description |
|---|---|
| Modify Contact | Change email address or last-contacted date |
| Delete Contacts | Single, multi-select, or paste-to-scrape deletion |
| Database Table | Full view of all contacts with domain and date |

### 🌐 Tab 4 — Domain-Wise Email Viewer

| Feature | Description |
|---|---|
| Metrics | Total emails, domains, contacted, pending counts |
| Search | Filter by full email, username, or domain name |
| Domain Export | Download any domain's contacts as CSV |
| Bulk Delete | Delete all contacts under a domain (with confirmation) |

### 🔗 Tab 5 — LinkedIn Scraper

| Feature | Description |
|---|---|
| Job Search | Open LinkedIn job search in Edge for specific titles |
| Scraper Settings | Configure scroll speed, post count, OCR language |
| Resource Settings | CPU/RAM thresholds and worker limits |
| Live Scraping | Real-time log of found, duplicate, and skipped posts |
| Template Send | Send to all found emails via template pipeline |

---

## 🏗️ System Architecture

```
User Interfaces
    ├── Streamlit Dashboard  (bin/app.py)   — 5 tabs
    └── CLI Script           (bin/main.py)

Configuration Layer  (data/config/)
    ├── candidate_profile.json
    ├── email_config.json
    ├── model_config.json
    ├── smtp_config.json
    ├── generic_email_names.json
    └── scraper_config.json

src/ Core Modules
    ├── config_loader.py                 (lru_cache)
    ├── email_db_helper.py
    ├── resource_manager.py
    ├── linkedin_scraper/
    │   ├── window_manager.py
    │   ├── screenshot.py
    │   ├── ocr_extractor.py
    │   └── scroller.py
    ├── ai_email_writer/
    │   ├── generator.py
    │   ├── model.py
    │   ├── prompts.py
    │   ├── schemas.py
    │   ├── validator.py
    │   ├── formatter.py
    │   ├── profile.py
    │   ├── recipient.py
    │   ├── resume_parser.py
    │   └── templates.py
    └── email_sender/
        ├── batch.py
        ├── sender.py
        ├── smtp.py
        ├── builder.py
        ├── attachments.py
        ├── storage.py
        └── date_utils.py
```

---

## 📂 Project Structure

```
AI-Job-Search-Auto-Apply/
├── app.py                            # Root Streamlit launcher
├── pyproject.toml                    # Dependencies (Python >=3.10)
├── README.md
│
├── bin/
│   ├── app.py                        # Streamlit dashboard (5 tabs)
│   └── main.py                       # CLI batch execution
│
├── run/
│   ├── main_runner.sh                # ← Main launcher (run this)
│   ├── colors_and_utils.sh           # ANSI colors + print helpers
│   ├── banner_and_cleanup.sh         # Project banner + post-app cleanup
│   ├── ollama_setup.sh               # Ollama detect/install/model select
│   ├── python_env.sh                 # Python interpreter detection
│   ├── config_updater.sh             # model_config.json update
│   ├── deps_installer.sh             # pip dependency install
│   └── streamlit_launcher.sh         # Streamlit app launch
│
├── data/
│   ├── config/
│   │   ├── candidate_profile.json
│   │   ├── email_config.json
│   │   ├── model_config.json
│   │   ├── smtp_config.json
│   │   ├── generic_email_names.json
│   │   └── scraper_config.json
│   └── template/
│       └── template1.txt … template5.txt
│
├── tests/
│   └── test_all_requirements.py
│
└── src/
    ├── config_loader.py
    ├── email_db_helper.py
    ├── resource_manager.py
    ├── linkedin_scraper/
    │   ├── __init__.py
    │   ├── window_manager.py
    │   ├── screenshot.py
    │   ├── ocr_extractor.py
    │   └── scroller.py
    ├── ai_email_writer/
    └── email_sender/
```

---

## 🔧 Configuration Files

### `data/config/email_config.json`

Controls sender email, subject, look-back period, and resume filename.

```json
{
    "sender_email": "you@gmail.com",
    "subject": "AI Engineer | Data Scientist | 3+ Years Experience",
    "look_back": 1,
    "look_back_format": "months",
    "resume_filename": "YOUR_RESUME.pdf"
}
```

### `data/config/model_config.json`

Controls LLM model selection and system prompt.

```json
{
    "model_name": "deepseek-r1:1.5b",
    "llm_enabled": true,
    "max_tokens": 2048,
    "temperature": 0.1,
    "system_prompt": "..."
}
```

Set `"llm_enabled": false` to disable AI personalization and use
static templates only.

### `data/config/scraper_config.json`

Controls all LinkedIn scraper, OCR, resource, and template settings.
All values are editable from the Tab 5 settings UI.

```json
{
    "linkedin": {
        "feed_url": "https://www.linkedin.com/feed/",
        "max_posts": 20,
        "empty_streak_limit": 10,
        "scroll_amount": 3,
        "scroll_delay_seconds": 0.8,
        "post_load_wait_seconds": 1.0
    },
    "ocr": {
        "languages": ["en"],
        "use_gpu": false,
        "warm_up_on_start": true
    },
    "resource": {
        "max_worker_cap": 5,
        "cpu_overload_threshold": 80,
        "ram_per_worker_gb": 2.0,
        "min_workers": 2
    },
    "template": {
        "mode": "random",
        "fixed_template_index": null,
        "no_consecutive_repeat": true
    }
}
```

### `data/config/candidate_profile.json`

Auto-populated when you upload a resume. Can also be edited manually
or via the Tab 1 profile editor.

```json
{
    "name": "Rahul Kumar Singh",
    "current_role": "Data Scientist",
    "experience_summary": "3+ years in Data Science and AI",
    "technical_skills": ["Python", "SQL", "Machine Learning"],
    "projects": ["Project A", "Project B"],
    "education": "B.Tech Computer Science"
}
```

---

## 📦 Dependencies

| Package | Version | Purpose |
|---|---|---|
| langchain-ollama | >=1.1.0 | Local LLM (DeepSeek-R1) calls |
| langchain-core | >=1.0.0 | LangChain abstractions |
| pydantic | >=2.7.0 | Structured output validation |
| streamlit | >=1.30.0 | Web dashboard UI |
| pandas | >=2.0.0 | Contact DB manipulation |
| numpy | >=1.24.0 | Numerical utilities |
| openpyxl | >=3.1.0 | Excel DB support |
| pypdf | >=4.0.0 | PDF resume parsing |
| python-docx | >=1.1.0 | DOCX resume parsing |
| watchdog | >=3.0.0 | File system monitoring |
| psutil | >=5.9.0 | CPU/RAM monitoring |
| mss | >=9.0.0 | Fast screen capture |
| easyocr | >=1.7.0 | OCR engine for LinkedIn scraper |
| pyautogui | >=0.9.54 | Scroll simulation |
| pygetwindow | >=0.0.9 | Edge window detection |

Install all at once:

```bash
pip install .
```

---

## 🛡️ Reliability & Safety

- **No credential storage** — Gmail App Password lives only in the
  Streamlit session, never written to disk
- **RFC-compliant email validation** — invalid addresses are rejected
  before sending
- **Versioned timestamped backups** — a backup is created before every
  database mutation
- **Lookback deduplication** — recipients contacted within the configured
  window are automatically skipped
- **Two-step deletion** — confirmation dialogs prevent accidental contact
  removal
- **Adaptive workers** — CPU/RAM-aware thread count prevents laptop
  overload during parallel sending
- **OCR pre-warmed** — EasyOCR model loads in a background thread at
  startup, eliminating first-scan delay
- **Smart scroll** — posts without `@` symbol are skipped before running
  full OCR (10x faster scan)
- **Thread-safe screenshot** — fresh `mss` instance per capture call
  prevents cross-thread crashes on Windows
- **Atomic config writes** — all JSON config saves use a `.tmp` →
  `replace` pattern to prevent partial writes

---

## 🔗 Links

- **Gmail App Passwords:** [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
- **Ollama Models:** [ollama.com/library](https://ollama.com/library)
- **Ollama Download:** [ollama.com/download](https://ollama.com/download)
- **GitHub:** [github.com/rahulsingh04/AI-Job-Search-Auto-Apply](https://github.com/rahulsingh04/AI-Job-Search-Auto-Apply)
