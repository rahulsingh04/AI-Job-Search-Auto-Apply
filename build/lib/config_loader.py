"""Configuration loader helper to read and update static project configs from JSON files."""

import json
from pathlib import Path
from typing import Any, Dict, List

# Locate the project root relative to this module in src/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "data" / "config"
MASTER_CONFIG_FILE = CONFIG_DIR / "project_config.json"


def _read_json(file_path: Path) -> Dict[str, Any]:
    """Helper to safely read a JSON file."""
    if not file_path.is_file():
        return {}
    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(file_path: Path, data: Dict[str, Any]) -> None:
    """Helper to safely write a JSON file atomically."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = file_path.with_suffix(file_path.suffix + ".tmp")
    with temp_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    temp_file.replace(file_path)


def load_project_config() -> Dict[str, Any]:
    """Load the master project configuration dictionary."""
    return _read_json(MASTER_CONFIG_FILE)


def get_candidate_profile() -> Dict[str, Any]:
    """Load the candidate profile information."""
    config = load_project_config()
    if "candidate_profile" in config:
        return config["candidate_profile"]
    return _read_json(CONFIG_DIR / "candidate_profile.json")


def get_email_config() -> Dict[str, Any]:
    """Load email settings (sender, subject, template, lookback)."""
    config = load_project_config()
    if "email_config" in config:
        return config["email_config"]
    return _read_json(CONFIG_DIR / "email_config.json")


def save_email_config(new_email_cfg: Dict[str, Any]) -> None:
    """Save updated email settings to email_config.json and project_config.json."""
    _write_json(CONFIG_DIR / "email_config.json", new_email_cfg)
    if MASTER_CONFIG_FILE.is_file():
        master = load_project_config()
        master["email_config"] = new_email_cfg
        _write_json(MASTER_CONFIG_FILE, master)


def get_model_config() -> Dict[str, Any]:
    """Load LLM model settings and system prompt."""
    config = load_project_config()
    if "model_config" in config:
        return config["model_config"]
    return _read_json(CONFIG_DIR / "model_config.json")


def save_model_config(new_model_cfg: Dict[str, Any]) -> None:
    """Save updated model settings and system prompt to model_config.json and project_config.json."""
    _write_json(CONFIG_DIR / "model_config.json", new_model_cfg)
    if MASTER_CONFIG_FILE.is_file():
        master = load_project_config()
        master["model_config"] = new_model_cfg
        _write_json(MASTER_CONFIG_FILE, master)


def get_smtp_config() -> Dict[str, Any]:
    """Load SMTP connection configuration."""
    config = load_project_config()
    if "smtp_config" in config:
        return config["smtp_config"]
    return _read_json(CONFIG_DIR / "smtp_config.json")


def get_generic_email_prefixes() -> List[str]:
    """Load list of generic email prefixes (hr, careers, etc.)."""
    config = load_project_config()
    if "generic_email_prefixes" in config:
        return config["generic_email_prefixes"]
    data = _read_json(CONFIG_DIR / "generic_email_names.json")
    return data.get("generic_email_prefixes", [])


def get_recipients() -> List[str]:
    """Load list of recipient email addresses dynamically from active Email_Storage.json."""
    storage_file = PROJECT_ROOT / "bin" / "data" / "Email_Storage.json"
    if storage_file.is_file():
        storage_data = _read_json(storage_file)
        if isinstance(storage_data, dict):
            return list(storage_data.keys())
    return []
