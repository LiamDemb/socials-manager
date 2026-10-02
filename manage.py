#!/usr/bin/env python3
import os
import sys

from core.env import load_project_env


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Tests must never open the owner data root or load owner API secrets from .env.
        os.environ["DJANGO_SETTINGS_MODULE"] = "socials_manager.settings_test"
    else:
        load_project_env()
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "socials_manager.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
