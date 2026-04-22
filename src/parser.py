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
    assignment_text: str = ""  # Повний текст завдання
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
    # "на четвер двадцять третє квітня 2026 року"
    DUE_DATE_PATTERN = re.compile(
        r"(?:Due:|Термін:|Срок выполнения:)\s*(.+?)(?:\s*at\s+(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)))?",
        re.IGNORECASE
    )
    
    # Pattern for Ukrainian date in title: "на четвер двадцять третє квітня 2026 року"
    DUE_DATE_UK_PATTERN = re.compile(
        r"на\s+\w+\s+((?:двадцять\s+)?\w+)\s+(\w+)\s+(\d{4})",
        re.IGNORECASE
    )

    # Teacher name pattern
    # Format 1: "Від: Гонтковська Олександра Юріївна (Клас) <no-reply@classroom.google.com>"
    # Format 2: "Опубліковано 9:17 дп, квіт. 20 користувачем Горова Ольга Михайлівна"
    TEACHER_PATTERN = re.compile(
        r"Від:\s*([^\n<]+?)\s*\([^\)]*\)\s*<",
        re.IGNORECASE
    )
    
    # Pattern for extracting teacher from "published by" line
    # Match until newline or "Google"
    PUBLISHED_BY_PATTERN = re.compile(
        r"користувачем\s+([^\n]+)",
        re.IGNORECASE
    )

    # Course/Subject pattern from body
    # Format 1: "8-В Інтегрований курс МИСТЕЦТВО"
    # Format 2: "8-В Геометрія" (just subject after class)
    # Format 3: "8-В клас Біологія /ЗБД"
    COURSE_PATTERN = re.compile(
        r"курс\s+([А-ЯЁёІЇЄЄ]{4,})",
        re.IGNORECASE
    )
    
    # Pattern for "8-В Геометрія" or "8-В клас Біологія /ЗБД"
    CLASS_SUBJECT_PATTERN = re.compile(
        r"8-В\s+(?:клас\s+)?([А-Яа-яёЇІЄєі]+(?:\s*/\s*[А-Яа-яёЇІЄєі]+)?)",
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

            # Try to extract course: first from email subject, then from teacher
            if not course_name or course_name == "Unknown":
                try:
                    from .subject_mappings import EMAIL_SUBJECT_MAP, TEACHER_SUBJECTS

                    # 1. Try email subject pattern
                    for email_pattern, timetable_subject in EMAIL_SUBJECT_MAP.items():
                        if email_pattern.lower() in subject.lower():
                            course_name = timetable_subject
                            break

                    # 2. If not found, try teacher last name
                    if not course_name or course_name == "Unknown":
                        for teacher_key, subjects in TEACHER_SUBJECTS.items():
                            if teacher_key.split()[0].lower() in subject.lower():
                                course_name = subjects[0]
                                break
                except Exception:
                    pass

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
            
            # Fallback: extract from "користувачем" line
            if not teacher_name:
                published_match = cls.PUBLISHED_BY_PATTERN.search(body)
                if published_match:
                    teacher_name = published_match.group(1).strip()
                    logger.debug(f"Teacher from 'користувачем': {teacher_name}")

            # Extract due date from body
            due_date = None
            due_time = None

            due_match = cls.DUE_DATE_PATTERN.search(body)
            if due_match:
                due_date_str = due_match.group(1).strip()
                due_time = due_match.group(2)

                due_date = cls._parse_due_date(due_date_str)
            
            # Fallback: try Ukrainian pattern from body "на четвер двадцять третє квітня 2026"
            # Note: subject may be truncated, so search in body too
            if not due_date:
                due_match_uk = cls.DUE_DATE_UK_PATTERN.search(assignment_title)
                if not due_match_uk:
                    due_match_uk = cls.DUE_DATE_UK_PATTERN.search(body)
                
                if due_match_uk:
                    day_words = due_match_uk.group(1).lower()
                    month_name = due_match_uk.group(2).lower()
                    year = int(due_match_uk.group(3))
                    
                    # Ukrainian number words
                    uk_numbers = {
                        "перше": 1, "друге": 2, "третє": 3, "четверте": 4, "п'яте": 5,
                        "шосте": 6, "сьоме": 7, "восьме": 8, "дев'яте": 9, "десяте": 10,
                        "одинадцяте": 11, "дванадцяте": 12, "тринадцяте": 13, "чотирнадцяте": 14, "п'ятнадцяте": 15,
                        "шістнадцяте": 16, "сімнадцяте": 17, "вісімнадцяте": 18, "дев'ятнадцяте": 19, "двадцяте": 20,
                        "двадцять": 20, "двадцять перше": 21, "двадцять друге": 22, "двадцять третє": 23,
                    }
                    
                    day = uk_numbers.get(day_words)
                    month_map = {
                        "січня": 1, "лютого": 2, "березня": 3, "квітня": 4,
                        "травня": 5, "червня": 6, "липня": 7, "серпня": 8,
                        "вересня": 9, "жовтня": 10, "листопада": 11, "грудня": 12,
                    }
                    
                    if day and month_name in month_map:
                        try:
                            due_date = datetime(year, month_map[month_name], day, 23, 59, 59)
                            logger.debug(f"Due date from Ukrainian pattern: {due_date}")
                        except ValueError as e:
                            logger.warning(f"Invalid date: {day}/{month_map[month_name]}/{year}: {e}")

            # If course is still "Unknown", try to extract from email subject pattern
            # Look for pattern like "8-В Інтегрований курс МИСТЕЦТВО" or "8-В Геометрія"
            if course_name == "Unknown" or not course_name:
                course_match = cls.COURSE_PATTERN.search(body)
                if course_match:
                    extracted = course_match.group(1).strip()
                    # Use email subject mapping
                    try:
                        from .subject_mappings import EMAIL_SUBJECT_MAP
                        course_name = EMAIL_SUBJECT_MAP.get(extracted, extracted)
                    except Exception:
                        pass
                
                # Also try "8-В Геометрія" pattern
                if not course_name or course_name == "Unknown":
                    class_match = cls.CLASS_SUBJECT_PATTERN.search(body)
                    if class_match:
                        extracted = class_match.group(1).strip()
                        # Handle "Біологія /ЗБД" format - take first
                        if "/" in extracted:
                            extracted = extracted.split("/")[0].strip()
                        course_name = extracted
                        logger.debug(f"Course from '8-В' pattern: {course_name}")

            # Extract full assignment text from body - ALWAYS from body, not subject
            assignment_text = cls._extract_assignment_text(body)
            
            # If still empty, try to get from body directly after "Нове завдання" marker
            if not assignment_text or len(assignment_text) < 10:
                lines = body.split('\n')
                capture = False
                parts = []
                for line in lines:
                    if 'Нове завдання' in line:
                        capture = True
                        continue
                    if capture:
                        # Stop at common markers
                        lower = line.lower()
                        if any(m in lower for m in ['докладніше', 'докладно', 'детальніше', 'опубліковано', 'https://', 'налаштування']):
                            break
                        if line.strip():
                            parts.append(line.strip())
                if parts:
                    assignment_text = ' '.join(parts)

            # If still no due date, try AI to extract from assignment text
            if not due_date and assignment_text:
                try:
                    from .ai_analyzer import AIAnalyzer
                    ai = AIAnalyzer()
                    if ai.is_available():
                        ai_due = ai.extract_due_date(assignment_text)
                        if ai_due:
                            due_date = ai_due
                            logger.info(f"AI extracted due date: {due_date}")
                except Exception as e:
                    logger.debug(f"AI due date extraction failed: {e}")

            # If still Unknown, try teacher mapping + AI fallback
            if not course_name or course_name == "Unknown":
                if teacher_name:
                    # First try teacher mapping
                    try:
                        from .subject_mappings import TEACHER_SUBJECTS
                        for teacher_key, subjects in TEACHER_SUBJECTS.items():
                            if teacher_key.lower() in teacher_name.lower() or teacher_name.lower() in teacher_key.lower():
                                if len(subjects) == 1:
                                    # Only one subject - use it
                                    course_name = subjects[0]
                                else:
                                    # Multiple subjects - use AI to determine
                                    try:
                                        from .ai_analyzer import AIAnalyzer
                                        ai = AIAnalyzer()
                                        if ai.is_available() and assignment_text:
                                            ai_subject = ai.analyze_subject(assignment_text, teacher_name)
                                            if ai_subject:
                                                course_name = ai_subject
                                                logger.info(f"AI determined subject: {course_name} for teacher {teacher_name}")
                                            else:
                                                course_name = subjects[0]  # Fallback to first
                                        else:
                                            course_name = subjects[0]
                                    except Exception as e:
                                        logger.warning(f"AI analysis failed: {e}")
                                        course_name = subjects[0]
                                break
                    except Exception as e:
                        logger.warning(f"Teacher mapping failed: {e}")
                        pass

            # Extract link
            link = cls.LINK_PATTERN.search(body)

            return ClassroomAssignment(
                course_name=course_name,
                assignment_title=assignment_title,
                assignment_text=assignment_text,
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
    def _extract_assignment_text(cls, body: str) -> str:
        """Extract full assignment text from email body (no truncation)."""
        try:
            # Handle forwarded messages - skip header
            lines = body.split('\n')
            
            # Find where forwarded message content starts
            start_idx = 0
            for i, line in enumerate(lines):
                if '---------- Forwarded message' in line or 'Forwarded message' in line:
                    start_idx = i + 1
                    break
            
            # Process lines from forwarded message content
            capturing = False
            text_parts = []
            skip_empty = True  # Skip first empty lines after marker
            
            for line in lines[start_idx:]:
                # Skip header lines like "Subject:", "To:", "Від:", "Date:", "8-В"
                line_lower = line.lower()
                if line_lower.startswith(('subject:', 'to:', 'від:', 'date:', 'cc:', 'bcc:')):
                    continue
                # Skip "8-В Алгебра" like patterns
                import re
                if re.match(r'^\d+-[А-Яа-яІіЇїЄє]\s+\D+', line) or re.match(r'^\[image:', line):
                    continue
                
                # Find "Нове завдання" (standalone, not in subject line)
                if ('Нове завдання' in line or 'New assignment' in line) and not line_lower.startswith('subject'):
                    # Start capturing AFTER this line - skip empty lines first
                    skip_empty = True
                    continue
                
                # After finding "Нове завдання", skip empty lines
                if skip_empty:
                    if not line.strip():
                        continue
                    # Found first non-empty line after marker - start capturing
                    skip_empty = False
                
                # Stop ONLY at "Докладніше" (or similar)
                if 'докладніше' in line_lower or 'детальніше' in line_lower:
                    # Stop BEFORE this line
                    break
                
                # Skip other markers but keep the text
                if any(m in line_lower for m in [
                    'оцінки', 'матеріали', 'додатково', 
                    'коментар', 'відповісти', 'опубліковано',
                    'настройка сповіщень', 'налаштування сповіщень',
                ]):
                    continue
                
                # Keep the line
                if line.strip():
                    text_parts.append(line.strip())
            
            full_text = ' '.join(text_parts)
            # Clean up only obvious junk - keep URLs in assignment text
            import re
            full_text = re.sub(r'\[image:[^\]]+\]', '', full_text)
            full_text = re.sub(r'<[^>]+>(?!\s*https?://)', '', full_text)  # Keep URLs
            full_text = re.sub(r'Налаштування сповіщень', '', full_text, flags=re.IGNORECASE)
            full_text = re.sub(r'To:\s*\S+@\S+', '', full_text)
            # Keep URLs but clean up email addresses
            full_text = re.sub(r'<\S+@\S+\.\S+>', '', full_text)
            full_text = full_text.strip()
            
            return full_text[:2000] if full_text else ""
            
        except Exception as e:
            logger.warning(f"Failed to extract assignment text: {e}")
            return ""

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

    @classmethod
    def _guess_course_from_teacher(cls, teacher_name: str) -> str | None:
        """Guess course from teacher's name."""
        if not teacher_name:
            return None

        teacher_lower = teacher_name.lower()

        # Map teachers to subjects
        teacher_map = {
            "гонтковська": "Мистецтво",
            "сидоренко": "Українська мова",
            "колесник": "Англійська мова",
            "шіхтар": "Фізика",
            "ланій": "Біологія",
            "ткаченко": "Історія України",
            "шевченко": "Геометрія",
            "бондаренко": "Алгебра",
            "максимчук": "Хімія",
            "старовір": "Географія",
            "павленко": "Інформатика",
        }

        for name, course in teacher_map.items():
            if name in teacher_lower:
                return course

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