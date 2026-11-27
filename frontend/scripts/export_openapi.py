"""Read the FastAPI contract without database access or backend writes.

Run from the repository root with the existing backend virtual environment:
  .venv/Scripts/python.exe -B frontend/scripts/export_openapi.py
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
os.environ.update({
    "DATABASE_URL": "sqlite:///:memory:",
    "DEV_JOB_WRITE_KEY": "schema-export-placeholder",
    "GROQ_API_KEY": "",
    "RESUME_AI_ENABLED": "false",
    "LANGCHAIN_EXPLANATIONS_ENABLED": "false",
    "APPLICATION_DRAFTS_AI_ENABLED": "false",
})
sys.path.insert(0, str(ROOT / "backend"))
from app.main import app  # noqa: E402

target = ROOT / "frontend/src/lib/openapi.json"
target.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
print(f"Exported {len(app.openapi()['paths'])} paths to {target}")
