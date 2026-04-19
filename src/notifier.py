"""Notification logic for new assignments from Gmail."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .gmail_client import GmailClient
from .parser import ClassroomAssignment, EmailParser

logger = logging.getLogger(__name__)


class StateManager:
    """Manages state to track processed emails."""

    def __init__(self, state_file: str):
        self.state_file = Path(state_file)
        self._state: dict = {}
        self._load()

    def _load(self):
        """Load state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    self._state = json.load(f)
                logger.debug(f"Loaded state from {self.state_file}")
            except Exception as e:
                logger.warning(f"Failed to load state: {e}")
                self._state = {}

    def save(self):
        """Save state to file."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, "w") as f:
                json.dump(self._state, f, indent=2, default=str)
            logger.debug(f"Saved state to {self.state_file}")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def get_last_check_time(self) -> Optional[datetime]:
        """Get last check time."""
        timestamp = self._state.get("last_check")
        if timestamp:
            try:
                return datetime.fromisoformat(timestamp)
            except Exception:
                return None
        return None

    def update_last_check_time(self):
        """Update last check time."""
        self._state["last_check"] = datetime.now().isoformat()

    def is_email_processed(self, email_id: str) -> bool:
        """Check if email has been processed."""
        return email_id in self._state.get("processed_emails", [])

    def mark_email_processed(self, email_id: str):
        """Mark email as processed."""
        if "processed_emails" not in self._state:
            self._state["processed_emails"] = []

        if email_id not in self._state["processed_emails"]:
            self._state["processed_emails"].append(email_id)

    def get_processed_since(self, since: datetime) -> set:
        """Get set of email IDs processed since a specific time."""
        processed = self._state.get("processed_emails_details", {})

        result = set()
        for email_id, timestamp_str in processed.items():
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
                if timestamp >= since:
                    result.add(email_id)
            except Exception:
                continue

        return result


class Notifier:
    """Handles notification logic for new assignments from Gmail."""

    def __init__(self, client: GmailClient, state_manager: StateManager):
        self.client = client
        self.state = state_manager

    def check_new_assignments(self, force_all_new: bool = False) -> list[ClassroomAssignment]:
        """Check for new assignments from Gmail."""
        # Get recent Classroom emails (only unread)
        emails = self.client.get_classroom_emails(max_results=50, unread_only=True)

        # Parse emails into assignments
        assignments = []
        processed_ids = []
        
        for email in emails:
            # Skip already processed emails (unless force_all_new)
            if not force_all_new and self.state.is_email_processed(email.id):
                continue

            assignment = EmailParser.parse_email(
                subject=email.subject,
                body=email.body,
                date=email.date,
                email_id=email.id
            )

            if assignment:
                assignments.append(assignment)
                # Mark as processed in state
                self.state.mark_email_processed(email.id)
                # Track for marking as read in Gmail
                processed_ids.append(email.id)

        # Mark processed emails as read in Gmail
        if processed_ids:
            self.client.mark_as_read(processed_ids)
            logger.info(f"Marked {len(processed_ids)} emails as read")

        # Update last check time
        self.state.update_last_check_time()
        self.state.save()

        return assignments

    def get_all_assignments(self) -> list[ClassroomAssignment]:
        """Get all assignments from Gmail (for initial sync)."""
        emails = self.client.get_classroom_emails(max_results=100)

        assignments = []
        for email in emails:
            assignment = EmailParser.parse_email(
                subject=email.subject,
                body=email.body,
                date=email.date,
                email_id=email.id
            )

            if assignment:
                assignments.append(assignment)

        return assignments

    def format_notification(self, assignments: list[ClassroomAssignment]) -> str:
        """Format assignments for display."""
        if not assignments:
            return "No new assignments"

        lines = []
        lines.append(f"New assignments ({len(assignments)}):")
        lines.append("-" * 40)

        for assignment in assignments:
            lines.append(f"Course: {assignment.course_name}")
            lines.append(f"   Assignment: {assignment.assignment_title}")

            # Format received date
            received_str = assignment.received_date.strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"   Received: {received_str}")

            # Format due date
            if assignment.due_date:
                due_str = assignment.due_date.strftime("%Y-%m-%d")
                if assignment.due_time:
                    due_str += f" {assignment.due_time}"
                lines.append(f"   Due: {due_str}")
            else:
                lines.append("   Due: -")

            # Add link if available
            if assignment.link:
                lines.append(f"   Link: {assignment.link}")

            lines.append("-" * 40)

        return "\n".join(lines)