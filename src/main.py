"""Main entry point for Google Classroom Notifier (Gmail Edition)."""

import argparse
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from . import config
from .gmail_client import GmailClient
from .notifier import Notifier, StateManager
from .storage import AssignmentStorage


def setup_logging(level: str):
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def cmd_check(args):
    """Run single check for new assignments."""
    cfg = config.load_config(args.config)
    errors = cfg.validate()

    if errors:
        for err in errors:
            print(f"Error: {err}")
        return 1

    setup_logging(cfg.log_level)

    try:
        client = GmailClient(cfg.credentials_file, cfg.token_file)
        state = StateManager(cfg.state_file)
        notifier = Notifier(client, state)

        print("Checking Gmail for Classroom emails...")

        # Get emails first to verify connection
        emails = client.get_classroom_emails(max_results=5)
        print(f"Found emails from Classroom: {len(emails)}")

        # Debug: show first few emails
        if args.verbose and emails:
            print("\n--- Debug: First emails ---")
            for i, email in enumerate(emails[:3]):
                print(f"{i+1}. Subject: {email.subject}")
                print(f"   From: {email.from_address}")
                print(f"   Date: {email.date}")
            print("--- End debug ---\n")

        # Check for new assignments
        new_assignments = notifier.check_new_assignments()

        # Save to storage
        storage = AssignmentStorage(args.storage or "assignments.xlsx")
        for assignment in new_assignments:
            storage.add_assignment(assignment)

        # Display results
        output = notifier.format_notification(new_assignments)
        print()
        print(output)

        if new_assignments:
            print(f"\nSaved {len(new_assignments)} assignment(s) to {args.storage or 'assignments.xlsx'}")

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("\nTo set up OAuth:")
        print("1. Create project in Google Cloud Console")
        print("2. Enable Gmail API")
        print("3. Create OAuth credentials for Desktop app")
        print("4. Download credentials.json to project folder")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        logging.exception("Unexpected error")
        return 1


def cmd_daemon(args):
    """Run in daemon mode, checking periodically."""
    cfg = config.load_config(args.config)
    errors = cfg.validate()

    if errors:
        for err in errors:
            print(f"Error: {err}")
        return 1

    setup_logging(cfg.log_level)
    logger = logging.getLogger(__name__)

    try:
        client = GmailClient(cfg.credentials_file, cfg.token_file)
        state = StateManager(cfg.state_file)
        notifier = Notifier(client, state)

        logger.info(f"Starting daemon mode (interval: {cfg.check_interval_minutes} min)")

        # Initial check
        print("Initial check...")
        emails = client.get_classroom_emails(max_results=5)
        print(f"Connected. Found emails: {len(emails)}")

        while True:
            try:
                new_assignments = notifier.check_new_assignments()
                output = notifier.format_notification(new_assignments)

                print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] {output}")

            except Exception as e:
                logger.error(f"Error during check: {e}")

            logger.debug(f"Sleeping for {cfg.check_interval_minutes} minutes")
            time.sleep(cfg.check_interval_minutes * 60)

    except KeyboardInterrupt:
        print("\nStopped by user")
        return 0
    except Exception as e:
        logger.exception("Fatal error")
        return 1


def cmd_list(args):
    """List all assignments from storage."""
    storage = AssignmentStorage(args.storage or "assignments.xlsx")
    
    assignments = storage.get_assignments(completed=False)
    
    if not assignments:
        print("No assignments found.")
        return 0

    print(f"\n=== All Assignments ({len(assignments)}) ===\n")
    
    # Sort by due date
    assignments.sort(key=lambda x: x.get("due_date", "9999"))
    
    for a in assignments:
        due_str = a.get("due_date", "No deadline")
        if a.get("due_time"):
            due_str += f" {a.get('due_time')}"
        
        print(f"Subject: {a.get('course', 'Unknown')}")
        print(f"  Assignment: {a.get('title', 'N/A')}")
        print(f"  Teacher: {a.get('teacher', 'N/A')}")
        print(f"  Due: {due_str}")
        print()

    return 0


def cmd_today(args):
    """Show assignments due today."""
    storage = AssignmentStorage(args.storage or "assignments.xlsx")
    
    today = datetime.now().strftime("%Y-%m-%d")
    assignments = storage.get_assignments_for_date(today)
    
    if not assignments:
        print(f"No assignments due today ({today})")
        return 0

    print(f"\n=== Assignments for Today ({today}) ({len(assignments)}) ===\n")
    
    for a in assignments:
        print(f"Subject: {a.get('course', 'Unknown')}")
        print(f"  Assignment: {a.get('title', 'N/A')}")
        print(f"  Teacher: {a.get('teacher', 'N/A')}")
        if a.get("due_time"):
            print(f"  Due time: {a.get('due_time')}")
        print()

    return 0


def cmd_tomorrow(args):
    """Show assignments due tomorrow."""
    storage = AssignmentStorage(args.storage or "assignments.xlsx")
    
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    assignments = storage.get_assignments_for_date(tomorrow)
    
    if not assignments:
        print(f"No assignments due tomorrow ({tomorrow})")
        return 0

    print(f"\n=== Assignments for Tomorrow ({tomorrow}) ({len(assignments)}) ===\n")
    
    for a in assignments:
        print(f"Subject: {a.get('course', 'Unknown')}")
        print(f"  Assignment: {a.get('title', 'N/A')}")
        print(f"  Teacher: {a.get('teacher', 'N/A')}")
        if a.get("due_time"):
            print(f"  Due time: {a.get('due_time')}")
        print()

    return 0


def cmd_week(args):
    """Show assignments for the next 7 days."""
    storage = AssignmentStorage(args.storage or "assignments.xlsx")
    
    all_assignments = storage.get_assignments(completed=False)
    
    # Filter assignments for next 7 days
    today = datetime.now().date()
    week_later = today + timedelta(days=7)
    
    week_assignments = []
    for a in all_assignments:
        due_date_str = a.get("due_date")
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
                if today <= due_date <= week_later:
                    week_assignments.append(a)
            except:
                pass
    
    if not week_assignments:
        print(f"No assignments due in the next 7 days")
        return 0

    print(f"\n=== Assignments for Next 7 Days ({len(week_assignments)}) ===\n")
    
    # Group by date
    from collections import defaultdict
    by_date = defaultdict(list)
    for a in week_assignments:
        by_date[a.get("due_date", "Unknown")].append(a)
    
    # Sort by date
    for date in sorted(by_date.keys()):
        print(f"=== {date} ===")
        for a in by_date[date]:
            print(f"  Subject: {a.get('course', 'Unknown')}")
            print(f"    Assignment: {a.get('title', 'N/A')}")
            print(f"    Teacher: {a.get('teacher', 'N/A')}")
        print()

    return 0


def cmd_auth(args):
    """Run OAuth authentication flow."""
    cfg = config.load_config(args.config)

    setup_logging("INFO")

    try:
        client = GmailClient(cfg.credentials_file, cfg.token_file)

        # This will trigger OAuth flow
        service = client._get_service()

        print("Authorization successful!")
        print(f"Token saved to: {cfg.token_file}")

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        logging.exception("Error")
        return 1


def cmd_debug(args):
    """Debug - show recent emails."""
    cfg = config.load_config(args.config)
    errors = cfg.validate()

    if errors:
        for err in errors:
            print(f"Error: {err}")
        return 1

    setup_logging("INFO")

    try:
        client = GmailClient(cfg.credentials_file, cfg.token_file)

        print("Fetching recent emails...")
        emails = client.get_all_emails(max_results=10)

        print(f"\nTotal emails: {len(emails)}\n")

        for i, email in enumerate(emails):
            print(f"{i+1}. Subject: {email.subject}")
            print(f"   From: {email.from_address}")
            print(f"   Date: {email.date}")
            print(f"   Snippet: {email.snippet[:80]}...")
            print()

        return 0

    except Exception as e:
        print(f"Error: {e}")
        logging.exception("Error")
        return 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="gcn",
        description="Google Classroom Notifier - check assignments via Gmail",
    )
    parser.add_argument(
        "-c", "--config",
        default=None,
        help="Path to config file (default: config/config.json or GCN_CONFIG_PATH)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show debug info",
    )
    parser.add_argument(
        "-s", "--storage",
        default=None,
        help="Path to assignments Excel file",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # check command
    check_parser = subparsers.add_parser("check", help="One-time check for new assignments")
    check_parser.add_argument("-v", "--verbose", action="store_true", help="Show debug info")
    check_parser.add_argument("-s", "--storage", default=None, help="Path to assignments Excel file")

    # daemon command
    daemon_parser = subparsers.add_parser("daemon", help="Run in daemon mode")

    # list command
    list_parser = subparsers.add_parser("list", help="Show all assignments")
    list_parser.add_argument("-s", "--storage", default=None, help="Path to assignments Excel file")

    # today command
    today_parser = subparsers.add_parser("today", help="Show assignments due today")
    today_parser.add_argument("-s", "--storage", default=None, help="Path to assignments Excel file")

    # tomorrow command
    tomorrow_parser = subparsers.add_parser("tomorrow", help="Show assignments due tomorrow")
    tomorrow_parser.add_argument("-s", "--storage", default=None, help="Path to assignments Excel file")

    # week command
    week_parser = subparsers.add_parser("week", help="Show assignments for next 7 days")
    week_parser.add_argument("-s", "--storage", default=None, help="Path to assignments Excel file")

    # auth command
    auth_parser = subparsers.add_parser("auth", help="Authenticate via OAuth")

    # debug command
    debug_parser = subparsers.add_parser("debug", help="Show recent emails (debug)")

    args = parser.parse_args()

    if args.command == "check":
        return cmd_check(args)
    elif args.command == "daemon":
        return cmd_daemon(args)
    elif args.command == "list":
        return cmd_list(args)
    elif args.command == "today":
        return cmd_today(args)
    elif args.command == "tomorrow":
        return cmd_tomorrow(args)
    elif args.command == "week":
        return cmd_week(args)
    elif args.command == "auth":
        return cmd_auth(args)
    elif args.command == "debug":
        return cmd_debug(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())