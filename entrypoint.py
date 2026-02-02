#!/usr/bin/env python3
"""
Initialization script for Invenio RDM Starter
Uses Invenio CLI commands via subprocess for all operations.
The invenio CLI commands are Python-based, so they work in Docker Hardened Images
(DHI) which lack a shell (/bin/sh) for security reasons.
"""

import os
import subprocess
import sys


def run_command(cmd, check=True, capture_output=False):
    """Execute a shell command and return the result."""
    try:
        result = subprocess.run(
            cmd,
            shell=False,
            check=check,
            capture_output=capture_output,
            text=True,
        )
        return result
    except subprocess.CalledProcessError as e:
        if check:
            print(f"Error running command: {' '.join(cmd)}", file=sys.stderr)
            print(f"Error: {e}", file=sys.stderr)
            raise
        return e


def check_custom_field_exists():
    """Check if custom field journal:journal exists."""
    result = run_command(
        [
            "invenio",
            "rdm-records",
            "custom-fields",
            "exists",
            "-f",
            "journal:journal",
        ],
        check=False,
        capture_output=True,
    )
    return "exists" in result.stdout.lower() if result.stdout else False


def main():
    """Main initialization logic."""

    try:
        print("Creating database if not exists...")
        run_command(["invenio", "db", "init", "create"])

        print("Creating files location...")
        s3_bucket = os.environ.get("INVENIO_S3_BUCKET_NAME")
        if s3_bucket:
            run_command(
                [
                    "invenio",
                    "files",
                    "location",
                    "create",
                    "--default",
                    "s3-default",
                    f"s3://{s3_bucket}",
                ]
            )
        else:
            run_command(
                [
                    "invenio",
                    "files",
                    "location",
                    "create",
                    "--default",
                    "default",
                    "file:///opt/invenio/var/instance/data",
                ]
            )

        print("Creating superuser role...")
        run_command(["invenio", "roles", "create", "admin"])
        run_command(
            [
                "invenio",
                "access",
                "allow",
                "superuser-access",
                "role",
                "admin",
            ]
        )

        print("Creating administration access role...")
        run_command(["invenio", "roles", "create", "administration"])
        run_command(
            [
                "invenio",
                "access",
                "allow",
                "administration-access",
                "role",
                "administration",
            ]
        )

        # Creating admin user if credentials are provided
        admin_email = os.environ.get("INVENIO_ADMIN_EMAIL")
        admin_password = os.environ.get("INVENIO_ADMIN_PASSWORD")

        if admin_email and admin_password:
            print(f"Creating admin user: {admin_email}...")
            run_command(
                [
                    "invenio",
                    "users",
                    "create",
                    admin_email,
                    "--password",
                    admin_password,
                    "--active",
                    "--confirm",
                ]
            )
            run_command(["invenio", "roles", "add", admin_email, "admin"])

        print("Dropping and re-creating indices...")
        run_command(["invenio", "index", "destroy", "--force", "--yes-i-know"])
        run_command(["invenio", "index", "init"])

        print("Database and search setup completed.")

        # Check if custom fields need to be initialized
        if not check_custom_field_exists():
            print("Creating custom fields for records...")
            run_command(["invenio", "rdm-records", "custom-fields", "init"])

            print("Creating custom fields for communities...")
            run_command(["invenio", "communities", "custom-fields", "init"])

            print("Creating rdm fixtures...")
            run_command(["invenio", "rdm-records", "fixtures"])

            print("Rebuilding all indices...")
            run_command(["invenio", "rdm", "rebuild-all-indices"])

            print("Declaring queues...")
            result = run_command(
                ["invenio", "queues", "declare"],
                check=False,
                capture_output=True,
            )
            if result.returncode != 0:
                print(
                    "Warning: Failed to declare queues. This is usually non-critical."
                )
                if result.stderr:
                    print(f"Queue declaration error: {result.stderr}")

            print("Custom fields and fixtures setup completed.")

        print("Initialization completed successfully.")
    except Exception as e:
        print(f"Initialization failed: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # Execute the command passed as arguments (e.g., gunicorn, celery)
    if len(sys.argv) > 1:
        print(f"Starting application: {' '.join(sys.argv[1:])}")
        os.execvp(sys.argv[1], sys.argv[1:])
    else:
        print("No command provided to execute.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
