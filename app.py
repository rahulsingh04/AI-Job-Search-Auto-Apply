"""
Root launcher for AI Job Search & Auto-Apply Streamlit Frontend
=============================================================
Run command:
    streamlit run app.py
"""

import subprocess
import sys
from pathlib import Path

bin_app = Path(__file__).parent / "bin" / "app.py"
subprocess.run(
    [sys.executable, "-m", "streamlit", "run", str(bin_app)],
    check=False,
)
