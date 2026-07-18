"""
Message formatters for Telegram notifications.

Formats scraped data into clean, readable Telegram messages.
"""

from datetime import datetime, timezone

from sakai_bot.models import Announcement, Assignment, Exam, Resource


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
    def format_reminder(
        cls,
        item: Assignment | Exam,
        due: datetime,
        hours_left: float,
    ) -> str:
        """
        Format a deadline reminder for an assignment or exam.

        Args:
            item: The assignment or exam being reminded about
            due: The deadline (timezone-aware)
            hours_left: Hours remaining until the deadline

        Returns:
            str: Formatted message string
        """
        if hours_left >= 24:
            time_left = f"about {int(round(hours_left / 24))} day(s)"
            urgency = "🟡"
        elif hours_left >= 6:
            time_left = f"about {int(round(hours_left))} hours"
            urgency = "🟠"
        else:
            time_left = f"about {int(round(hours_left))} hour(s)"
            urgency = "🔴"

        kind = "EXAM" if isinstance(item, Exam) else "ASSIGNMENT"

        lines = [
            f"⏰ *{kind} REMINDER* {urgency}",
            "",
            f"📚 *Course:* {item.course_code}",
            f"📝 *Title:* {item.title}",
            f"📅 *Due:* {cls._format_datetime(due)}",
            f"⏳ *Time left:* {time_left}",
        ]

        if isinstance(item, Exam):
            if item.exam_time:
                lines.append(f"🕐 *Time:* {item.exam_time}")
            if item.location:
                lines.append(f"📍 *Location:* {item.location}")

        if item.url:
            lines.extend(["", f"🔗 View: {item.url}"])

        return "\n".join(lines)

    @classmethod
    def format_resource(cls, resource: Resource) -> str:
        """
        Format a new course file notification.

        Args:
            resource: The uploaded resource

        Returns:
            str: Formatted message string
        """
        lines = [
            "📁 *NEW COURSE FILE*",
            "",
            f"📚 *Course:* {resource.course_code}",
            f"📄 *File:* {resource.title}",
        ]

        if resource.container:
            lines.append(f"🗂 *Folder:* {resource.container}")

        if resource.author:
            lines.append(f"👤 *Uploaded by:* {resource.author}")

        if resource.modified_at:
            lines.append(f"🕐 *Uploaded:* {cls._format_datetime(resource.modified_at)}")

        if resource.size_bytes:
            lines.append(f"💾 *Size:* {cls._format_size(resource.size_bytes)}")

        if resource.url:
            lines.extend(["", f"🔗 Download: {resource.url}"])

        return "\n".join(lines)

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format a file size in human-readable units."""
        size = float(size_bytes)
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024 or unit == "GB":
                return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
            size /= 1024
        return f"{size_bytes} B"

    @classmethod
    def format_digest(
        cls,
        assignments: list[Assignment],
        exams: list[Exam],
    ) -> str:
        """
        Format the weekly digest of upcoming deadlines.

        Args:
            assignments: Assignments due in the coming week, sorted by date
            exams: Exams scheduled in the coming week, sorted by date

        Returns:
            str: Formatted message string
        """
        lines = [
            "🗓 *WEEKLY DIGEST — The Week Ahead*",
            "",
        ]

        if not assignments and not exams:
            lines.append("No deadlines found for the coming week. 🎉")
            return "\n".join(lines)

        if assignments:
            lines.append("📋 *Assignments due:*")
            for a in assignments:
                lines.append(f"• {cls._format_date(a.due_date)} — {a.course_code}: {a.title}")
            lines.append("")

        if exams:
            lines.append("🚨 *Exams & quizzes:*")
            for e in exams:
                entry = f"• {cls._format_date(e.exam_date)} — {e.course_code}: {e.title}"
                if e.exam_time:
                    entry += f" ({e.exam_time})"
                lines.append(entry)
            lines.append("")

        total = len(assignments) + len(exams)
        lines.append(f"_Total: {total} deadline(s) in the next 7 days_")

        return "\n".join(lines)

    @classmethod
    def format_summary(
        cls,
        announcements_count: int = 0,
        assignments_count: int = 0,
        exams_count: int = 0,
        resources_count: int = 0,
    ) -> str:
        """
        Format a summary message after a monitoring run.

        Args:
            announcements_count: Number of new announcements
            assignments_count: Number of new assignments
            exams_count: Number of new exams detected
            resources_count: Number of new course files

        Returns:
            str: Formatted summary message
        """
        total = announcements_count + assignments_count + exams_count + resources_count

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
        if resources_count:
            lines.append(f"📁 {resources_count} new course file(s)")

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
