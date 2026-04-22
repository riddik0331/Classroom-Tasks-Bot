"""AI Analyzer for assignment subject detection using Groq."""
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Load .env at module start
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)

# Subjects list for AI to choose from
SUBJECTS = [
    "Мистецтво",
    "Біологія",
    "ЗБД",
    "Фізика",
    "Хімія",
    "Географія",
    "Інформатика",
    "Алгебра",
    "Геометрія",
    "Історія України",
    "Всесвітня Історія",
    "Громадянська Освіта",
    "Українська мова",
    "Українська література",
    "Англійська мова",
    "Зарубіжна література",
    "Фізична культура",
    "Технології",
    "Підприємництво і фінансова грамотність",
]


class AIAnalyzer:
    """Analyze assignment to detect subject using Groq AI."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self._client = None

        if not self.api_key:
            logger.warning("GROQ_API_KEY not found in environment")
            return

        try:
            from groq import Groq
            self._client = Groq(api_key=self.api_key)
            logger.info("Groq AI initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Groq: {e}")
            self._client = None

    def is_available(self) -> bool:
        """Check if AI is available."""
        return self._client is not None

    def analyze_subject(self, assignment_text: str, teacher: str = "") -> Optional[str]:
        """
        Analyze assignment text and determine the subject.

        Args:
            assignment_text: Full text of the assignment
            teacher: Teacher name (optional)

        Returns:
            Subject name from SUBJECTS list, or None if uncertain
        """
        if not self._client:
            return None

        try:
            prompt = self._build_prompt(assignment_text, teacher)
            
            chat_completion = self._client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.1,
                max_tokens=50,
            )

            result = chat_completion.choices[0].message.content.strip()
            logger.info(f"AI detected subject: {result}")

            # Validate result is in SUBJECTS
            for subject in SUBJECTS:
                if subject.lower() in result.lower():
                    return subject

            return None

        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return None
    
    def full_parse_email(self, email_text: str, teacher: str = "") -> Optional[dict]:
        """
        Parse email with AI to extract:
        - subject (Предмет)
        - teacher (Учитель)
        - title (Название задания)
        - full_text (Полный текст задания)
        - email_date (Дата когда пришло письмо)
        """
        if not self._client:
            return None

        prompt = f"""Ти - асистент для парсингу листів Google Classroom.
Проаналізуй текст листа і витягни всю інформацію.

Email text:
{email_text[:2000]}

Виведи результат у форматі JSON (тільки JSON, без додаткового тексту):
{{
  "subject": "Назва предмета",
  "teacher": "ПІБ вчителя",
  "title": "Коротка назва завдання",
  "full_text": "Повний текст завдання",
  "email_date": "YYYY-MM-DD"
}}

Правила:
- subject: тільки з списку: Алгебра, Геометрія, Біологія, Фізика, Хімія, Українська мова, Англійська мова, Німецька мова, Історія України, Всесвітня історія, Географія, Правознавство, Фізична культура, Захист Вітчизни, Основи здоров'я, Музичне мистецтво, Образотворче мистецтво, Технології, Інформатика
- teacher: ПІБ вчителя
- title: перші 100 символів завдання
- full_text: повний текст між "Нове завдання" і "Докладніше"
- email_date: дата у форматі YYYY-MM-DD (коли прийшло завдання)
"""

        try:
            chat_completion = self._client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.1,
                max_tokens=500,
            )

            import json
            result_text = chat_completion.choices[0].message.content.strip()
            
            # Parse JSON
            try:
                # Remove markdown if present
                if "```json" in result_text:
                    result_text = result_text.split("```json")[1].split("```")[0]
                elif "```" in result_text:
                    result_text = result_text.split("```")[1].split("```")[0]
                
                result = json.loads(result_text.strip())
                logger.info(f"AI parsed: subject={result.get('subject')}, teacher={result.get('teacher')}")
                return result
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse AI JSON: {result_text[:200]}")
                return None

        except Exception as e:
            logger.error(f"AI parse error: {e}")
            return None
    
    def _build_prompt(self, assignment_text: str, teacher: str) -> str:
        """Build prompt for AI."""
        subjects_str = ", ".join(SUBJECTS)

        prompt = f"""Проаналізуй завдання та визнач предмет.

ЗАВДАННЯ: {assignment_text[:500]}
{"ВИКЛАДАЧ: " + teacher if teacher else ""}

СПИСОК ПРЕДМЕТІВ: {subjects_str}

ВІДПОВІДЬ: Напиши ТІЛЬКИ назву предмета зі списку вище.
Якщо завдання стосується кількох предметів - вибери найголовніший.
Якщо не впевнений - напиши "Невідомо".
"""
        return prompt

    def extract_due_date(self, assignment_text: str) -> Optional[datetime]:
        """Extract due date from assignment text using AI."""
        if not self._client:
            return None

        try:
            prompt = self._build_due_date_prompt(assignment_text)
            
            chat_completion = self._client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.1,
                max_tokens=100,
            )

            result = chat_completion.choices[0].message.content.strip()
            logger.info(f"AI extracted due date: {result}")

            # Parse the result
            return self._parse_ai_due_date(result)

        except Exception as e:
            logger.error(f"AI due date extraction failed: {e}")
            return None

    def _build_due_date_prompt(self, assignment_text: str) -> str:
        """Build prompt for due date extraction."""
        prompt = f"""Знайди дедлайн (дату) у тексті завдання.

ЗАВДАННЯ: {assignment_text[:800]}

ВІДПОВІДЬ: Напиши дату у форматі "день.місяць.рік" (наприклад: 23.04.2026)
Якщо дедлайн не вказаний - напиши "Немає".
Шукай такі варіанти:
- "до [дата]"
- "на [день тижня] [дата]"
- "до [дня]"
- "виконати до [дата]"
- просто дата у тексті
"""
        return prompt

    def _parse_ai_due_date(self, result: str) -> Optional[datetime]:
        """Parse AI response to extract due date."""
        import re
        from dateutil import parser as date_parser

        if not result or "немає" in result.lower() or "none" in result.lower():
            return None

        # Try to parse "день.місяць.рік" format
        match = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', result)
        if match:
            try:
                day = int(match.group(1))
                month = int(match.group(2))
                year = int(match.group(3))
                return datetime(year, month, day, 23, 59, 59)
            except ValueError:
                pass

        # Try dateutil for other formats
        try:
            return date_parser.parse(result, fuzzy=True)
        except Exception:
            pass

        return None


def analyze_with_ai(assignment_text: str, teacher: str = "") -> Optional[str]:
    """Quick function to analyze subject."""
    analyzer = AIAnalyzer()
    if analyzer.is_available():
        return analyzer.analyze_subject(assignment_text, teacher)
    return None