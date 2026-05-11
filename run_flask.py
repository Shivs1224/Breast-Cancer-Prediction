"""
Run Flask web UI with Django database (SQLite).

Usage (from project root):
    python run_flask.py

Then open http://127.0.0.1:5000 — register a user, upload, draw polygons, save.
"""
import os
import sys

# Project root on path for mammo_project + annotations
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mammo_project.settings")

import django

django.setup()

from django.core.management import call_command
from flask_frontend.app import create_app

call_command("migrate", interactive=False, verbosity=0)
app = create_app()

if __name__ == "__main__":
    print("MammoAI - Flask UI + Django SQLite")
    print("  http://127.0.0.1:5000")
    print("  DB: db.sqlite3  |  Uploads: media/  |  Masks/CSV: data/")
    app.run(host="127.0.0.1", port=5000, debug=True)
