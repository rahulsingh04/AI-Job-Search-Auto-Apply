# AI Job Search & Auto-Apply

AI-powered cold email outreach and job application automation platform. It
leverages local Large Language Models (DeepSeek-R1 via Ollama) to craft
personalized recruiter emails, validates quality before dispatch, attaches
your PDF resume, and tracks outreach history to prevent duplicate sends.

**v0.4.0** adds a LinkedIn Post Email Scraper tab, parallel SMTP sending,
adaptive resource management, and full config-driven zero-hardcoding
architecture.

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
    └── scraper_config.json              ← NEW v0.4.0

src/ Core Modules
    ├── config_loader.py                 (lru_cache)
    ├── email_db_helper.py
    ├── resource_manager.py              ← NEW v0.4.0
    ├── linkedin_scraper/                ← NEW v0.4.0
    │   ├── window_manager.py
    │   ├── screenshot.py
    │   ├── ocr_extractor.py
    │   └── scroller.py
    ├── ai_email_writer/
    │   ├── generator.py                 (+ template utils)
    │   └── ...
    └── email_sender/
        ├── batch.py                     (+ parallel send)
        └── ...
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
│   ├── run.sh                        # Auto environment launcher
│   ├── run2.sh / run3.sh
│
├── data/
│   ├── config/
│   │   ├── candidate_profile.json
│   │   ├── email_config.json
│   │   ├── model_config.json
│   │   ├── smtp_config.json
│   │   ├── generic_email_names.json
│   │   └── scraper_config.json       ← NEW
│   └── template/
│       └── template1.txt … template5.txt
│
├── tests/
│   └── test_all_requirements.py
│
└── src/
    ├── config_loader.py
    ├── email_db_helper.py
    ├── resource_manager.py           ← NEW
    ├── linkedin_scraper/             ← NEW
    │   ├── __init__.py
    │   ├── window_manager.py
    │   ├── screenshot.py
    │   ├── ocr_extractor.py
    │   └── scroller.py
    ├── ai_email_writer/
    └── email_sender/
```

---

## 🚀 Quick Start & Prerequisites

1. **Python 3.10+** required.

2. **Install dependencies:**
   ```bash
   pip install .
   ```

3. **Ollama (Optional — for AI personalization):**
   ```bash
   ollama pull deepseek-r1:1.5b
   ```
   If Ollama is offline, the app automatically falls back
   to static templates.

4. **Gmail App Password (for SMTP sending):**
   Generate a 16-character app password from:
   [Google App Passwords](https://myaccount.google.com/apppasswords)

---

## 💻 How to Run

### Primary launcher (auto-detects environment)
```bash
bash run/run.sh
```

### Direct Python
```bash
pip install .
python -m streamlit run app.py
```

### CLI batch mode
```bash
python bin/main.py
```

### Run tests
```bash
pytest tests/test_all_requirements.py -v
```

---

## 🖥️ Streamlit Dashboard — 5 Tabs

### 💬 Tab 1: Chat & Auto-Email
- Upload resume (PDF/DOCX/TXT) → extract candidate profile
- Load recipient database (JSON/CSV/XLSX/TXT)
- AI-personalized email sending with LLM fallback
- Live streaming progress per recipient

### 🔍 Tab 2: Subject, Body & System Prompt
- Subject line length validator
- Body quality checker
- Editable dynamic system prompt for LLM

### 🗄️ Tab 3: Database Manager
- Modify contact email or last-contacted date
- Delete single, multi-select, or script-scraped contacts

### 🌐 Tab 4: Domain-Wise Email Viewer
- Analytics: total emails, domains, contacted, pending
- Filter by full email or domain name
- Export domain contacts as CSV
- Bulk domain deletion with confirmation

### 🔗 Tab 5: LinkedIn Post Email Scraper ← NEW
- Scrapes emails from LinkedIn posts in Edge browser
- No browser modification needed — purely visual
- Smart scrolling: skips posts without `@` symbol
- Stops after N consecutive empty posts (configurable)
- Deduplicates against existing Email_Storage.json
- Template-based sending (no LLM — fast)
- Random or fixed template selection per recipient
- All settings editable from UI, saved to scraper_config.json

---

## ⚙️ New in v0.4.0

### LinkedIn Post Email Scraper
Scrapes emails from LinkedIn posts visible in your Edge
browser using screen capture + EasyOCR. No browser
automation flags needed.

**How it works:**
1. Opens/focuses Edge browser automatically
2. Takes screenshots of the browser window region
3. Fast `@` pre-check skips posts without email symbols
4. Full EasyOCR runs only when `@` is detected
5. Deduplicates against existing database
6. Sends via template pipeline, saves to Email_Storage.json

### Adaptive Resource Manager
Automatically calculates safe parallel worker count based
on live CPU usage, free RAM, and configured limits.

```
CPU > threshold%  →  min_workers (protection mode)
Otherwise         →  min(cpu_cores/2, ram/per_worker, cap)
```

All thresholds configurable from Tab 5 settings UI.

### Parallel SMTP Sending
`run_email_batch_parallel` sends multiple emails
simultaneously using ThreadPoolExecutor with adaptive
workers. Used by the LinkedIn scraper tab for speed.

### Config Caching (lru_cache)
All config reads are cached after first disk read.
Cache is invalidated automatically when config is saved.

| Operation | Before | After |
|---|---|---|
| Config read (2nd+) | ~50ms | ~0.1ms |
| Scan 20 LinkedIn posts | ~60s | ~15s |
| Send 50 emails (template) | ~50s | ~12s |
| First OCR call | ~5s | ~0s (pre-warmed) |

---

## 🔧 Configuration Files

### `data/config/scraper_config.json` (NEW)
Controls all LinkedIn scraper, OCR, resource, and
template settings. Editable from Tab 5 UI.

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

**Zero hardcoding policy:** every value is read from
config at runtime. Nothing is hardcoded in source code.

---

## 📦 Dependencies

| Package | Version | Purpose |
|---|---|---|
| langchain-ollama | >=1.1.0 | Local LLM integration |
| langchain-core | >=1.0.0 | LangChain abstractions |
| pydantic | >=2.7.0 | Structured output validation |
| streamlit | >=1.30.0 | Web dashboard UI |
| pandas | >=2.0.0 | Contact DB manipulation |
| numpy | >=1.24.0 | Numerical utilities |
| openpyxl | >=3.1.0 | Excel DB support |
| pypdf | >=4.0.0 | PDF resume parsing |
| python-docx | >=1.1.0 | DOCX resume parsing |
| watchdog | >=3.0.0 | File system monitoring |
| psutil | >=5.9.0 | CPU/RAM monitoring ← NEW |
| mss | >=9.0.0 | Fast screen capture ← NEW |
| easyocr | >=1.7.0 | OCR engine ← NEW |
| pyautogui | >=0.9.54 | Scroll simulation ← NEW |
| pygetwindow | >=0.0.9 | Edge window detection ← NEW |

---

## 🛡️ Reliability & Safety

- **No sensitive data leaks** — passwords never hardcoded
- **Strict email validation** — RFC-compliant regex
- **Versioned backups** — timestamped backup before every
  DB change
- **Zero accidental sends** — lookback window skips
  recently contacted recipients
- **Two-step deletion** — confirmation dialogs prevent
  accidental contact deletion
- **Adaptive workers** — never overloads laptop CPU/RAM
- **OCR pre-warmed** — no delay on first LinkedIn scan
- **Smart scroll** — skips posts without `@` symbol (10x
  faster than full OCR on every post)
