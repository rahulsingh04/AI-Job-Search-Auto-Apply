# AI Job Search & Auto-Apply

AI-powered cold email outreach and job application automation platform. It leverages local Large Language Models (DeepSeek-R1 via Ollama) to craft highly personalized, respectful, and recruiter-tailored emails, validates email quality and structure before dispatch, attaches your PDF resume, and tracks outreach history to prevent duplicate sends.

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    subgraph UI ["User Interfaces"]
        UI_Web["Streamlit Web Dashboard<br/>(app.py / bin/app.py)"]
        UI_CLI["CLI Script<br/>(bin/main.py)"]
        UI_SH["Automated Launcher<br/>(run.sh / run/mail_sender.sh / .bat)"]
    end

    subgraph ConfigLayer ["Configuration Layer (data/config/)"]
        CFG_Prof["candidate_profile.json<br/>(Dynamic Profile & Resume Extractor)"]
        CFG_Mail["email_config.json<br/>(Sender, Lookback & Body Template)"]
        CFG_Model["model_config.json<br/>(Ollama Model Params & System Prompt)"]
        CFG_SMTP["smtp_config.json<br/>(Gmail TLS SMTP Settings)"]
        CFG_Gen["generic_email_names.json<br/>(Prefixes to Skip for Name Inference)"]
    end

    subgraph CoreEngine ["src/ Core Helpers"]
        Loader["config_loader.py<br/>(Dynamic Config Loader & Saver)"]
        DBHelper["email_db_helper.py<br/>(Multi-format Parser, Dedup & Backup)"]
        
        subgraph AIWriter ["ai_email_writer/"]
            Recipient["recipient.py<br/>(Name Inference: Hi [Name],)"]
            Formatter["formatter.py<br/>(Skills & Greeting Formatter)"]
            LLM["model.py<br/>(Ollama / DeepSeek-R1)"]
            Validator["validator.py<br/>(Email Quality & Completeness Tool)"]
            Generator["generator.py<br/>(Retry Loop & Fallback Engine)"]
            Prompts["prompts.py<br/>(Dynamic Generic System Prompt)"]
            ResumeParser["profile.py<br/>(PDF Resume Extractor & Pydantic Validation)"]
        end

        subgraph EmailSender ["email_sender/"]
            Storage["storage.py<br/>(Email_Storage.json History Persistence)"]
            Builder["builder.py<br/>(MIME Multipart & PDF Attachment)"]
            SMTP["smtp.py<br/>(Gmail TLS SMTP Client)"]
            Batch["batch.py<br/>(Live Streaming Outreach Pipeline)"]
        end
    end

    UI --> Loader
    UI --> DBHelper
    Loader --> ConfigLayer
    Batch --> Storage
    Batch --> Generator
    Generator --> Prompts
    Generator --> Recipient
    Generator --> LLM
    Generator --> Formatter
    Generator --> Validator
    Generator -.->|Fallback if no LLM detected| Formatter
    Batch --> Builder
    Builder --> SMTP
    SMTP -->|Sent| External["Recruiter Inboxes 📬"]
```

---

## 📂 Project Structure

```
AI-Job-Search-and-Auto-Apply/
├── app.py                            # 🌐 Root Streamlit web launcher
├── run.sh                            # ⚡ Root automated environment & launch script
├── pyproject.toml                    # 📦 Python project & dependencies (Author: RAHUL KUMAR SINGH)
├── README.md                         # 📖 Documentation & guides
│
├── bin/                              # 🚀 Execution & Storage
│   ├── app.py                        # Main Streamlit dashboard (4 tabs)
│   ├── main.py                       # CLI batch execution script
│   └── data/
│       ├── Email_Storage.json        # Active sorted recipient history & dedup storage
│       └── Email_Storage_*.json      # Timestamped archives automatically created on ingestion
│
├── run/                              # ⚡ Modular Launchers
│   ├── mail_sender.sh                # Shell script with step tracker & terminal viewer
│   └── mail_sender.bat               # Windows batch launcher
│
├── doc/
│   └── nb/
│       └── test_case1.ipynb          # 🧪 12-Step modular end-to-end test suite
│
├── data/
│   └── config/                       # ⚙️ JSON Configuration Bucket
│       ├── candidate_profile.json    # Candidate background, skills & projects
│       ├── email_config.json         # Sender email, subject, template & lookback
│       ├── model_config.json         # Model parameters & custom system prompt
│       ├── smtp_config.json          # SMTP server connection settings
│       └── generic_email_names.json  # Prefixes to skip for personal name inference
│
└── src/                              # 🧩 Modular Source Code
    ├── config_loader.py              # Configuration loader & saver helper
    ├── email_db_helper.py            # Multi-format parser, strict regex, backups & domain ops
    │
    ├── ai_email_writer/              # 🤖 AI Generation & Quality Control
    │   ├── model.py                  # Local Ollama model initialization
    │   ├── recipient.py              # Name inference (Hi [Name],)
    │   ├── formatter.py              # Skills numbering & greeting enforcement
    │   ├── validator.py              # Email body completeness & quality validator
    │   ├── generator.py              # Generation orchestrator with retry & fallback
    │   ├── prompts.py                # Dynamic generic system prompt from candidate_profile
    │   ├── profile.py                # Candidate profile text builder & PDF parser
    │   └── schemas.py                # Pydantic response models
    │
    └── email_sender/                 # 📤 Email Delivery & Protection
        ├── batch.py                  # Streaming batch outreach generator & pipeline
        ├── sender.py                 # Single email dispatch with dedup
        ├── builder.py                # MIME multipart message builder
        ├── attachments.py            # PDF resume attachment validator
        ├── storage.py                # Atomic JSON history persistence
        ├── smtp.py                   # TLS SMTP client
        └── date_utils.py             # Calendar month/day/year math
```

---

## 🚀 Quick Start Guide

### Prerequisites
1. **Ollama**: Download and install [Ollama](https://ollama.com). Pull the local reasoning model:
   ```bash
   ollama pull deepseek-r1:1.5b
   ```
2. **Gmail App Password**: Generate a 16-character password via:
   [Google App Passwords Direct Link](https://myaccount.google.com/apppasswords?rapt=AEjHL4OxjMhR8sHJ0zDg_QESBF0hz-FbIdCGL5w8_Z3ANcLxtBpaXoyvsshRYbMjzGsKw8wCMWqG6bWL8TtMHNNUutxlbtvTngrfFjkaeqgP69mxLVTlA14)
3. **Resume PDF**: Upload your resume PDF through the Streamlit UI or place it in the project root.

---

### Method 1: One-Click Automated Script (Recommended)

#### On Linux / macOS / Git Bash:
```bash
bash run.sh
# or: bash run/mail_sender.sh
```

#### On Windows (Command Prompt or PowerShell):
```cmd
run\mail_sender.bat
```

**What the launcher does automatically:**
1. Detects your active Python environment (Conda, Virtualenv, or System PATH).
2. Checks project dependencies; if missing, creates a virtual environment (`.venv`).
3. Runs `pip install -e .[dev]` to install all packages declared in `pyproject.toml` (developed by **RAHUL KUMAR SINGH**).
4. Automatically launches the Streamlit frontend with clean step-by-step terminal output.

---

### Method 2: Manual Streamlit Web App

For a fresh Python environment (all packages managed directly via `pyproject.toml`):
```bash
# 1. Install project dependencies in editable mode
pip install -e ".[dev]"

# 2. Launch web interface
streamlit run app.py
```

---

## 🖥️ Streamlit Frontend Dashboard Guide

The web interface is organized into 4 specialized tabs:

### 💬 Tab 1: Chat & Auto-Email
- **Resume Upload & AI Extractor**: Automatically parses your PDF/TXT resume using LLM with regex fallback and Pydantic validation directly into `candidate_profile.json`.
- **Database File Location**: Specify the exact location of your database file (`.json`, `.csv`, `.xlsx`, `.txt`). Defaults to `bin/data/Email_Storage.json` and loads active records dynamically.
- **Automatic Ingestion & Current DB Backup**: Pasting single emails, multiple emails, raw text, or job postings into `"Add Email(s) / Paste Job Description Script:"` extracts all valid emails, **first creates a backup of the current database file** (`Email_Storage_<date>_<time>.json`), and **then adds the updated emails** in sorted, deduplicated order.
- **Directory Export & Snapshot Backups**: In the export section, clicking Save or Download automatically saves the exported files (`Email_Storage.csv`, `.xlsx`, `.txt`, `.json`) **directly in the same directory where the database file is located**, and also creates the timestamped backup `Email_Storage_<date>_<time>.json` in the same directory **without asking**.

- **Real-Time Streaming Outreach**: Clicking `"🚀 Send Automatic Email"` streams progressive live updates:
  1. `📊 In your database you have X emails`
  2. `⏱️ From the last {LOOK-BACK}_{UNIT} you have already sent Y emails`
  3. `📬 Remaining emails to process: Z`
  4. Per email:
     - Shows recipient address, sender address, and subject
     - Displays the generic template
     - Detects local LLM; if online, generates personalized body; if offline, reports:
       `⚠️ Oops, sorry! No LLM detected. Switching to the generic body...`
     - Dispatches via TLS SMTP
     - Displays remaining emails left to process

### 🔍 Tab 2: Dynamic Subject, Body & System Prompt
- **Dynamic Subject Line**: Real-time length validation and mobile client truncation warnings ($\le 60$ characters).
- **Quality Validator**: Tests the general body against the `EmailValidator` tool (checks greeting, closing, signature, word count, cut-off sentences, placeholder leaks).
- **Dynamic Generic System Prompt**: Directly exposes `candidate_profile.json` details to the LLM. Enforces:
  - An exceptionally polite, respectful, and humble tone.
  - Proper bullet points (`•`) whenever presenting skills or achievements.
  - Double newlines (`\n\n`) between sentences/paragraphs when transitioning sections.
  - Interactive editor with a **"🔄 Reset to Generic Prompt"** button.

### 🗄️ Tab 3: Database Manager (Modify & Delete Only)
- **Modify Contact Record**: Select any contact in the database to edit their email address or update their last contacted timestamp.
- **Delete Contact Record(s)**: Select single/multiple emails or paste a text script to scrape and delete matching contacts.
- **Live Searchable Preview**: Interactive table of all stored contacts and last contacted dates.

### 🌐 Tab 4: Domain-Wise Email Viewer & Analytics
- **Analytics KPIs**: Displays Total Emails, Unique Domains, Contacted Count, and Uncontacted/Pending Count.
- **Domain Search**: Search and filter contacts by company domain name (e.g., `capgemini.com`, `ey.com`, `fractal.ai`).
- **Domain Actions**: Export contacts for a specific domain as CSV, or delete an entire domain.
- **Two-Step Confirmation Security**:
  - Deleting an individual contact requires a second confirmation check.
  - Deleting an entire domain requires an explicit bulk deletion confirmation banner.

---

## 🧪 Modular End-to-End Test Suite

Run all backend components without Streamlit in Jupyter:
```bash
jupyter notebook doc/nb/test_case1.ipynb
```
The notebook tests 12 modular steps:
1. Environment & Path Initialization
2. Dynamic Candidate Profile & Config Loader
3. Dynamic Generic System Prompt Generation
4. Multi-format Database Loading (`.json`, `.csv`, `.xlsx`, `.txt`)
5. Strict Email Validation & Text Scraping (`is_valid_email`)
6. Recipient Salutation & Name Inference (`Hi [Name],`)
7. Email Body Quality Validator (`EmailValidator`)
8. Graceful Fallback Engine when LLM is Offline
9. Look-back Window & Deduplication Skip Logic
10. Multi-format Database Export (`.json`, `.csv`, `.xlsx`, `.txt`)
11. Domain-Wise Analytics & Domain Operations
12. End-to-End Streaming Batch Outreach Simulation (`run_email_batch_stream`)

---

## 🛡️ Reliability & Safety Guarantees

- **Strict Regex Filtering**: Eliminates malformed addresses (e.g. `user@domain.`, trailing dots, bracketed characters) with TLD length $\ge 2$.
- **Automatic Versioned Backups**: Never lose contact history; every ingestion creates an immutable timestamped file.
- **Zero Accidental Sends**: Contacts emailed within the look-back window are skipped before calling the LLM or SMTP.
- **Double-Confirmation Deletion**: Prevents accidental data deletion with interactive confirmation dialogues.
