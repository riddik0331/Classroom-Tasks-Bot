"""Timetable management and next lesson calculation."""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import openpyxl

logger = logging.getLogger(__name__)


class Timetable:
    """Manages school timetable."""

    # Subject name mapping - normalize subject names
    SUBJECT_MAP = {
        "біологія": "біологія",
        "історія україни": "історія україни",
        "всесвітня історія": "всесвітня історія",
        "фізика": "фізика",
        "фізична культура": "фізична культура",
        "алгебра": "алгебра",
        "геометрія": "геометрія",
        "українська мова": "українська мова",
        "українська література": "українська література",
        "зарубіжна література": "зарубіжна література",
        "англійська мова": "англійська мова",
        "хімія": "хімія",
        "географія": "географія",
        "інформатика": "інформатика",
        "мистецтво": "мистецтво",
        "збд": "збд",
        "технології": "технології",
        "підприємство і фінансова грамотність": "підприємство і фінансова грамотність",
        "громадянська освіта": "громадянська освіта",
    }

    # Teacher to subject mapping
    TEACHER_TO_SUBJECT = {
        "шевченко альона юріївна": "біологія",
        "романів юрій андрійович": "історія україни",
        "вельможко василь іванович": "фізика",
        "тимошина валерія валеріївна": "фізична культура",
        "горова ольга михайлівна": "алгебра",
        "нетребенко жанна ігорівна": "українська мова",
        "сташевський даніель ростиславович": "англійська мова",
        "стаматакі єлизавета андріївна": "зарубіжна література",
        "хільчевська дарія володимирівна": "інформатика",
        "гонтковська олександра юріївна": "мистецтво",
        "куцебо оксана миколаївна": "хімія",
        "юраш анастасія сергіївна": "географія",
        "петренко таїсія георгіївна": "технології",
    }

    def __init__(self, timetable_file: str = "timetable.xlsx"):
        self.timetable_file = Path(timetable_file)
        self.schedule = {}  # {(week_type, day): [(time_start, subject), ...]}
        self._load_timetable()

    def _load_timetable(self):
        """Load timetable from Excel."""
        if not self.timetable_file.exists():
            logger.warning(f"Timetable file not found: {self.timetable_file}")
            return

        wb = openpyxl.load_workbook(self.timetable_file, read_only=True)
        ws = wb["Timetable"]

        current_week = None
        current_day = None

        for row in ws.iter_rows(values_only=True):
            # Detect week type
            if row[0] == "Непарний Тиждень":
                current_week = "odd"
                current_day = None
                continue
            elif row[0] == "Парний Тиждень":
                current_week = "even"
                current_day = None
                continue

            # Detect day
            days = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота", "Неділя"]
            if row[0] in days:
                current_day = row[0]
                continue

            # Skip empty rows
            if not row[2]:
                continue

            # Parse time and subject
            time_start = row[0]
            subject = row[2]

            if time_start and subject and current_week and current_day:
                key = (current_week, current_day)
                if key not in self.schedule:
                    self.schedule[key] = []
                self.schedule[key].append((time_start, subject.strip().lower()))

        logger.info(f"Loaded timetable with {len(self.schedule)} schedule entries")

    def get_subject_from_teacher(self, teacher_name: str) -> Optional[str]:
        """Get subject from teacher name."""
        if not teacher_name:
            return None
        
        # Normalize teacher name
        normalized = teacher_name.lower().strip()
        
        # Try exact match
        if normalized in self.TEACHER_TO_SUBJECT:
            return self.TEACHER_TO_SUBJECT[normalized]
        
        # Try partial match
        for teacher_key, subject in self.TEACHER_TO_SUBJECT.items():
            if teacher_key in normalized or normalized in teacher_key:
                return subject
        
        return None

    def normalize_subject(self, subject: str) -> str:
        """Normalize subject name for matching."""
        if not subject:
            return ""
        
        subject = subject.lower().strip()
        
        # Remove quotes and extra spaces
        subject = subject.replace('"', '').replace("'", "").strip()
        
        # Try to match known subjects
        for known, normalized in self.SUBJECT_MAP.items():
            if known in subject or subject in known:
                return normalized
        
        # Try partial match
        for known in self.SUBJECT_MAP:
            if known.split()[0] == subject.split()[0] if subject.split() else "":
                return known
        
        return subject

    def is_odd_week(self, date: datetime) -> bool:
        """Check if week is odd (1st, 3rd, 5th week of month)."""
        # Week number from start of month (1-based)
        week_num = (date.day - 1) // 7 + 1
        return week_num % 2 == 1

    def get_week_type(self, date: datetime) -> str:
        """Get week type (odd/even) for specific date."""
        return "odd" if self.is_odd_week(date) else "even"

    def get_day_name(self, date: datetime) -> str:
        """Get day name in Ukrainian."""
        days = {
            0: "Понеділок",
            1: "Вівторок",
            2: "Середа",
            3: "Четвер",
            4: "П'ятниця",
            5: "Субота",
            6: "Неділя",
        }
        return days.get(date.weekday(), "")

    def find_next_lesson(self, subject: str, after_date: datetime) -> Optional[datetime]:
        """Find next lesson for subject after given date."""
        normalized_subject = self.normalize_subject(subject)
        
        if not normalized_subject:
            return None

        # Search for the next 14 days
        search_date = after_date + timedelta(days=1)
        
        for _ in range(14):
            week_type = self.get_week_type(search_date)
            day_name = self.get_day_name(search_date)
            
            key = (week_type, day_name)
            if key in self.schedule:
                for time_start, schedule_subject in self.schedule[key]:
                    if self._subject_matches(schedule_subject, normalized_subject):
                        # Parse time
                        hour, minute = map(int, time_start.split(":"))
                        next_date = search_date.replace(hour=hour, minute=minute, second=0)
                        
                        # Skip if it's in the past
                        if next_date > after_date:
                            return next_date
            
            search_date += timedelta(days=1)

        return None

    def _subject_matches(self, schedule_subject: str, target_subject: str) -> bool:
        """Check if subjects match."""
        # Direct match
        if schedule_subject == target_subject:
            return True
        
        # Partial match (first word)
        schedule_words = schedule_subject.split()
        target_words = target_subject.split()
        
        if schedule_words and target_words:
            return schedule_words[0] == target_words[0]
        
        return False

    def get_schedule_for_day(self, date: datetime) -> list[tuple]:
        """Get schedule for specific day."""
        week_type = self.get_week_type(date)
        day_name = self.get_day_name(date)
        
        key = (week_type, day_name)
        return self.schedule.get(key, [])


def calculate_due_date(received_date: datetime, subject: str, teacher_name: str = None, timetable_file: str = "timetable.xlsx") -> Optional[datetime]:
    """Calculate due date for assignment based on timetable."""
    timetable = Timetable(timetable_file)
    
    # Try to get subject from teacher if not provided
    final_subject = subject
    if (not final_subject or final_subject == "Unknown") and teacher_name:
        subject_from_teacher = timetable.get_subject_from_teacher(teacher_name)
        if subject_from_teacher:
            final_subject = subject_from_teacher
            logger.info(f"Got subject from teacher: {final_subject}")
    
    if not final_subject or final_subject == "Unknown":
        return None
    
    return timetable.find_next_lesson(final_subject, received_date)