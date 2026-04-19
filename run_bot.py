"""Run Telegram bot."""

import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/06_TeleBot-HomeTasks")

# Load .env file
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)


def main():
    parser = argparse.ArgumentParser(description="Run Google Classroom Telegram Bot")
    parser.add_argument("token", nargs="?", help="Telegram bot token (or set TELEGRAM_BOT_TOKEN in .env)")
    parser.add_argument("-s", "--storage", default=None, help="Assignments file")
    parser.add_argument("-t", "--timetable", default=None, help="Timetable file")
    parser.add_argument("-c", "--config", default=None, help="Config file")

    args = parser.parse_args()

    # Get token from args or .env
    token = args.token or os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        parser.error("Telegram bot token is required. Pass as argument or set TELEGRAM_BOT_TOKEN in .env")

    # Get other settings from args or .env
    storage = args.storage or os.environ.get("ASSIGNMENTS_FILE", "assignments.xlsx")
    timetable = args.timetable or os.environ.get("TIMETABLE_FILE", "timetable.xlsx")

    # Set config path if provided
    if args.config:
        os.environ["GCN_CONFIG_PATH"] = args.config

    from src.telegram_bot import run_bot

    print(f"Starting bot...")
    run_bot(token, storage, timetable)


if __name__ == "__main__":
    main()