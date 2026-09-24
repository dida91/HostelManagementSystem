"""Fee structures, monthly invoicing, overdue marking, reminders and payments."""

from __future__ import annotations

import asyncio
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from api_helpers import h, login, mina, new_room, new_student, notifications, sita, warden
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal
from app.models.enums import InvoiceStatus, NotificationCategory, PaymentMethod
from app.models.finance import FeeInvoice
from app.models.notification import Notification
from app.models.user import Student, User
from app.services.finance import FinanceService

pytestmark = pytest.mark.asyncio


async def _sita_ids(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    """(student_id, user_id) of a seeded resident who is always active."""
    row = (
        await session.execute(
            select(Student.id, Student.user_id)
            .join(User, User.id == Student.user_id)
            .where(User.email == "sita@kutumba.local")
        )
    ).one()
    return row[0], row[1]


async def _resident(client: AsyncClient, staff: dict[str, str], rate: int = 9000) -> tuple:
    """A student living in a fresh room at `rate` NPR per month."""
    room = await new_room(client, staff, rate=rate)
    student, password = await new_student(client, staff)
    r = await client.post(
        "/api/v1/rooms/allocations",
        headers=staff,
        json={
            "student_id": student["id"],
            "bed_id": room["beds"][0]["id"],
            "from_date": "2026-01-01",
        },
    )
    assert r.status_code == 201, r.text
    return student, password


async def test_fee_structures_are_warden_managed(client: AsyncClient) -> None:
    staff = await warden(client)
    body = {
        "name": "Laundry",
        "amount_npr": "500.00",
        "cadence": "MONTHLY",
        "effective_from": "2040-01-01",
        "effective_to": "2040-01-31",
    }
    assert (
        await client.post("/api/v1/fees/structures", headers=await sita(client), json=body)
    ).status_code == 403

    created = await client.post("/api/v1/fees/structures", headers=staff, json=body)
    assert created.status_code == 201, created.text
    sid = created.json()["id"]

    edited = await client.patch(
        f"/api/v1/fees/structures/{sid}", headers=staff, json={"amount_npr": "550.00"}
    )
    assert edited.status_code == 200 and Decimal(edited.json()["amount_npr"]) == Decimal("550")

    inverted = await client.patch(
        f"/api/v1/fees/structures/{sid}", headers=staff, json={"effective_to": "2039-12-31"}
    )
    assert inverted.status_code == 422

    assert (await client.delete(f"/api/v1/fees/structures/{sid}", headers=staff)).status_code == 204


async def test_monthly_generation_bills_rent_plus_fees_once(client: AsyncClient) -> None:
    staff = await warden(client)
    student, password = await _resident(client, staff, rate=9000)
    # A fee that applies only in this test's month, so no other test sees it.
    await client.post(
        "/api/v1/fees/structures",
        headers=staff,
        json={
            "name": "Mess fee",
            "amount_npr": "4500",
            "effective_from": "2031-03-01",
            "effective_to": "2031-03-31",
        },
    )

    first = await client.post(
        "/api/v1/fees/invoices/generate", headers=staff, json={"period": "2031-03", "due_day": 7}
    )
    assert first.status_code == 200, first.text
    mine = [i for i in first.json()["invoices"] if i["student_id"] == student["id"]]
    assert len(mine) == 1
    invoice = mine[0]
    assert invoice["billing_period"] == "2031-03"
    assert invoice["due_date"] == "2031-03-07"
    assert Decimal(invoice["total_npr"]) == Decimal("13500")

    again = await client.post(
        "/api/v1/fees/invoices/generate", headers=staff, json={"period": "2031-03"}
    )
    assert again.json()["created"] == 0
    assert again.json()["skipped_existing"] >= 1

    # The student sees the invoice, its lines and the new balance.
    resident = h(await login(client, student["email"], password))
    detail = await client.get(f"/api/v1/fees/invoices/{invoice['id']}", headers=resident)
    assert detail.status_code == 200
    lines = {
        li["description"]: Decimal(li["unit_amount_npr"]) for li in detail.json()["line_items"]
    }
    assert Decimal("9000") in lines.values() and Decimal("4500") in lines.values()
    assert Decimal(detail.json()["outstanding_npr"]) == Decimal("13500")
    balance = (await client.get("/api/v1/fees/balance", headers=resident)).json()
    assert Decimal(balance["outstanding"]) == Decimal("13500")
    assert "INVOICE_ISSUED" in [n["category"] for n in await notifications(client, resident)]

    # Nobody else can read it.
    assert (
        await client.get(f"/api/v1/fees/invoices/{invoice['id']}", headers=await mina(client))
    ).status_code == 404


async def test_concurrent_generation_never_double_bills(client: AsyncClient) -> None:
    """Two runs at once (scheduler + a warden's click): the partial unique index
    on (student, billing_period) must hold."""
    staff = await warden(client)
    await _resident(client, staff)

    async def run() -> None:
        async with AsyncSessionLocal() as s:
            await FinanceService(s).generate_monthly_invoices(year=2032, month=5, due_day=10)
            await s.commit()

    await asyncio.gather(run(), run())

    async with AsyncSessionLocal() as s:
        per_student = (
            await s.execute(
                select(FeeInvoice.student_id, func.count(FeeInvoice.id))
                .where(FeeInvoice.billing_period == "2032-05")
                .group_by(FeeInvoice.student_id)
            )
        ).all()
    assert per_student, "residents should have been billed"
    assert all(count == 1 for _, count in per_student)


async def test_invoice_numbers_are_unique_and_sequential(session: AsyncSession) -> None:
    sid, _ = await _sita_ids(session)
    service = FinanceService(session)
    items = [("Damage charge", Decimal("1"), Decimal("250"))]
    a = await service.issue_invoice(
        student_id=sid,
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 30),
        due_date=date(2026, 10, 7),
        line_items=items,
    )
    b = await service.issue_invoice(
        student_id=sid,
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 30),
        due_date=date(2026, 10, 7),
        line_items=items,
    )
    assert a.invoice_number != b.invoice_number
    assert int(b.invoice_number.rsplit("-", 1)[1]) > int(a.invoice_number.rsplit("-", 1)[1])


async def test_zero_total_invoice_is_rejected_cleanly(client: AsyncClient) -> None:
    staff = await warden(client)
    sid = (await client.get("/api/v1/students", headers=staff)).json()["items"][0]["id"]
    r = await client.post(
        "/api/v1/fees/invoices",
        headers=staff,
        json={
            "student_id": sid,
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "due_date": "2026-10-07",
            "line_items": [{"description": "Waived", "quantity": 1, "unit_amount_npr": 0}],
        },
    )
    assert r.status_code == 422, "used to be a 500 from the ledger's amount > 0 check"


async def test_overdue_marking_and_reminders_notify_once(session: AsyncSession) -> None:
    sid, user_id = await _sita_ids(session)
    service = FinanceService(session)
    today = date(2031, 6, 15)
    items = [("Hostel fee", Decimal("1"), Decimal("8000"))]
    late = await service.issue_invoice(
        student_id=sid,
        period_start=date(2031, 5, 1),
        period_end=date(2031, 5, 31),
        due_date=today - timedelta(days=5),
        line_items=items,
    )
    soon = await service.issue_invoice(
        student_id=sid,
        period_start=date(2031, 6, 1),
        period_end=date(2031, 6, 30),
        due_date=today + timedelta(days=2),
        line_items=items,
    )

    marked = await service.mark_overdue(today=today)
    assert late in marked and soon not in marked
    assert late.status is InvoiceStatus.OVERDUE
    assert late not in await service.mark_overdue(today=today), "already overdue"

    assert await service.send_due_reminders(today=today, days_before=3) >= 1
    assert await service.send_due_reminders(today=today, days_before=3) == 0, "reminded once"

    counts = dict(
        (
            await session.execute(
                select(Notification.category, func.count(Notification.id))
                .where(
                    Notification.user_id == user_id,
                    Notification.dedupe_key.in_(
                        [f"fee_overdue:{late.id}", f"fee_reminder:{soon.id}:{soon.due_date}"]
                    ),
                )
                .group_by(Notification.category)
            )
        )
        .tuples()
        .all()
    )
    assert counts == {NotificationCategory.FEE_OVERDUE: 1, NotificationCategory.FEE_REMINDER: 1}


async def test_payment_rules(client: AsyncClient) -> None:
    staff = await warden(client)
    student, password = await _resident(client, staff)
    other, _ = await new_student(client, staff)
    invoice = (
        await client.post(
            "/api/v1/fees/invoices",
            headers=staff,
            json={
                "student_id": student["id"],
                "period_start": "2026-09-01",
                "period_end": "2026-09-30",
                "due_date": "2099-01-01",
                "line_items": [{"description": "Hostel fee", "unit_amount_npr": 8000}],
            },
        )
    ).json()

    def pay(student_id: str, amount: int) -> dict:
        return {
            "headers": {**staff, "Idempotency-Key": str(uuid.uuid4())},
            "json": {
                "student_id": student_id,
                "amount_npr": amount,
                "method": "ESEWA",
                "invoice_id": invoice["id"],
            },
        }

    wrong_owner = await client.post("/api/v1/fees/payments", **pay(other["id"], 8000))
    assert wrong_owner.status_code == 422, "one student's payment cannot settle another's invoice"

    part = await client.post("/api/v1/fees/payments", **pay(student["id"], 3000))
    assert part.status_code == 201
    detail = (await client.get(f"/api/v1/fees/invoices/{invoice['id']}", headers=staff)).json()
    assert detail["status"] == "PARTIALLY_PAID"
    assert Decimal(detail["outstanding_npr"]) == Decimal("5000")

    rest = await client.post("/api/v1/fees/payments", **pay(student["id"], 5000))
    assert rest.status_code == 201
    detail = (await client.get(f"/api/v1/fees/invoices/{invoice['id']}", headers=staff)).json()
    assert detail["status"] == "PAID"

    resident = h(await login(client, student["email"], password))
    received = [
        n for n in await notifications(client, resident) if n["category"] == "PAYMENT_RECEIVED"
    ]
    assert len(received) == 2
    assert "your eSewa payment" in received[0]["body"]

    # Residents read these lines in their account history: no internal ids.
    ledger = (await client.get("/api/v1/fees/ledger", headers=resident)).json()
    credits = [e["description"] for e in ledger if e["entry_type"] == "CREDIT"]
    assert credits == [f"Payment by eSewa for {invoice['invoice_number']}"] * 2


async def test_part_payment_does_not_cure_an_overdue_invoice(session: AsyncSession) -> None:
    sid, _ = await _sita_ids(session)
    service = FinanceService(session)
    invoice = await service.issue_invoice(
        student_id=sid,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        due_date=date(2026, 1, 10),
        line_items=[("Hostel fee", Decimal("1"), Decimal("8000"))],
    )
    await service.mark_overdue(today=date(2026, 2, 1))
    await service.record_payment(
        student_id=sid,
        amount=Decimal("1000"),
        method=PaymentMethod.CASH,
        idempotency_key=f"test-{uuid.uuid4()}",
        received_by_user_id=None,
        invoice_id=invoice.id,
    )
    assert invoice.status is InvoiceStatus.OVERDUE


async def test_invoice_lists_name_the_student(client: AsyncClient) -> None:
    staff = await warden(client)
    student, _ = await _resident(client, staff)
    await client.post(
        "/api/v1/fees/invoices",
        headers=staff,
        json={
            "student_id": student["id"],
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "due_date": "2026-10-07",
            "line_items": [{"description": "Key replacement", "unit_amount_npr": 300}],
        },
    )
    page = (
        await client.get(f"/api/v1/fees/invoices?student_id={student['id']}", headers=staff)
    ).json()
    assert page["items"][0]["student_name"] == student["full_name"]
    assert page["items"][0]["student_code"] == student["student_code"]
