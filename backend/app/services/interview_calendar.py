"""Export interview appointments as RFC 5545 iCalendar text."""

from datetime import datetime, timezone

from app.models.interview import Interview

UTC = timezone.utc  # noqa: UP017


def utc_stamp(value: datetime) -> str:
    """Return an RFC 5545 UTC datetime value."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def escape_ical(value: str) -> str:
    """Escape TEXT values without creating new calendar properties."""
    return (
        value.replace("\\", "\\\\")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def fold_line(line: str) -> str:
    """
    Fold at no more than 75 UTF-8 octets per physical line.

    Continuation lines begin with one space.
    """
    pieces: list[str] = []
    current = ""

    for char in line:
        candidate = current + char

        if len(candidate.encode("utf-8")) > 75:
            pieces.append(current)
            current = " " + char
        else:
            current = candidate

    pieces.append(current)
    return "\r\n".join(pieces)


def render_interview_calendar(
    interview: Interview,
    *,
    job_title: str,
    company_name: str,
    now: datetime | None = None,
) -> str:
    """Generate a downloadable VEVENT. Nothing is sent externally."""

    current = now or datetime.now(UTC)
    summary = (
        f"{interview.title} - "
        f"{job_title} at {company_name}"
    )

    description = (
        interview.notes
        or "Interview details recorded in the AI Job Agent."
    )

    fields = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//AI Job Agent//Interview Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{interview.id}@ai-job-agent.local",
        f"DTSTAMP:{utc_stamp(current)}",
        f"DTSTART:{utc_stamp(interview.starts_at)}",
        f"DTEND:{utc_stamp(interview.ends_at)}",
        f"SEQUENCE:{interview.version - 1}",
        (
            "STATUS:CANCELLED"
            if interview.status == "cancelled"
            else "STATUS:CONFIRMED"
        ),
        f"SUMMARY:{escape_ical(summary)}",
        f"DESCRIPTION:{escape_ical(description)}",
    ]

    if interview.location_or_link:
        fields.append(
            "LOCATION:"
            + escape_ical(interview.location_or_link)
        )

    fields.extend(
        ["END:VEVENT", "END:VCALENDAR"]
    )

    return "\r\n".join(fold_line(field) for field in fields) + "\r\n"