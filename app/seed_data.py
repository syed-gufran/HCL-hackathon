from __future__ import annotations

import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

from app.database import SessionLocal
from app.models import Category, Resolution, Ticket, User


FAKE_NAMES = [
    "Ali Khan",
    "Sara Ahmed",
    "John Smith",
    "Maya Patel",
    "Noah Wilson",
    "Ava Brown",
    "Liam Davis",
    "Emma Johnson",
]


TITLE_TEMPLATES = [
    "{category} - urgent issue",
    "{category} not working",
    "Need help with {category}",
    "{category} failure on production",
    "{category} issue after latest update",
]


DESC_TEMPLATES = [
    "User reports repeated failure in {category}. Steps to reproduce are available.",
    "System shows intermittent errors for {category} in production.",
    "{category} issue started after configuration change and affects daily work.",
    "Customer cannot complete workflow due to {category}.",
    "{category} behavior is unstable across environments.",
]


def ensure_admin(db) -> User:
    admin = db.query(User).filter(User.email == "admin@example.com").first()
    if admin:
        return admin

    admin = User(
        name="System Admin",
        email="admin@example.com",
        password_hash="dev-only",
        role="admin",
        department="IT",
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def ensure_fake_users(db, count: int = 6) -> list[User]:
    users: list[User] = []
    for idx in range(count):
        email = f"user{idx+1}@example.com"
        row = db.query(User).filter(User.email == email).first()
        if row is None:
            row = User(
                name=FAKE_NAMES[idx % len(FAKE_NAMES)],
                email=email,
                password_hash="dev-only",
                role="user",
                department=random.choice(["IT", "Sales", "HR", "Finance", "Operations"]),
            )
            db.add(row)
            db.flush()
        users.append(row)
    db.commit()
    return users


def ensure_categories(db, csv_rows: list[dict]) -> dict[str, Category]:
    category_names = sorted(
        {
            (row.get("issue_category") or "General").strip() or "General"
            for row in csv_rows
        }
    )
    existing = {c.name: c for c in db.query(Category).all()}

    for name in category_names:
        if name in existing:
            continue
        category = Category(
            name=name,
            description=f"Auto-created category for {name}",
        )
        db.add(category)
        db.flush()
        existing[name] = category

    db.commit()
    return existing


def create_fake_tickets(db, users: list[User], categories: dict[str, Category], per_category: int) -> int:
    created = 0
    now = datetime.utcnow()
    for category_name, category in categories.items():
        existing_count = db.query(Ticket).filter(Ticket.category_id == category.category_id).count()
        needed = max(0, per_category - existing_count)
        for _ in range(needed):
            created_date = now - timedelta(days=random.randint(1, 45))
            ticket = Ticket(
                user_id=random.choice(users).user_id,
                category_id=category.category_id,
                title=random.choice(TITLE_TEMPLATES).format(category=category_name),
                description=random.choice(DESC_TEMPLATES).format(category=category_name),
                priority=random.choice(["low", "med", "high"]),
                status=random.choice(["open", "in_progress", "open", "open"]),
                created_date=created_date,
                updated_date=created_date,
            )
            db.add(ticket)
            created += 1
    db.commit()
    return created


def parse_csv_date(raw: str) -> datetime:
    raw = (raw or "").strip()
    if not raw:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return datetime.utcnow()


def import_historical_resolutions(db, csv_rows: list[dict], categories: dict[str, Category], admin: User) -> int:
    inserted = 0
    tickets_by_category: dict[int, list[Ticket]] = {}
    for category in categories.values():
        tickets = db.query(Ticket).filter(Ticket.category_id == category.category_id).all()
        tickets_by_category[category.category_id] = tickets

    for row in csv_rows:
        category_name = (row.get("issue_category") or "General").strip() or "General"
        category = categories.get(category_name)
        if category is None:
            continue

        resolution_text = (row.get("resolution_text") or "").strip()
        if not resolution_text:
            continue

        resolved_date = parse_csv_date(row.get("resolved_date", ""))
        helpful_count = int((row.get("helpful_count") or "0").strip() or 0)
        is_verified = (row.get("is_verified") or "true").strip().lower() in {"true", "1", "yes"}

        category_tickets = tickets_by_category.get(category.category_id, [])
        if not category_tickets:
            created_date = parse_csv_date(row.get("created_date", ""))
            ticket = Ticket(
                user_id=admin.user_id,
                category_id=category.category_id,
                title=f"Imported {category_name}",
                description=f"Historical issue from CSV for {category_name}",
                priority="med",
                status="open",
                created_date=created_date,
                updated_date=created_date,
            )
            db.add(ticket)
            db.flush()
            category_tickets = [ticket]
            tickets_by_category[category.category_id] = category_tickets

        target_ticket = random.choice(category_tickets)
        existing_resolution = (
            db.query(Resolution)
            .filter(
                Resolution.ticket_id == target_ticket.ticket_id,
                Resolution.resolution_text == resolution_text,
            )
            .first()
        )
        if existing_resolution:
            continue

        resolution = Resolution(
            ticket_id=target_ticket.ticket_id,
            added_by=admin.user_id,
            resolution_text=resolution_text,
            resolved_date=resolved_date,
            helpful_count=helpful_count,
            is_verified=is_verified,
        )
        db.add(resolution)
        inserted += 1

        if is_verified:
            target_ticket.status = "resolved"
            target_ticket.resolved_date = resolved_date
            target_ticket.updated_date = datetime.utcnow()

    db.commit()
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed tickets.db with fake data and historical resolutions.")
    parser.add_argument("--csv", default="Historical_ticket_data.csv", help="Path to historical CSV file")
    parser.add_argument("--tickets-per-category", type=int, default=4, help="Minimum fake tickets per category")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        csv_rows = list(csv.DictReader(f))

    random.seed(42)
    db = SessionLocal()
    try:
        admin = ensure_admin(db)
        users = ensure_fake_users(db, count=6)
        categories = ensure_categories(db, csv_rows)
        created_tickets = create_fake_tickets(db, users, categories, args.tickets_per_category)
        inserted_resolutions = import_historical_resolutions(db, csv_rows, categories, admin)

        total_users = db.query(User).count()
        total_categories = db.query(Category).count()
        total_tickets = db.query(Ticket).count()
        total_resolutions = db.query(Resolution).count()

        print(f"created_tickets={created_tickets}")
        print(f"inserted_resolutions={inserted_resolutions}")
        print(f"total_users={total_users}")
        print(f"total_categories={total_categories}")
        print(f"total_tickets={total_tickets}")
        print(f"total_resolutions={total_resolutions}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
