"""Telegram bot for Google Classroom assignments."""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from . import config
from .gmail_client import GmailClient
from .notifier import Notifier, StateManager
from .storage import AssignmentStorage
from .parser import parse_emails

logger = logging.getLogger(__name__)


class ClassroomBot:
    """Telegram bot for managing assignments."""

    def __init__(self, token: str, storage_file: str = "assignments.xlsx", timetable_file: str = "timetable.xlsx"):
        self.token = token
        self.storage = AssignmentStorage(storage_file, timetable_file)
        self._gmail_client = None
        self._notifier = None

    @property
    def gmail_client(self):
        """Lazy initialization of Gmail client."""
        if self._gmail_client is None:
            cfg = config.load_config()
            self._gmail_client = GmailClient(cfg.credentials_file, cfg.token_file)
        return self._gmail_client

    @property
    def notifier(self):
        """Lazy initialization of notifier."""
        if self._notifier is None:
            state = StateManager("/tmp/gcn_state.json")
            self._notifier = Notifier(self.gmail_client, state)
        return self._notifier

    def check_new_emails(self) -> int:
        """Check for new emails and save to storage."""
        try:
            emails = self.gmail_client.get_classroom_emails(max_results=50, unread_only=True)
            
            if not emails:
                return 0

            assignments = parse_emails(emails)
            
            for assignment in assignments:
                self.storage.add_assignment(assignment)

            # Mark as read
            if emails:
                self.gmail_client.mark_as_read([e.id for e in emails])

            logger.info(f"Added {len(assignments)} new assignments")
            return len(assignments)

        except Exception as e:
            logger.error(f"Failed to check emails: {e}")
            return 0

    def format_assignments(self, assignments: list[dict]) -> str:
        """Format assignments for display."""
        if not assignments:
            return "Нет заданий 😔"

        lines = []
        
        # Group by date
        from collections import defaultdict
        by_date = defaultdict(list)
        for a in assignments:
            due = a.get("due_date", "Без срока")
            by_date[due].append(a)

        # Format each date group
        for date in sorted(by_date.keys()):
            # Convert date to Ukrainian format
            date_obj = None
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d").date()
            except:
                pass
            
            # Format date in Ukrainian
            if date_obj:
                months_uk = {
                    1: "січня", 2: "лютого", 3: "березня", 4: "квітня",
                    5: "травня", 6: "червня", 7: "липня", 8: "серпня",
                    9: "вересня", 10: "жовтня", 11: "листопада", 12: "грудня"
                }
                # Check if it's today or tomorrow
                today = datetime.now().date()
                if date_obj == today:
                    date_str_uk = "Сьогодні"
                elif date_obj == today + timedelta(days=1):
                    date_str_uk = "Завтра"
                else:
                    day = date_obj.day
                    month = months_uk.get(date_obj.month, "")
                    year = date_obj.year
                    date_str_uk = f"{day} {month} {year}"
            else:
                date_str_uk = date
            
            lines.append(f"📅 <b>Завдання на {date_str_uk}</b>")
            
            for a in by_date[date]:
                subject = a.get("course", "Неизвестно")
                title = a.get("title", "Нет названия")
                teacher = a.get("teacher", "")
                
                lines.append(f"  📚 {subject}")
                lines.append(f"     📝 {title[:50]}...")
                if teacher:
                    lines.append(f"     👨‍🏫 {teacher}")
                lines.append("")

        return "\n".join(lines)

    def get_assignments_for_period(self, days: int) -> list[dict]:
        """Get assignments for next N days."""
        all_assignments = self.storage.get_assignments(completed=False)
        
        today = datetime.now().date()
        end_date = today + timedelta(days=days)
        
        result = []
        for a in all_assignments:
            due_str = a.get("due_date")
            if due_str:
                try:
                    due_date = datetime.strptime(due_str, "%Y-%m-%d").date()
                    if today <= due_date <= end_date:
                        result.append(a)
                except:
                    pass
        
        # Sort by date
        result.sort(key=lambda x: x.get("due_date", ""))
        return result


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_text(
        "Привет! Я бот для отслеживания заданий Google Classroom.\n\n"
        "Нажми кнопку ниже, чтобы получить задания.",
        reply_markup=get_main_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await update.message.reply_text(
        "Команды:\n"
        "/start - Начать\n"
        "/today - Задания на сегодня\n"
        "/tomorrow - Задания на завтра\n"
        "/week - Задания на неделю\n"
        "/refresh - Проверить почту и обновить"
    )


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show today's assignments."""
    app = context.bot_data.get("app")
    if not app:
        return

    bot = app.bot_data.get("classroom_bot")
    today = datetime.now().strftime("%Y-%m-%d")
    assignments = bot.storage.get_assignments_for_date(today)
    
    text = f"📅 Задания на сегодня ({today}):\n\n"
    text += bot.format_assignments(assignments)
    
    await update.message.reply_text(text, parse_mode="HTML")


async def tomorrow_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show tomorrow's assignments."""
    app = context.bot_data.get("app")
    if not app:
        return

    bot = app.bot_data.get("classroom_bot")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    assignments = bot.storage.get_assignments_for_date(tomorrow)
    
    text = f"📅 Задания на завтра ({tomorrow}):\n\n"
    text += bot.format_assignments(assignments)
    
    await update.message.reply_text(text, parse_mode="HTML")


async def week_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show week's assignments."""
    app = context.bot_data.get("app")
    if not app:
        return

    bot = app.bot_data.get("classroom_bot")
    assignments = bot.get_assignments_for_period(7)
    
    text = "📅 Задания на ближайшую неделю:\n\n"
    text += bot.format_assignments(assignments)
    
    await update.message.reply_text(text, parse_mode="HTML")


async def refresh_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check new emails and refresh."""
    app = context.bot_data.get("app")
    if not app:
        return

    bot = app.bot_data.get("classroom_bot")
    
    await update.message.reply_text("🔄 Проверяю почту...")
    
    count = bot.check_new_emails()
    
    if count > 0:
        await update.message.reply_text(f"✅ Добавлено {count} новых заданий!")
    else:
        await update.message.reply_text("✅ Новых заданий нет.")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()
    
    app = context.bot_data.get("app")
    if not app:
        return

    bot = app.bot_data.get("classroom_bot")
    
    if query.data == "refresh":
        await query.edit_message_text("🔄 Проверяю почту...")
        count = bot.check_new_emails()
        
        if count > 0:
            await query.edit_message_text(f"✅ Добавлено {count} новых заданий!")
        else:
            await query.edit_message_text("✅ Новых заданий нет.")
    
    elif query.data == "today":
        today = datetime.now().strftime("%Y-%m-%d")
        assignments = bot.storage.get_assignments_for_date(today)
        text = f"📅 Задания на сегодня ({today}):\n\n"
        text += bot.format_assignments(assignments)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=get_main_keyboard())
    
    elif query.data == "tomorrow":
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        assignments = bot.storage.get_assignments_for_date(tomorrow)
        text = f"📅 Задания на завтра ({tomorrow}):\n\n"
        text += bot.format_assignments(assignments)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=get_main_keyboard())
    
    elif query.data == "week":
        assignments = bot.get_assignments_for_period(7)
        text = "📅 Задания на ближайшую неделю:\n\n"
        text += bot.format_assignments(assignments)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=get_main_keyboard())
    
    elif query.data == "form":
        # First refresh, then show week
        await query.edit_message_text("🔄 Проверяю почту и формирую список...")
        
        count = bot.check_new_emails()
        
        assignments = bot.get_assignments_for_period(7)
        
        if count > 0:
            text = f"✅ Добавлено {count} новых заданий!\n\n"
        else:
            text = "✅ Новых заданий нет.\n\n"
        
        text += "📅 Задания на ближайшую неделю:\n\n"
        text += bot.format_assignments(assignments)
        
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=get_main_keyboard())


def get_main_keyboard():
    """Get main keyboard with buttons."""
    from telegram import KeyboardButton, ReplyKeyboardMarkup
    
    keyboard = [
        [KeyboardButton("🔄 Сформировать"), KeyboardButton("📅 Сегодня")],
        [KeyboardButton("📅 Завтра"), KeyboardButton("📅 Неделя")],
    ]
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def run_bot(token: str, storage_file: str = "assignments.xlsx", timetable_file: str = "timetable.xlsx"):
    """Run the Telegram bot."""
    # Create bot instance
    classroom_bot = ClassroomBot(token, storage_file, timetable_file)
    
    # Build application
    application = Application.builder().token(token).build()
    
    # Store bot in bot_data
    application.bot_data["classroom_bot"] = classroom_bot
    application.bot_data["app"] = application
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("today", today_command))
    application.add_handler(CommandHandler("tomorrow", tomorrow_command))
    application.add_handler(CommandHandler("week", week_command))
    application.add_handler(CommandHandler("refresh", refresh_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Start polling
    application.run_polling(pending_updates=True)