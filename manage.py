#!/usr/bin/env python3
import os
import sys


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Tests must never open the owner data root.
        os.environ["DJANGO_SETTINGS_MODULE"] = "bandevidence.settings_test"
    else:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bandevidence.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
