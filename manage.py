#!/usr/bin/env python
"""Django entrypoint for database migrations and admin."""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mammo_project.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Install dependencies: pip install -r requirements.txt"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
