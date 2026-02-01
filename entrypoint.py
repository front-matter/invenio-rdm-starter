#!/usr/bin/env python3
"""
Initialization script for Invenio RDM Starter
Uses Invenio CLI commands via subprocess for all operations.
The invenio CLI commands are Python-based, so they work in Docker Hardened Images
(DHI) which lack a shell (/bin/sh) for security reasons.
"""

import fcntl
import os
import subprocess
import sys
import time

# Lock file path for preventing concurrent initialization
LOCK_FILE = "/tmp/invenio_init.lock"
LOCK_TIMEOUT = 300  # 5 minutes

# State tracking for cleanup
INIT_STATE = {
    "db_created": False,
    "files_location_created": False,
    "admin_role_created": False,
    "administration_role_created": False,
    "admin_user_created": False,
    "indices_created": False,
    "custom_fields_initialized": False,
}


def acquire_lock(lock_file_path, timeout=LOCK_TIMEOUT):
    """
    Acquire an exclusive lock to prevent concurrent initialization.

    Args:
        lock_file_path: Path to the lock file
        timeout: Maximum time to wait for lock in seconds

    Returns:
        File handle if lock acquired, None if timeout
    """
    start_time = time.time()
    lock_file = None

    while True:
        try:
            lock_file = open(lock_file_path, "w")
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock_file.write(f"{os.getpid()}\n")
            lock_file.flush()
            print(f"Lock acquired by process {os.getpid()}")
            return lock_file
        except (IOError, OSError):
            if lock_file:
                lock_file.close()

            elapsed = time.time() - start_time
            if elapsed >= timeout:
                print(
                    f"Failed to acquire lock after {timeout} seconds",
                    file=sys.stderr,
                )
                return None

            print(f"Waiting for initialization lock... ({int(elapsed)}s)")
            time.sleep(2)


def release_lock(lock_file):
    """Release the initialization lock."""
    if lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()
            print(f"Lock released by process {os.getpid()}")
        except Exception as e:
            print(f"Error releasing lock: {e}", file=sys.stderr)


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


def check_db():
    """Check if database is initialized."""
    result = run_command(
        ["invenio", "db", "check"], check=False, capture_output=True
    )
    return result.returncode == 0


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


def check_demo_data_exists():
    """Check if demo data already exists by querying for records."""
    result = run_command(
        [
            "invenio",
            "shell",
            "-c",
            "from invenio_rdm_records.proxies import current_rdm_records; print(current_rdm_records.records_service.search(system_identity, size=1).total)",
        ],
        check=False,
        capture_output=True,
    )
    if result.returncode == 0 and result.stdout:
        try:
            count = int(result.stdout.strip())
            return count > 0
        except ValueError:
            pass
    return False


def cleanup_partial_initialization():
    """
    Cleanup partially initialized resources.
    Called when initialization fails partway through.
    """
    print("\n" + "=" * 60)
    print("INITIALIZATION FAILED - Starting cleanup...")
    print("=" * 60 + "\n")

    # Cleanup in reverse order of creation
    if INIT_STATE["custom_fields_initialized"]:
        print("Note: Custom fields cannot be automatically removed.")
        print("Manual intervention may be required.")

    if INIT_STATE["indices_created"]:
        print("Cleaning up search indices...")
        try:
            run_command(
                ["invenio", "index", "destroy", "--force", "--yes-i-know"],
                check=False,
            )
            print("Search indices cleaned up.")
        except Exception as e:
            print(f"Warning: Failed to cleanup indices: {e}")

    if INIT_STATE["admin_user_created"]:
        admin_email = os.environ.get("INVENIO_ADMIN_EMAIL")
        if admin_email:
            print(f"Cleaning up admin user: {admin_email}...")
            try:
                run_command(
                    ["invenio", "users", "delete", admin_email], check=False
                )
                print("Admin user cleaned up.")
            except Exception as e:
                print(f"Warning: Failed to cleanup admin user: {e}")

    if INIT_STATE["administration_role_created"]:
        print("Cleaning up administration role...")
        try:
            run_command(
                ["invenio", "roles", "delete", "administration"], check=False
            )
            print("Administration role cleaned up.")
        except Exception as e:
            print(f"Warning: Failed to cleanup administration role: {e}")

    if INIT_STATE["admin_role_created"]:
        print("Cleaning up admin role...")
        try:
            run_command(["invenio", "roles", "delete", "admin"], check=False)
            print("Admin role cleaned up.")
        except Exception as e:
            print(f"Warning: Failed to cleanup admin role: {e}")

    if INIT_STATE["files_location_created"]:
        print("Note: Files location cleanup must be done manually if needed.")

    if INIT_STATE["db_created"]:
        print("Cleaning up database...")
        try:
            run_command(["invenio", "db", "drop", "--yes-i-know"], check=False)
            print("Database cleaned up.")
        except Exception as e:
            print(f"Warning: Failed to cleanup database: {e}")

    print("\n" + "=" * 60)
    print("Cleanup completed. Please review and fix any issues.")
    print("=" * 60 + "\n")


def main():
    """Main initialization logic."""

    lock_file = None
    try:
        # Acquire lock to prevent concurrent initialization
        lock_file = acquire_lock(LOCK_FILE)
        if not lock_file:
            print(
                "Could not acquire initialization lock. Exiting.",
                file=sys.stderr,
            )
            sys.exit(1)

        # Check if database setup has already been completed
        if not check_db():
            try:
                print("Creating database...")
                run_command(["invenio", "db", "init", "create"])
                INIT_STATE["db_created"] = True

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
                INIT_STATE["files_location_created"] = True

                print("Creating superuser role...")
                run_command(["invenio", "roles", "create", "admin"])
                INIT_STATE["admin_role_created"] = True
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
                INIT_STATE["administration_role_created"] = True
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
                    INIT_STATE["admin_user_created"] = True
                    run_command(
                        ["invenio", "roles", "add", admin_email, "admin"]
                    )

                print("Dropping and re-creating indices...")
                run_command(
                    ["invenio", "index", "destroy", "--force", "--yes-i-know"]
                )
                run_command(["invenio", "index", "init"])
                INIT_STATE["indices_created"] = True

                print("Database and search setup completed.")
            except Exception as e:
                print(
                    f"\nDatabase initialization failed: {e}", file=sys.stderr
                )
                cleanup_partial_initialization()
                raise

        # Check if custom fields need to be initialized
        if not check_custom_field_exists():
            try:
                print("Creating custom fields for records...")
                run_command(
                    ["invenio", "rdm-records", "custom-fields", "init"]
                )

                print("Creating custom fields for communities...")
                run_command(
                    ["invenio", "communities", "custom-fields", "init"]
                )
                INIT_STATE["custom_fields_initialized"] = True

                print("Creating rdm fixtures...")
                run_command(["invenio", "rdm-records", "fixtures"])

                print("Rebuilding all indices...")
                run_command(["invenio", "rdm", "rebuild-all-indices"])

                # Creating demo records and communities if enabled
                demo_data = os.environ.get("INVENIO_DEMO_DATA", "").lower()
                if demo_data in ("true", "1", "yes"):
                    if check_demo_data_exists():
                        print("Demo data already exists, skipping creation...")
                    else:
                        print("Creating demo data...")
                        admin_email = os.environ.get("INVENIO_ADMIN_EMAIL")
                        if admin_email:
                            run_command(
                                [
                                    "invenio",
                                    "rdm-records",
                                    "demo",
                                    "records",
                                    "--user",
                                    admin_email,
                                ]
                            )
                            run_command(
                                [
                                    "invenio",
                                    "rdm-records",
                                    "demo",
                                    "communities",
                                    "--user",
                                    admin_email,
                                ]
                            )
                            print("Demo data creation completed.")
                        else:
                            print(
                                "Warning: INVENIO_ADMIN_EMAIL not set, skipping demo data creation."
                            )

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
            except Exception as e:
                print(
                    f"\nCustom fields initialization failed: {e}",
                    file=sys.stderr,
                )
                cleanup_partial_initialization()
                raise

        print("Initialization completed successfully.")
    finally:
        # Release lock before starting the application
        release_lock(lock_file)

    # Execute the command passed as arguments (e.g., gunicorn, celery)
    if len(sys.argv) > 1:
        print(f"Starting application: {' '.join(sys.argv[1:])}")
        os.execvp(sys.argv[1], sys.argv[1:])
    else:
        print("No command provided to execute.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Initialization failed: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)
