"""
Root launcher for AI Job Search & Auto-Apply Streamlit Frontend
=============================================================
Run command:
    streamlit run app.py
"""

from pathlib import Path
import runpy

app_path = Path(__file__).parent / "bin" / "app.py"
runpy.run_path(str(app_path), run_name="__main__")

