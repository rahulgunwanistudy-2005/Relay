"""Deterministic fallback provider.

Operates on arbitrary valid input — never a canned graph. It preserves the user
text, extracts obvious date/recurrence phrases deterministically, creates one
editable EXECUTE step, and surfaces unknowns as clarification questions rather
than inventing them. It never assigns ownership.
"""

from __future__ import annotations

import datetime as dt
import re

from dateutil.relativedelta import relativedelta

from relay.ai.schemas import ExtractionContext, ResponsibilityGraphDraft, StepDraft
from relay.core.enums import LifecycleKind, Provenance

_RECURRENCE = [
    (re.compile(r"\bevery\s+(\d+)\s+days?\b", re.I), lambda m: f"FREQ=DAILY;INTERVAL={m.group(1)}"),
    (
        re.compile(r"\bevery\s+(\d+)\s+weeks?\b", re.I),
        lambda m: f"FREQ=WEEKLY;INTERVAL={m.group(1)}",
    ),
    (
        re.compile(r"\bevery\s+(\d+)\s+months?\b", re.I),
        lambda m: f"FREQ=MONTHLY;INTERVAL={m.group(1)}",
    ),
    (re.compile(r"\b(every\s*day|daily)\b", re.I), lambda m: "FREQ=DAILY"),
    (re.compile(r"\b(every\s*week|weekly)\b", re.I), lambda m: "FREQ=WEEKLY"),
    (re.compile(r"\b(every\s*month|monthly)\b", re.I), lambda m: "FREQ=MONTHLY"),
    (re.compile(r"\b(every\s*year|yearly|annually)\b", re.I), lambda m: "FREQ=YEARLY"),
]

_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_IN_N = re.compile(r"\bin\s+(\d+)\s+(day|week|month)s?\b", re.I)


def _detect_recurrence(text: str) -> str | None:
    for pattern, build in _RECURRENCE:
        m = pattern.search(text)
        if m:
            return build(m)
    return None


def _detect_deadline(text: str, now: dt.datetime) -> tuple[str, dt.datetime] | None:
    """Return (matched_phrase, resolved_datetime) or None. Conservative: only
    matches clear tokens so we never invent a date."""
    lowered = text.lower()
    if "tomorrow" in lowered:
        return "tomorrow", now + dt.timedelta(days=1)
    if "next week" in lowered:
        return "next week", now + dt.timedelta(days=7)
    if "next month" in lowered:
        return "next month", now + relativedelta(months=1)
    m = _IN_N.search(text)
    if m:
        n, unit = int(m.group(1)), m.group(2).lower()
        if unit == "day":
            return m.group(0), now + dt.timedelta(days=n)
        if unit == "week":
            return m.group(0), now + dt.timedelta(weeks=n)
        return m.group(0), now + relativedelta(months=n)
    m = _ISO_DATE.search(text)
    if m:
        y, mo, d = (int(g) for g in m.groups())
        try:
            resolved = dt.datetime(y, mo, d, 9, 0, tzinfo=now.tzinfo)
            return m.group(0), resolved
        except ValueError:
            return None
    return None


def _title(text: str) -> str:
    first = text.strip().splitlines()[0] if text.strip() else "Untitled responsibility"
    first = re.split(r"[.!?]", first)[0].strip()
    return (first[:297] + "...") if len(first) > 300 else (first or "Untitled responsibility")


class DeterministicFallbackProvider:
    name = "deterministic_fallback"
    model = "rules-v1"
    prompt_version = "fallback-v1"

    def extract(self, text: str, context: ExtractionContext) -> ResponsibilityGraphDraft:
        text = text or ""
        provenance: dict[str, Provenance] = {"title": Provenance.deterministic}

        recurrence = _detect_recurrence(text)
        if recurrence:
            provenance["recurrence_rrule"] = Provenance.deterministic

        deadline = _detect_deadline(text, context.now)
        deadline_text = deadline_at = None
        if deadline:
            deadline_text, deadline_at = deadline
            provenance["deadline_at"] = Provenance.deterministic

        people = [
            p for p in context.known_people if p and re.search(rf"\b{re.escape(p)}\b", text, re.I)
        ]
        if people:
            provenance["people"] = Provenance.user_explicit

        clarifications = ["Who should own this responsibility?"]
        if deadline_at is None:
            clarifications.append("When is this due?")

        step = StepDraft(
            step_key="execute",
            kind=LifecycleKind.execute,
            description=text.strip() or "Complete this responsibility",
            provenance=Provenance.deterministic,
            due_at=deadline_at,
            is_assumption=False,
        )

        return ResponsibilityGraphDraft(
            title=_title(text),
            domain="general",
            people=people,
            deadline_text=deadline_text,
            deadline_at=deadline_at,
            recurrence_rrule=recurrence,
            steps=[step],
            dependencies=[],
            completion_standard=None,
            assumptions=[],
            clarification_questions=clarifications,
            field_provenance=provenance,
            confidence=None,
            source_text=text,
        )
