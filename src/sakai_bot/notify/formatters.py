"""
Message formatters for Telegram notifications.

Formats scraped data into clean, readable Telegram messages.
"""

from datetime import datetime, timezone

from sakai_bot.models import Announcement, Assignment, Exam


class MessageFormatter:
    """
    Formats notification content for Telegram messages.

    Creates well-structured, emoji-enhanced messages that are
    easy to read on mobile devices.
    """

    # Maximum message length for Telegram (4096 chars, but we leave buffer)
    MAX_LENGTH = 3500

    @staticmethod
    def _truncate(text: str, max_length: int = 500) -> str:
        """Truncate text with ellipsis if too long."""
        if len(text) <= max_length:
            return text
        return text[: max_length - 3].rsplit(" ", 1)[0] + "..."

    @staticmethod
    def _format_datetime(dt: datetime | None) -> str:
        """Format datetime for display."""
        if dt is None:
            return "Not specified"
        return dt.strftime("%a, %b %d, %Y at %I:%M %p")

    @staticmethod
    def _format_date(dt: datetime | None) -> str:
        """Format date only for display."""
        if dt is None:
            return "Not specified"
        return dt.strftime("%a, %b %d, %Y")

    @classmethod
    def format_announcement(cls, announcement: Announcement) -> str:
        """
        Format an announcement for WhatsApp notification.

        Args:
            announcement: The announcement to format

        Returns:
            str: Formatted message string
        """
        # Clean and truncate content
        content = announcement.content.strip()
        content = cls._truncate(content, 800)

        # Build message
        lines = [
            "📢 *NEW ANNOUNCEMENT*",
            "",
            f"📚 *Course:* {announcement.course_code}",
            f"📝 *Title:* {announcement.title}",
        ]

        if announcement.author:
            lines.append(f"👤 *Posted by:* {announcement.author}")

        if announcement.posted_at:
            lines.append(f"🕐 *Date:* {cls._format_datetime(announcement.posted_at)}")

        lines.extend(
            [
                "",
                "─" * 20,
                "",
                content,
            ]
        )

        if announcement.url:
            lines.extend(
                [
                    "",
                    f"🔗 View: {announcement.url}",
                ]
            )

        return "\n".join(lines)

    @classmethod
    def format_assignment(cls, assignment: Assignment) -> str:
        """
        Format an assignment for WhatsApp notification.

        Args:
            assignment: The assignment to format

        Returns:
            str: Formatted message string
        """
        lines = [
            "📋 *NEW ASSIGNMENT*",
            "",
            f"📚 *Course:* {assignment.course_code}",
            f"📝 *Title:* {assignment.title}",
        ]

        if assignment.due_date:
            # Add urgency indicator
            days_until = (assignment.due_date - datetime.now(timezone.utc)).days
            if days_until < 0:
                urgency = "⚠️ OVERDUE"
            elif days_until == 0:
                urgency = "🔴 DUE TODAY"
            elif days_until <= 2:
                urgency = "🟠 DUE SOON"
            elif days_until <= 7:
                urgency = "🟡"
            else:
                urgency = "🟢"

            lines.append(f"📅 *Due:* {cls._format_datetime(assignment.due_date)} {urgency}")

        if assignment.open_date:
            lines.append(f"📆 *Opens:* {cls._format_datetime(assignment.open_date)}")

        if assignment.max_points:
            lines.append(f"🎯 *Points:* {assignment.max_points}")

        if assignment.description:
            description = cls._truncate(assignment.description, 500)
            lines.extend(
                [
                    "",
                    "─" * 20,
                    "",
                    description,
                ]
            )

        if assignment.url:
            lines.extend(
                [
                    "",
                    f"🔗 View: {assignment.url}",
                ]
            )

        return "\n".join(lines)

    @classmethod
    def format_exam(cls, exam: Exam) -> str:
        """
        Format an exam notification for WhatsApp.

        Args:
            exam: The exam to format

        Returns:
            str: Formatted message string
        """
        # Choose emoji based on exam type
        type_emoji = {
            "exam": "📝",
            "midterm": "📊",
            "final": "🎓",
            "quiz": "❓",
            "test": "✍️",
        }.get(exam.exam_type.lower(), "📝")

        lines = [
            f"🚨 *{exam.exam_type.upper()} ALERT* {type_emoji}",
            "",
            f"📚 *Course:* {exam.course_code}",
            f"📝 *Title:* {exam.title}",
        ]

        if exam.exam_date:
            # Calculate days until exam
            days_until = (exam.exam_date - datetime.now(timezone.utc)).days
            if days_until < 0:
                countdown = "(Already passed)"
            elif days_until == 0:
                countdown = "🔴 TODAY!"
            elif days_until == 1:
                countdown = "🟠 TOMORROW!"
            elif days_until <= 7:
                countdown = f"🟡 In {days_until} days"
            else:
                countdown = f"In {days_until} days"

            lines.append(f"📅 *Date:* {cls._format_date(exam.exam_date)} {countdown}")

        if exam.exam_time:
            lines.append(f"🕐 *Time:* {exam.exam_time}")

        if exam.location:
            lines.append(f"📍 *Location:* {exam.location}")

        if exam.duration_minutes:
            hours = exam.duration_minutes // 60
            minutes = exam.duration_minutes % 60
            duration_str = ""
            if hours:
                duration_str += f"{hours}h "
            if minutes:
                duration_str += f"{minutes}m"
            lines.append(f"⏱️ *Duration:* {duration_str.strip()}")

        if exam.notes:
            notes = cls._truncate(exam.notes, 300)
            lines.extend(
                [
                    "",
                    "─" * 20,
                    "",
                    f"📌 {notes}",
                ]
            )

        if exam.url:
            lines.extend(
                [
                    "",
                    f"🔗 More info: {exam.url}",
                ]
            )

        return "\n".join(lines)

    @classmethod
    def format_summary(
        cls,
        announcements_count: int = 0,
        assignments_count: int = 0,
        exams_count: int = 0,
    ) -> str:
        """
        Format a summary message after a monitoring run.

        Args:
            announcements_count: Number of new announcements
            assignments_count: Number of new assignments
            exams_count: Number of new exams detected

        Returns:
            str: Formatted summary message
        """
        total = announcements_count + assignments_count + exams_count

        if total == 0:
            return "✅ *Sakai Bot Check Complete*\n\nNo new updates found."

        lines = [
            "📊 *Sakai Bot Summary*",
            "",
        ]

        if announcements_count:
            lines.append(f"📢 {announcements_count} new announcement(s)")
        if assignments_count:
            lines.append(f"📋 {assignments_count} new assignment(s)")
        if exams_count:
            lines.append(f"🚨 {exams_count} exam/quiz alert(s)")

        lines.extend(
            [
                "",
                f"_Total: {total} new update(s)_",
            ]
        )

        return "\n".join(lines)

    @classmethod
    def format_error(cls, error_message: str) -> str:
        """
        Format an error notification.

        Args:
            error_message: The error to report

        Returns:
            str: Formatted error message
        """
        return (
            "⚠️ *Sakai Bot Error*\n\n"
            f"An error occurred during monitoring:\n\n"
            f"```{cls._truncate(error_message, 500)}```\n\n"
            "_Please check the logs for more details._"
        )
