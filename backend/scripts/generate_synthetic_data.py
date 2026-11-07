"""
Generate reproducible synthetic dataset for Udhaar Ledger.

Generates:
- 1 Organization: Sharma Distributors Pvt Ltd
- 1 seeded admin record (admin@sharma-dist.com). Sign-in is via Clerk, so its local
  password is random and unused unless INITIAL_ADMIN_PASSWORD is set.
- 150 Indian wholesale customers with GSTINs, credit terms, and risk tiers
- 800 Invoices across the last 18 months
- Payments and partial payment allocations
- Follow-up records for overdue accounts
- Exports a sample CSV: backend/scripts/synthetic_invoices.csv
"""

import csv
import os
import secrets
import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import uuid

from sqlalchemy.orm import Session
from faker import Faker

from app.core.database import SessionLocal, engine
from app.core.security import hash_password
from app.models.base import Base
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.customer import Customer, RiskTier
from app.models.invoice import Invoice, InvoiceItem, InvoiceStatus
from app.models.payment import Payment, PaymentAllocation, PaymentMode
from app.models.follow_up import FollowUp, FollowUpStatus, FollowUpChannel

# Fixed seed for reproducibility
random.seed(42)
fake = Faker("en_IN")
fake.seed_instance(42)

INDIAN_CITIES = [
    "Mumbai", "Delhi", "Bengaluru", "Ahmedabad", "Pune",
    "Surat", "Jaipur", "Indore", "Kanpur", "Nagpur",
    "Lucknow", "Hyderabad", "Chennai", "Kolkata", "Vadodara"
]

BUSINESS_SUFFIXES = [
    "Enterprises", "Distributors", "Agencies", "Traders", "Logistics",
    "Wholesale Corp", "Pharma Dist", "FMCG Supplies", "Hardware Mart", "Textiles"
]

INDIAN_NAMES = [
    "Patel", "Sharma", "Gupta", "Verma", "Mehta", "Shah", "Reddy", "Jain",
    "Agarwal", "Singh", "Choudhary", "Iyer", "Nair", "Bansal", "Kulkarni",
    "Deshmukh", "Poddar", "Trivedi", "Mishra", "Joshi", "Saxena", "Bhatia"
]


def generate_gstin(state_code: str = "27") -> str:
    pan = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=5))
    pan += "".join(random.choices("0123456789", k=4))
    pan += random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    return f"{state_code}{pan}1Z{random.choice('0123456789ABCDEF')}"


def seed_data():
    Base.metadata.create_all(bind=engine)  # fresh databases (e.g. a new Neon branch) have no tables yet
    db: Session = SessionLocal()
    try:
        print("🌱 Seeding Udhaar Ledger synthetic dataset...")

        # 1. Organization
        org = db.query(Organization).filter(Organization.slug == "sharma-dist").first()
        if not org:
            org = Organization(
                name="Sharma Distributors Pvt Ltd",
                slug="sharma-dist",
                is_active=True,
            )
            db.add(org)
            db.flush()
            print(f"✓ Created Organization: {org.name} ({org.id})")
        else:
            print(f"ℹ Using existing Organization: {org.name}")

        # 2. Admin User
        admin_email = "admin@sharma-dist.com"
        admin = db.query(User).filter(User.email == admin_email).first()
        admin_pwd = os.environ.get("INITIAL_ADMIN_PASSWORD") or secrets.token_urlsafe(32)
        if not admin:
            admin = User(
                org_id=org.id,
                email=admin_email,
                hashed_password=hash_password(admin_pwd),
                full_name="Rajesh Sharma",
                role=UserRole.admin.value,
                is_active=True,
            )
            db.add(admin)
            db.flush()
            print(f"✓ Created Admin User: {admin_email} (local password is random; sign in with Clerk)")
        else:
            print(f"ℹ Admin user exists: {admin_email}")

        # Check existing customers count
        cust_count = db.query(Customer).filter(Customer.org_id == org.id).count()
        if cust_count >= 100:
            print(f"ℹ Found {cust_count} existing customers. Skipping customer generation.")
            customers = db.query(Customer).filter(Customer.org_id == org.id).all()
        else:
            print("Creating 150 realistic Indian B2B customers...")
            customers = []
            for i in range(150):
                family = random.choice(INDIAN_NAMES)
                suffix = random.choice(BUSINESS_SUFFIXES)
                city = random.choice(INDIAN_CITIES)
                name = f"{family} {suffix}"
                # 20% high risk, 30% medium risk, 50% low risk
                risk_roll = random.random()
                if risk_roll < 0.20:
                    risk_tier = RiskTier.high.value
                    terms = random.choice([45, 60])
                    credit = Decimal(random.choice([200000, 400000, 600000]))
                elif risk_roll < 0.50:
                    risk_tier = RiskTier.medium.value
                    terms = random.choice([30, 45])
                    credit = Decimal(random.choice([500000, 1000000, 1500000]))
                else:
                    risk_tier = RiskTier.low.value
                    terms = random.choice([15, 30])
                    credit = Decimal(random.choice([1000000, 2000000, 3000000]))

                c = Customer(
                    org_id=org.id,
                    name=name,
                    email=f"accounts@{name.lower().replace(' ', '')}.in",
                    phone=f"+91 9{random.randint(100000000, 999999999)}",
                    gst_number=generate_gstin(random.choice(["27", "07", "29", "24", "09"])),
                    address=f"Plot {random.randint(10, 400)}, GIDC Industrial Area, {city}",
                    credit_limit=credit,
                    payment_terms_days=terms,
                    risk_tier=risk_tier,
                    is_active=True,
                )
                db.add(c)
                customers.append(c)
            db.flush()
            print(f"✓ Created {len(customers)} customers.")

        # 3. Generate Invoices & Payments
        inv_count = db.query(Invoice).filter(Invoice.org_id == org.id).count()
        if inv_count >= 400:
            print(f"ℹ Found {inv_count} existing invoices. Skipping generation.")
        else:
            print("Creating 800 realistic invoices spanning 18 months...")
            today = date.today()
            start_date = today - timedelta(days=540)  # ~18 months

            csv_rows = []
            created_invoices = []

            for i in range(800):
                customer = random.choice(customers)
                # Random issue date between start_date and today
                days_offset = random.randint(0, 520)
                issue_date = start_date + timedelta(days=days_offset)
                due_date = issue_date + timedelta(days=customer.payment_terms_days)

                inv_num = f"INV-2024-{i+1:05d}"
                amount = Decimal(str(random.randint(15, 1200) * 1000))  # 15,000 to 1,200,000

                inv = Invoice(
                    org_id=org.id,
                    customer_id=customer.id,
                    invoice_number=inv_num,
                    issue_date=issue_date,
                    due_date=due_date,
                    total_amount=amount,
                    status=InvoiceStatus.sent.value,
                    notes=f"Goods consignment delivery #{random.randint(100, 999)}",
                )
                db.add(inv)
                db.flush()
                created_invoices.append(inv)

                # Line item
                item = InvoiceItem(
                    invoice_id=inv.id,
                    description=f"Wholesale Goods Consignment - Batch #{random.randint(1000, 9999)}",
                    quantity=Decimal("1.000"),
                    unit_price=amount,
                    line_total=amount,
                )
                db.add(item)

                # Payment simulation behavior depending on customer risk and age
                is_old = (due_date < today - timedelta(days=45))
                is_recent = (due_date >= today - timedelta(days=15))

                pay_amt = Decimal("0")
                pay_date = None
                pay_ref = None

                # Determine outcome
                # High risk customers pay late or default
                if customer.risk_tier == RiskTier.high.value:
                    outcome_roll = random.random()
                    if outcome_roll < 0.35 and is_old:  # Paid late
                        delay_days = random.randint(15, 75)
                        pay_date = due_date + timedelta(days=delay_days)
                        if pay_date <= today:
                            pay_amt = amount
                    elif outcome_roll < 0.65:  # Partial payment
                        pay_pct = Decimal(str(random.choice([0.25, 0.40, 0.50, 0.60])))
                        pay_amt = (amount * pay_pct).quantize(Decimal("1.00"))
                        pay_date = due_date + timedelta(days=random.randint(5, 30))
                        if pay_date > today:
                            pay_date = today
                    else:  # Unpaid / default
                        pay_amt = Decimal("0")
                elif customer.risk_tier == RiskTier.medium.value:
                    outcome_roll = random.random()
                    if outcome_roll < 0.60 and not is_recent:  # Paid
                        delay = random.randint(-5, 25)
                        pay_date = due_date + timedelta(days=delay)
                        if pay_date <= today:
                            pay_amt = amount
                    elif outcome_roll < 0.80:  # Partial
                        pay_amt = (amount * Decimal("0.50")).quantize(Decimal("1.00"))
                        pay_date = due_date
                    else:
                        pay_amt = Decimal("0")
                else:  # Low risk
                    outcome_roll = random.random()
                    if outcome_roll < 0.85 and not is_recent:
                        delay = random.randint(-10, 7)
                        pay_date = due_date + timedelta(days=delay)
                        if pay_date <= today:
                            pay_amt = amount
                    elif outcome_roll < 0.95:
                        pay_amt = (amount * Decimal("0.75")).quantize(Decimal("1.00"))
                        pay_date = due_date
                    else:
                        pay_amt = Decimal("0")

                # If pay_amt > 0 and pay_date <= today: create payment record
                if pay_amt > 0 and pay_date and pay_date <= today:
                    pay_ref = f"UTR-{random.randint(100000000000, 999999999999)}"
                    payment = Payment(
                        org_id=org.id,
                        customer_id=customer.id,
                        received_date=pay_date,
                        amount=pay_amt,
                        reference_no=pay_ref,
                        payment_mode=random.choice([PaymentMode.neft.value, PaymentMode.rtgs.value, PaymentMode.upi.value]),
                    )
                    db.add(payment)
                    db.flush()

                    allocation = PaymentAllocation(
                        payment_id=payment.id,
                        invoice_id=inv.id,
                        allocated_amount=pay_amt,
                        allocated_at=datetime.combine(pay_date, datetime.min.time(), tzinfo=timezone.utc),
                    )
                    db.add(allocation)

                    if pay_amt >= amount:
                        inv.status = InvoiceStatus.paid.value
                    else:
                        inv.status = InvoiceStatus.partial.value
                else:
                    if due_date < today:
                        inv.status = InvoiceStatus.overdue.value
                    else:
                        inv.status = InvoiceStatus.sent.value

                # Create follow-up for overdue or partial invoices
                if inv.status in (InvoiceStatus.overdue.value, InvoiceStatus.partial.value):
                    fu_status = random.choice([
                        FollowUpStatus.pending.value,
                        FollowUpStatus.contacted.value,
                        FollowUpStatus.promised.value,
                    ])
                    fu = FollowUp(
                        org_id=org.id,
                        invoice_id=inv.id,
                        customer_id=customer.id,
                        status=fu_status,
                        channel=random.choice([
                            FollowUpChannel.whatsapp.value,
                            FollowUpChannel.call.value,
                            FollowUpChannel.email.value,
                        ]),
                        notes=f"Automated reminder generated. Customer noted follow-up on {today.isoformat()}.",
                        scheduled_at=datetime.utcnow() + timedelta(days=random.randint(1, 5)),
                        created_by=admin.id,
                    )
                    db.add(fu)

                # Save row for CSV export
                csv_rows.append({
                    "invoice_number": inv_num,
                    "customer_name": customer.name,
                    "customer_email": customer.email,
                    "issue_date": issue_date.isoformat(),
                    "due_date": due_date.isoformat(),
                    "total_amount": str(amount),
                    "payment_amount": str(pay_amt) if pay_amt > 0 else "",
                    "payment_date": pay_date.isoformat() if pay_amt > 0 and pay_date else "",
                    "payment_reference": pay_ref or "",
                    "payment_mode": "neft",
                })

            db.commit()
            print(f"✓ Generated {len(created_invoices)} invoices with payment allocations and follow-ups.")

            # Write CSV export
            csv_path = Path(__file__).parent / "synthetic_invoices.csv"
            with open(csv_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "invoice_number", "customer_name", "customer_email",
                    "issue_date", "due_date", "total_amount",
                    "payment_amount", "payment_date", "payment_reference", "payment_mode"
                ])
                writer.writeheader()
                writer.writerows(csv_rows)
            print(f"✓ Exported sample import CSV to: {csv_path}")

        # Summary statistics
        total_invs = db.query(Invoice).filter(Invoice.org_id == org.id).count()
        total_pays = db.query(Payment).filter(Payment.org_id == org.id).count()
        total_allocs = db.query(PaymentAllocation).count()
        paid_invs = db.query(Invoice).filter(Invoice.org_id == org.id, Invoice.status == "paid").count()
        overdue_invs = db.query(Invoice).filter(Invoice.org_id == org.id, Invoice.status == "overdue").count()
        partial_invs = db.query(Invoice).filter(Invoice.org_id == org.id, Invoice.status == "partial").count()

        print("\n" + "="*50)
        print("📊 Udhaar Ledger Synthetic Data Summary:")
        print(f"  Organization: {org.name} (Org ID: {org.id})")
        print(f"  Customers:    {len(customers) if 'customers' in locals() else cust_count}")
        print(f"  Invoices:     {total_invs} total ({paid_invs} paid, {overdue_invs} overdue, {partial_invs} partial)")
        print(f"  Payments:     {total_pays} payments ({total_allocs} allocations)")
        print("="*50 + "\n")

    finally:
        db.close()


if __name__ == "__main__":
    seed_data()
