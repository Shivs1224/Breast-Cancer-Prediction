"""
WSGI entry for production (e.g. Gunicorn on Render).

Mounts Django at ``/admin`` only; all other paths are handled by the Flask UI.
Using ``mammo_project.wsgi:application`` fixes 404 on ``/`` when the host still
defaults to a Django-only start command.
"""
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mammo_project.settings")

import django

django.setup()

from django.core.wsgi import get_wsgi_application
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from flask_frontend.app import create_app

django_application = get_wsgi_application()
flask_application = create_app()

application = DispatcherMiddleware(
    flask_application,
    {"/admin": django_application},
)
