"""Phone normalisation and message composition."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.models.enums import LeaveStatus
from app.services.notifications import (
    compose_email_text,
    fee_overdue_message,
    leave_decided_message,
    normalise_nepal_mobile,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("9812345678", "9812345678"),
        ("+977-981-2345678", "9812345678"),
        ("977 9712345678", "9712345678"),
        ("9612345678", "9612345678"),
        ("061-521234", None),  # Pokhara landline
        ("981234567", None),  # too short
        ("+1 415 555 0100", None),
        ("", None),
        (None, None),
    ],
)
def test_normalise_nepal_mobile(raw: str | None, expected: str | None) -> None:
    assert normalise_nepal_mobile(raw) == expected


def test_money_and_dates_are_formatted_for_people() -> None:
    m = fee_overdue_message(
        invoice_number="INV-202610-00042", amount_due=Decimal("12500"), due_date=date(2026, 10, 10)
    )
    assert "NPR 12,500.00" in m.body and "10 Oct 2026" in m.body
    assert m.sms is not None and len(m.sms) <= 160


def test_leave_decision_carries_the_note_but_sms_stays_short() -> None:
    m = leave_decided_message(
        status=LeaveStatus.APPROVED,
        leave_type="HOME_VISIT",
        from_date=date(2026, 10, 1),
        to_date=date(2026, 10, 5),
        note="Return before 7 pm.",
    )
    assert "approved" in m.body and "Return before 7 pm." in m.body
    assert m.sms is not None and "Return before" not in m.sms


def test_email_body_links_to_the_portal() -> None:
    m = fee_overdue_message(
        invoice_number="INV-1", amount_due=Decimal("1"), due_date=date(2026, 1, 1)
    )
    body = compose_email_text(m)
    assert body.startswith(m.body)
    assert "/fees" in body and "automated message" in body
