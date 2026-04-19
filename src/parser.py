"""Parser for extracting assignment info from Classroom emails."""

import logging
import re
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ClassroomAssignment:
    """Extracted assignment information from email."""

    course_name: str  # Предмет
    assignment_title: str  # Название задания
    received_date: datetime  # Дата получения
    email_id: str
    due_date: datetime | None = None  # Дедлайн
    due_time: str | None = None
    link: str | None = None
    teacher_name: str | None = None  # Имя учителя


class EmailParser:
    """Parser for Google Classroom notification emails."""

    # Subject patterns - English
    # "New assignment in Mathematics 101: Homework #5"
    SUBJECT_PATTERN_EN = re.compile(
        r"New assignment in (.+?):\s*(.+)$",
        re.IGNORECASE
    )

    # Subject patterns - Ukrainian
    # "Нове завдання у Mathematics 101: Homework #5"
    # "Нове завдання: Homework Title" (new format)
    # "Fwd: Нове завдання: Title"
    SUBJECT_PATTERN_UK = re.compile(
        r"(?:Fwd:\s*)?Нове завдання\s*:?\s*(.+)$",
        re.IGNORECASE
    )

    # Subject pattern - from forwarded messages with new assignment
    # "Fwd: Нове завдання: Title"
    SUBJECT_PATTERN_NEW_ASSIGNMENT = re.compile(
        r"(?:Fwd:\s*)?Нове завдання\s*:\s*(.+)$",
        re.IGNORECASE
    )

    # Subject pattern - from forwarded messages with private comment
    # "Fwd: Додано приватний коментар у стрічку "Lab work""
    SUBJECT_PATTERN_FWD = re.compile(
        r"(?:Fwd:)\s*(?:Додано приватний коментар у стрічку|New private comment added to thread)\s+[\"'\"]*(.+?)[\"'\"]*",
        re.IGNORECASE
    )

    # Due date patterns in email body
    # "Due: April 24, 2026 at 11:59 PM"
    # "Термін: 24 квітня 2026"
    DUE_DATE_PATTERN = re.compile(
        r"(?:Due:|Термін:|Срок выполнения:)\s*(.+?)(?:\s*at\s+(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)))?",
        re.IGNORECASE
    )

    # Teacher name pattern
    # "Від: Гонтковська Олександра Юріївна (Клас) <no-reply@classroom.google.com>"
    TEACHER_PATTERN = re.compile(
        r"Від:\s*([^\n<]+?)\s*\([^\)]*\)\s*<",
        re.IGNORECASE
    )

    # Course/Subject pattern from body
    # "8-В Інтегрований курс МИСТЕЦТВО"
    # Looks for subject after "курс" or at the start of a line
    COURSE_PATTERN = re.compile(
        r"(?:курс\s+)?([А-Яа-яЁёІЇЄєїЄ]{4,})",
        re.IGNORECASE
    )

    # Link pattern
    LINK_PATTERN = re.compile(
        r"https://classroom\.google\.com/[a-zA-Z0-9/_\-]+",
        re.IGNORECASE
    )

    @classmethod
    def parse_email(cls, subject: str, body: str, date: datetime, email_id: str) -> ClassroomAssignment | None:
        """Parse an email to extract assignment info."""
        try:
            course_name = None
            assignment_title = None

            # Try English pattern: "New assignment in Course: Title"
            match = cls.SUBJECT_PATTERN_EN.search(subject)
            if match:
                course_name = match.group(1).strip()
                assignment_title = match.group(2).strip()

            # Try Ukrainian pattern for new assignment: "Fwd: Нове завдання: Title"
            if not assignment_title:
                match = cls.SUBJECT_PATTERN_NEW_ASSIGNMENT.search(subject)
                if match:
                    full_text = match.group(1).strip()
                    course_name = "Unknown"
                    assignment_title = full_text

            # Try other Ukrainian patterns
            if not assignment_title:
                match = cls.SUBJECT_PATTERN_UK.search(subject)
                if match:
                    full_text = match.group(1).strip()
                    course_name = "Unknown"
                    assignment_title = full_text

            # Try forwarded message pattern (private comment - NOT assignment)
            if not assignment_title:
                match = cls.SUBJECT_PATTERN_FWD.search(subject)
                if match:
                    logger.debug(f"Skipping non-assignment email: {subject}")
                    return None

            if not assignment_title:
                logger.debug(f"Could not parse subject: {subject}")
                return None

            # Extract teacher name
            teacher_name = None
            teacher_match = cls.TEACHER_PATTERN.search(body)
            if teacher_match:
                teacher_name = teacher_match.group(1).strip()

            # Extract due date from body
            due_date = None
            due_time = None

            due_match = cls.DUE_DATE_PATTERN.search(body)
            if due_match:
                due_date_str = due_match.group(1).strip()
                due_time = due_match.group(2)

                due_date = cls._parse_due_date(due_date_str)

            # If course is still "Unknown", try to extract from body
            # Look for pattern like "8-В Інтегрований курс МИСТЕЦТВО"
            if course_name == "Unknown" or not course_name:
                course_match = cls.COURSE_PATTERN.search(body)
                if course_match:
                    extracted = course_match.group(1).strip().upper()
                    # Map common subjects
                    subject_map = {
                        "МИСТЕЦТВО": "Мистецтво",
                        "БІОЛОГІЯ": "Біологія",
                        "ФІЗИКА": "Фізика",
                        "ХІМІЯ": "Хімія",
                        "ГЕОГРАФІЯ": "Географія",
                        "ІНФОРМАТИКА": "Інформатика",
                        "АЛГЕБРА": "Алгебра",
                        "ГЕОМЕТРІЯ": "Геометрія",
                        "ІСТОРІЯ": "Історія України",
                        "УКРАЇНСЬКА": "Українська мова",
                        "АНГЛІЙСЬКА": "Англійська мова",
                    }
                    course_name = subject_map.get(extracted, extracted.lower())

            # Extract link
            link = cls.LINK_PATTERN.search(body)

            return ClassroomAssignment(
                course_name=course_name,
                assignment_title=assignment_title,
                received_date=date,
                due_date=due_date,
                due_time=due_time,
                link=link.group(0) if link else None,
                email_id=email_id,
                teacher_name=teacher_name,
            )

        except Exception as e:
            logger.warning(f"Failed to parse email: {e}")
            return None

    @classmethod
    def _parse_due_date(cls, date_str: str) -> datetime | None:
        """Parse various date string formats."""
        from dateutil import parser as date_parser

        try:
            # Try dateutil which handles most formats
            return date_parser.parse(date_str, fuzzy=True)
        except Exception:
            pass

        # Manual parsing for common formats
        month_names = {
            "january": 1, "jan": 1,
            "february": 2, "feb": 2,
            "march": 3, "mar": 3,
            "april": 4, "apr": 4,
            "may": 5,
            "june": 6, "jun": 6,
            "july": 7, "jul": 7,
            "august": 8, "aug": 8,
            "september": 9, "sep": 9, "sept": 9,
            "october": 10, "oct": 10,
            "november": 11, "nov": 11,
            "december": 12, "dec": 12,
        }

        # Try format: "April 24, 2026"
        match = re.match(r"(\w+)\s+(\d+),?\s+(\d{4})", date_str, re.IGNORECASE)
        if match:
            month_name = match.group(1).lower()
            if month_name in month_names:
                try:
                    return datetime(
                        int(match.group(3)),
                        month_names[month_name],
                        int(match.group(2)),
                        23, 59, 59
                    )
                except ValueError:
                    pass

        # Try format: "24 April 2026"
        match = re.match(r"(\d+)\s+(\w+)\s+(\d{4})", date_str, re.IGNORECASE)
        if match:
            month_name = match.group(2).lower()
            if month_name in month_names:
                try:
                    return datetime(
                        int(match.group(3)),
                        month_names[month_name],
                        int(match.group(1)),
                        23, 59, 59
                    )
                except ValueError:
                    pass

        logger.warning(f"Could not parse due date: {date_str}")
        return None


def parse_emails(emails: list) -> list[ClassroomAssignment]:
    """Parse a list of emails into assignments."""
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