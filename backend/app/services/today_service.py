"""
Lane-based daily worklist ("Today"), following the Udhaar Ledger case study, Section 6.

    score = overdue_rupees x R x W x C

Lane rules (applied in order, per account):
  1. Any open disputed invoice            -> Resolve (not chased until cleared)
  2. Unresponsive, or oldest overdue > 90 -> Escalate (owner decides)
  3. Otherwise scored; top N              -> Call today; rest -> Message

All weights are the case study's ASSUMPTIONS. They are unvalidated and are
exposed as constants so a backtest can tune them. Patterns are derived only
from this organisation's own invoices, payments and logged follow-ups.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.schemas.today import TodayAccount, TodayResponse

# --- Case-study weights (Assumptions) --------------------------------------
R_FACTORS = {
    "pays_when_asked": 1.0,
    "thin_history": 0.7,
    "no_clear_pattern": 0.7,  # not in the study; treated like thin history
    "missed_promise": 0.6,
    "pays_on_its_own": 0.4,
    "unresponsive": 0.3,
}
# (max_days_inclusive, weight); anything above the last bound uses the final weight.
W_BANDS = [(7, 0.5), (30, 1.0), (60, 1.2), (90, 0.9)]
W_OVER_90 = 0.5
COOLDOWN_DAYS = 3
COOLDOWN_FACTOR = 0.5
ESCALATE_AFTER_DAYS = 90
SELF_PAY_WINDOW_DAYS = 7
THIN_HISTORY_MIN_SETTLED = 3
PROMISE_LOOKBACK_DAYS = 60
UNRESPONSIVE_MIN_CONTACTS = 2
STALE_RECEIPT_DAYS = 3

PATTERN_TEXT = {
    "pays_when_asked": "Usually pays when asked.",
    "pays_on_its_own": "Usually pays on its own.",
    "missed_promise": "Missed a promised pay date.",
    "unresponsive": "Contacted repeatedly with no response.",
    "thin_history": "Limited history (fewer than 3 settled invoices).",
    "no_clear_pattern": "No clear payment pattern yet.",
}


@dataclass
class SettledInvoice:
    due_date: date
    paid_date: date
    had_contact_before_payment: bool


@dataclass
class Contact:
    when: date
    has_promise: bool
    promised_date: Optional[date] = None
    promise_fulfilled: bool = False


@dataclass
class AccountFacts:
    customer_id: UUID
    name: str
    phone: Optional[str]
    overdue_amount: Decimal = Decimal("0")
    oldest_days_past_due: int = 0
    open_invoice_count: int = 0
    invoice_ids: list = field(default_factory=list)
    disputed_numbers: list = field(default_factory=list)
    disputed_ids: list = field(default_factory=list)
    settled: list = field(default_factory=list)  # SettledInvoice
    contacts: list = field(default_factory=list)  # Contact
    last_payment_date: Optional[date] = None


# --- Pure scoring helpers (unit-testable) -----------------------------------
def age_weight(days_past_due: int) -> float:
    for bound, weight in W_BANDS:
        if days_past_due <= bound:
            return weight
    return W_OVER_90


def detect_pattern(f: AccountFacts, today: date) -> str:
    recent = [c for c in f.contacts if (today - c.when).days <= PROMISE_LOOKBACK_DAYS]

    # Missed a promise: a logged promised date passed unpaid in the last 60 days.
    for c in recent:
        if c.promised_date and c.promised_date < today and not c.promise_fulfilled:
            return "missed_promise"

    # Unresponsive: >=2 logged contacts, none produced a promise, no payment since the first.
    unanswered = [c for c in recent if not c.has_promise]
    if len(unanswered) >= UNRESPONSIVE_MIN_CONTACTS:
        first = min(c.when for c in unanswered)
        if f.last_payment_date is None or f.last_payment_date < first:
            return "unresponsive"

    if len(f.settled) < THIN_HISTORY_MIN_SETTLED:
        return "thin_history"

    on_own = [
        s for s in f.settled
        if not s.had_contact_before_payment
        and (s.paid_date - s.due_date).days <= SELF_PAY_WINDOW_DAYS
    ]
    asked = [
        s for s in f.settled
        if s.had_contact_before_payment
        and (s.paid_date - s.due_date).days <= SELF_PAY_WINDOW_DAYS + 30  # paid after chasing
    ]
    recent_settled = sorted(f.settled, key=lambda s: s.paid_date)[-5:]
    on_own_recent = [s for s in recent_settled if s in on_own]
    asked_recent = [s for s in recent_settled if s in asked]
    half = len(recent_settled) / 2
    if len(on_own_recent) > half:
        return "pays_on_its_own"
    if len(asked_recent) > half:
        return "pays_when_asked"
    return "no_clear_pattern"


def compute_score(overdue: Decimal, pattern: str, oldest_days: int, contacted_recently: bool) -> float:
    c = COOLDOWN_FACTOR if contacted_recently else 1.0
    return float(overdue) * R_FACTORS[pattern] * age_weight(oldest_days) * c


def assign_lane(disputed: bool, pattern: str, oldest_days: int) -> Optional[str]:
    """Returns 'resolve' / 'escalate', or None when the account must be scored."""
    if disputed:
        return "resolve"
    if pattern == "unresponsive" or oldest_days > ESCALATE_AFTER_DAYS:
        return "escalate"
    return None


def _inr(x: Decimal) -> str:
    n = int(round(x))
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return f"₹{s}"


def explain(f: AccountFacts, lane: str, pattern: str, days_since_contact: Optional[int]) -> tuple[str, str, str]:
    """Returns (reason, suggested_action, what_would_change); text is generated from the same factors as the score."""
    parts = [f"{_inr(f.overdue_amount)} overdue {f.oldest_days_past_due} days."]
    if lane == "resolve":
        nums = ", ".join(f.disputed_numbers)
        parts = [f"Disputed invoice {nums}. {_inr(f.overdue_amount)} otherwise overdue."]
    parts.append(PATTERN_TEXT[pattern])
    if days_since_contact is None:
        parts.append("Never contacted.")
    elif days_since_contact == 0:
        parts.append("Contacted today.")
    else:
        parts.append(f"Not contacted for {days_since_contact} days." if days_since_contact > COOLDOWN_DAYS
                     else f"Contacted {days_since_contact} days ago.")
    if lane == "escalate" and pattern != "unresponsive":
        parts.append(f"Over {ESCALATE_AFTER_DAYS} days past due.")

    action = {
        "call": "Owner or accountant calls today.",
        "escalate": "Owner decides: visit, hold supply or settle.",
        "resolve": "Resolve the dispute before chasing.",
        "message": "Send a prefilled reminder (you review and send it).",
    }[lane]
    change = {
        "call": "Ranks lower if payment arrives, a promise is logged or the account is contacted today.",
        "escalate": "Leaves Escalate if payment arrives or a promise is logged.",
        "resolve": "Returns to the call list once the dispute is cleared.",
        "message": "Moves up if it stays unpaid or its pattern worsens.",
    }[lane]
    return " ".join(parts), action, change


# --- Data loading (batched; no per-invoice queries) -------------------------
def _load_facts(db: Session, org_id: UUID, today: date) -> dict[UUID, AccountFacts]:
    facts: dict[UUID, AccountFacts] = {}

    open_rows = db.execute(text("""
        SELECT i.id, i.customer_id, i.invoice_number, i.due_date, i.is_disputed,
               i.total_amount - COALESCE(pa.alloc, 0) AS outstanding
        FROM invoices i
        LEFT JOIN (SELECT invoice_id, SUM(allocated_amount) AS alloc
                   FROM payment_allocations GROUP BY invoice_id) pa ON pa.invoice_id = i.id
        WHERE i.org_id = :org AND i.deleted_at IS NULL
          AND i.status NOT IN ('paid', 'cancelled', 'draft')
    """), {"org": str(org_id)}).fetchall()

    cust_ids = {r.customer_id for r in open_rows}
    if not cust_ids:
        return facts
    customers = {
        c.id: c for c in db.query(Customer).filter(
            Customer.org_id == org_id, Customer.id.in_(cust_ids), Customer.deleted_at == None  # noqa: E711
        )
    }

    for r in open_rows:
        cust = customers.get(r.customer_id)
        outstanding = Decimal(str(r.outstanding))
        if cust is None or outstanding <= 0:
            continue
        f = facts.setdefault(cust.id, AccountFacts(cust.id, cust.name, cust.phone))
        if r.is_disputed:
            f.disputed_numbers.append(r.invoice_number)
            f.disputed_ids.append(r.id)
        days = (today - r.due_date).days
        if days > 0:
            f.invoice_ids.append(r.id)
            f.open_invoice_count += 1
            f.overdue_amount += outstanding
            f.oldest_days_past_due = max(f.oldest_days_past_due, days)

    # Only accounts with overdue money or a dispute belong on the list.
    facts = {k: v for k, v in facts.items() if v.overdue_amount > 0 or v.disputed_numbers}
    if not facts:
        return facts

    ids = [str(k) for k in facts]
    contacts_by_inv_customer: dict[UUID, list[Contact]] = defaultdict(list)
    fu_rows = db.execute(text("""
        SELECT customer_id, invoice_id, created_at, promised_date, promise_status
        FROM follow_ups WHERE org_id = :org AND customer_id = ANY(CAST(:ids AS uuid[]))
    """), {"org": str(org_id), "ids": ids}).fetchall()
    contact_dates_by_invoice: dict[UUID, list[date]] = defaultdict(list)
    for r in fu_rows:
        when = r.created_at.astimezone(timezone.utc).date() if r.created_at.tzinfo else r.created_at.date()
        contacts_by_inv_customer[r.customer_id].append(Contact(
            when=when,
            has_promise=r.promised_date is not None,
            promised_date=r.promised_date,
            promise_fulfilled=(r.promise_status == "fulfilled"),
        ))
        contact_dates_by_invoice[r.invoice_id].append(when)
    for cid, lst in contacts_by_inv_customer.items():
        facts[cid].contacts = lst

    settled_rows = db.execute(text("""
        SELECT i.id, i.customer_id, i.due_date, MAX(p.received_date) AS paid_date
        FROM invoices i
        JOIN payment_allocations pa ON pa.invoice_id = i.id
        JOIN payments p ON p.id = pa.payment_id
        WHERE i.org_id = :org AND i.status = 'paid' AND i.deleted_at IS NULL
          AND i.customer_id = ANY(CAST(:ids AS uuid[]))
        GROUP BY i.id, i.customer_id, i.due_date
    """), {"org": str(org_id), "ids": ids}).fetchall()
    for r in settled_rows:
        contacted = any(d <= r.paid_date for d in contact_dates_by_invoice.get(r.id, []))
        facts[r.customer_id].settled.append(SettledInvoice(r.due_date, r.paid_date, contacted))

    for r in db.execute(text("""
        SELECT customer_id, MAX(received_date) AS last_paid FROM payments
        WHERE org_id = :org AND customer_id = ANY(CAST(:ids AS uuid[])) GROUP BY customer_id
    """), {"org": str(org_id), "ids": ids}):
        facts[r.customer_id].last_payment_date = r.last_paid
    return facts


def get_today(db: Session, org_id: UUID, call_slots: int = 5, today: Optional[date] = None) -> TodayResponse:
    today = today or date.today()
    facts = _load_facts(db, org_id, today)

    scored: list[tuple[float, TodayAccount]] = []
    lanes: dict[str, list[TodayAccount]] = {"call": [], "escalate": [], "resolve": [], "message": []}

    def build(f: AccountFacts, lane: str, pattern: str, score: Optional[float]) -> TodayAccount:
        last_contact = max((c.when for c in f.contacts), default=None)
        since = (today - last_contact).days if last_contact else None
        reason, action, change = explain(f, lane, pattern, since)
        return TodayAccount(
            customer_id=f.customer_id, customer_name=f.name, customer_phone=f.phone, lane=lane,
            overdue_amount=f.overdue_amount, oldest_days_past_due=f.oldest_days_past_due,
            open_invoice_count=f.open_invoice_count, pattern=pattern,
            limited_history=pattern == "thin_history",
            score=round(score, 2) if score is not None else None,
            reason=reason, suggested_action=action, what_would_change=change,
            days_since_last_contact=since, invoice_ids=f.invoice_ids,
            disputed_invoice_numbers=f.disputed_numbers,
            disputed_invoice_ids=f.disputed_ids,
        )

    for f in facts.values():
        pattern = detect_pattern(f, today)
        lane = assign_lane(bool(f.disputed_numbers), pattern, f.oldest_days_past_due)
        if lane:
            lanes[lane].append(build(f, lane, pattern, None))
            continue
        last_contact = max((c.when for c in f.contacts), default=None)
        recent = last_contact is not None and (today - last_contact).days <= COOLDOWN_DAYS
        s = compute_score(f.overdue_amount, pattern, f.oldest_days_past_due, recent)
        scored.append((s, build(f, "message", pattern, s)))

    scored.sort(key=lambda x: x[0], reverse=True)
    for i, (_, acct) in enumerate(scored):
        acct.lane = "call" if i < call_slots else "message"
        if acct.lane == "call":
            acct.reason, acct.suggested_action, acct.what_would_change = explain(
                facts[acct.customer_id], "call", acct.pattern, acct.days_since_last_contact)
        lanes[acct.lane].append(acct)

    lanes["escalate"].sort(key=lambda a: a.overdue_amount, reverse=True)
    lanes["resolve"].sort(key=lambda a: a.overdue_amount, reverse=True)

    last_receipt = db.execute(
        text("SELECT MAX(received_date) FROM payments WHERE org_id = :org"), {"org": str(org_id)}
    ).scalar()
    since_receipt = (today - last_receipt).days if last_receipt else None

    return TodayResponse(
        as_of=today, call_slots=call_slots,
        call=lanes["call"], escalate=lanes["escalate"], resolve=lanes["resolve"], message=lanes["message"],
        days_since_last_receipt=since_receipt,
        data_stale=since_receipt is None or since_receipt > STALE_RECEIPT_DAYS,
    )
