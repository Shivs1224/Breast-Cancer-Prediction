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

from flask_frontend.app import create_app

app = create_app()

if __name__ == "__main__":
    from django.core.management import call_command

    call_command("migrate", interactive=False, verbosity=0)
    print("MammoAI - Flask UI + Django SQLite")
    port = int(os.environ.get("PORT", "5000"))
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    debug = not os.environ.get("RENDER")
    print(f"  http://{host}:{port}" if host != "0.0.0.0" else f"  http://127.0.0.1:{port}")
    print("  DB: db.sqlite3  |  Uploads: media/  |  Masks/CSV: data/")
    app.run(host=host, port=port, debug=debug)
