from __future__ import annotations

import hashlib
import os
import re
import secrets
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import random

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import String, cast
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.models import Base, Category, Resolution, Ticket, TicketStatusLog, User


Base.metadata.create_all(bind=engine)

default_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]
if not allowed_origins:
    allowed_origins = default_origins

app = FastAPI(title="Tickets API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@dataclass
class TicketVectorRow:
    ticket_id: int
    title: str
    category_name: str
    resolution_id: int
    resolution_text: str


def preprocess(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    tokens = [word for word in text.split() if word not in ENGLISH_STOP_WORDS]
    return " ".join(tokens)


class NLPRecommendationEngine:
    def __init__(self, max_features: int = 5000) -> None:
        self.vectorizer = TfidfVectorizer(max_features=max_features)
        self.rows: list[TicketVectorRow] = []
        self.tfidf_matrix = None
        self.is_ready = False

    def rebuild_cache(self, db: Session) -> int:
        query_rows = (
            db.query(Ticket, Resolution, Category)
            .join(Resolution, Resolution.ticket_id == Ticket.ticket_id)
            .join(Category, Category.category_id == Ticket.category_id)
            .filter(Resolution.is_verified.is_(True))
            .all()
        )

        corpus: list[str] = []
        self.rows = []

        for ticket, resolution, category in query_rows:
            combined = f"{ticket.title} {ticket.description} {resolution.resolution_text}"
            processed = preprocess(combined)
            if not processed:
                continue
            corpus.append(processed)
            self.rows.append(
                TicketVectorRow(
                    ticket_id=ticket.ticket_id,
                    title=ticket.title,
                    category_name=category.name if category else "General",
                    resolution_id=resolution.resolution_id,
                    resolution_text=resolution.resolution_text,
                )
            )

        if not corpus:
            self.tfidf_matrix = None
            self.is_ready = False
            return 0

        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)
        self.is_ready = True
        return len(self.rows)

    def get_recommendations(self, text: str, top_k: int = 3, min_score: float = 0.15) -> list[dict]:
        if not self.is_ready or self.tfidf_matrix is None:
            return []

        processed = preprocess(text)
        if not processed:
            return []

        query_vec = self.vectorizer.transform([processed])
        scores = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        top_indices = scores.argsort()[::-1][:top_k]

        suggestions: list[dict] = []
        rank = 1
        for idx in top_indices:
            score = float(scores[idx])
            if score < min_score:
                continue
            row = self.rows[idx]
            suggestions.append(
                {
                    "rank": rank,
                    "score": round(score, 2),
                    "ticket_id": row.ticket_id,
                    "title": row.title,
                    "category": row.category_name,
                    "resolution_id": row.resolution_id,
                    "resolution_text": row.resolution_text,
                }
            )
            rank += 1

        return suggestions


recommender = NLPRecommendationEngine(max_features=5000)
auth_tokens: dict[str, int] = {}
ADMIN_EMAIL = "admin@company.com"
ADMIN_PASSWORD = "admin123"
SECOND_ADMIN_EMAIL = "tazeema07@gmail.com"
SECOND_ADMIN_PASSWORD = "Gufran"
SECOND_ADMIN_NAME = "Gufran"


class RecommendRequest(BaseModel):
    ticket_text: str = Field(min_length=1)
    top_k: int = 3
    min_score: float = 0.15


class FeedbackRequest(BaseModel):
    resolution_id: int
    helpful: bool


class ResolutionCreateRequest(BaseModel):
    ticket_id: int
    resolution_text: str = Field(min_length=1)
    added_by: int
    is_verified: bool = False
    resolved_date: datetime | None = None


class LoginRequest(BaseModel):
    email: str
    password: str
    expected_role: str | None = None


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=150)
    password: str = Field(min_length=6, max_length=255)
    department: str = Field(default="General", min_length=2, max_length=100)


class TicketUpdateRequest(BaseModel):
    status: str
    resolution: str | None = None


class UserTicketCreateRequest(BaseModel):
    issue: str = Field(min_length=3, max_length=200)
    category: str = Field(min_length=3, max_length=50)
    description: str = Field(min_length=8)
    priority: str = "med"


class UserTicketResolveRequest(BaseModel):
    resolution: str = Field(min_length=3)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_latest_resolution_map(db: Session, ticket_ids: list[int]) -> dict[int, Resolution]:
    if not ticket_ids:
        return {}
    rows = (
        db.query(Resolution)
        .filter(Resolution.ticket_id.in_(ticket_ids))
        .order_by(Resolution.ticket_id.asc(), Resolution.resolved_date.desc(), Resolution.resolution_id.desc())
        .all()
    )
    latest: dict[int, Resolution] = {}
    for row in rows:
        if row.ticket_id not in latest:
            latest[row.ticket_id] = row
    return latest


def get_resolved_by_map(
    db: Session,
    ticket_ids: list[int],
    latest_resolution_map: dict[int, Resolution],
) -> dict[int, dict]:
    if not ticket_ids:
        return {}

    resolved_logs = (
        db.query(TicketStatusLog)
        .filter(
            TicketStatusLog.ticket_id.in_(ticket_ids),
            TicketStatusLog.new_status == "Resolved",
        )
        .order_by(
            TicketStatusLog.ticket_id.asc(),
            TicketStatusLog.changed_at.desc(),
            TicketStatusLog.log_id.desc(),
        )
        .all()
    )
    latest_log_by_ticket: dict[int, TicketStatusLog] = {}
    for row in resolved_logs:
        if row.ticket_id not in latest_log_by_ticket:
            latest_log_by_ticket[row.ticket_id] = row

    user_ids: set[int] = set()
    for row in latest_resolution_map.values():
        if row.added_by:
            user_ids.add(row.added_by)
    for row in latest_log_by_ticket.values():
        if row.changed_by:
            user_ids.add(row.changed_by)

    users_by_id: dict[int, User] = {}
    if user_ids:
        users = db.query(User).filter(User.user_id.in_(list(user_ids))).all()
        users_by_id = {u.user_id: u for u in users}

    output: dict[int, dict] = {}
    for ticket_id in ticket_ids:
        actor_id = None
        latest_resolution = latest_resolution_map.get(ticket_id)
        if latest_resolution and latest_resolution.added_by:
            actor_id = latest_resolution.added_by
        else:
            latest_log = latest_log_by_ticket.get(ticket_id)
            if latest_log and latest_log.changed_by:
                actor_id = latest_log.changed_by

        actor = users_by_id.get(actor_id) if actor_id else None
        output[ticket_id] = {
            "resolved_by_user_id": actor.user_id if actor else None,
            "resolved_by_name": actor.name if actor else None,
            "resolved_by_email": actor.email if actor else None,
        }
    return output


def get_admin(db: Session, x_user_id: int | None) -> User:
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="x-user-id header required")
    user = db.query(User).filter(User.user_id == x_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def get_current_user(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1].strip()
    user_id = auth_tokens.get(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_admin_user(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def seed_demo_data(db: Session, per_category: int = 30) -> dict:
    random.seed(42)

    db.query(Resolution).delete()
    db.query(TicketStatusLog).delete()
    db.query(Ticket).delete()
    db.query(Category).delete()
    db.query(User).delete()
    db.commit()

    admin = User(
        name="System Admin",
        email=ADMIN_EMAIL,
        password_hash=hash_password(ADMIN_PASSWORD),
        role="admin",
        department="IT",
    )
    db.add(admin)
    db.flush()
    employee = User(
        name="Employee User",
        email="employee@company.com",
        password_hash=hash_password("employee123"),
        role="user",
        department="Operations",
    )
    db.add(employee)
    db.flush()

    category_names = ["Software", "Access", "Hardware", "Network"]
    categories: dict[str, Category] = {}
    for name in category_names:
        category = Category(name=name, description=f"{name} related issues")
        db.add(category)
        db.flush()
        categories[name] = category

    issue_templates = {
        "Software": [
            "Application crashes on launch",
            "Outlook freezes after update",
            "ERP client not responding",
            "Unable to install approved software",
            "Blue screen after OS patch",
            "Printer software queue stalled",
            "Browser profile keeps resetting",
        ],
        "Access": [
            "SSO login denied",
            "SAP role missing for approvals",
            "Shared folder permission error",
            "MFA device not recognized",
            "Service account token expired",
            "New joiner cannot access HR portal",
            "Role mapping mismatch in IAM",
        ],
        "Hardware": [
            "Laptop overheating rapidly",
            "Docking station not detected",
            "Keyboard keys unresponsive",
            "Monitor stays black after boot",
            "Battery drains in under one hour",
            "USB-C hub disconnecting randomly",
            "Webcam not detected in meetings",
        ],
        "Network": [
            "VPN disconnects every 10 minutes",
            "Wi-Fi authentication loop",
            "Cannot reach intranet portal",
            "Packet loss on video calls",
            "DNS lookup latency is high",
            "Intermittent proxy timeout",
            "Office subnet cannot reach printer VLAN",
        ],
    }
    resolution_templates = {
        "Software": [
            "Repair the application install and clear local cache.",
            "Disable conflicting add-ins and patch to latest build.",
            "Reinstall dependency runtime and reboot system.",
        ],
        "Access": [
            "Re-sync identity group and force token refresh.",
            "Grant missing role in IAM and confirm policy propagation.",
            "Reset MFA enrollment and verify sign-in policy.",
        ],
        "Hardware": [
            "Replace faulty cable and update device firmware.",
            "Run hardware diagnostics and swap defective unit.",
            "Reset BIOS peripherals and re-seat the connector.",
        ],
        "Network": [
            "Restart VPN client service and rotate certificate.",
            "Apply DNS flush and renew DHCP lease.",
            "Move user to stable VLAN and update firewall rule.",
        ],
    }

    statuses = ["Open", "In Progress", "Resolved"]
    priorities = ["low", "med", "high"]
    now = datetime.utcnow()

    created_tickets = 0
    created_resolutions = 0
    for category_name, category in categories.items():
        for i in range(per_category):
            created_date = now.replace(microsecond=0)
            created_date = created_date.replace(day=max(1, (created_date.day - (i % 20))))
            status = random.choices(statuses, weights=[5, 5, 6], k=1)[0]
            title = random.choice(issue_templates[category_name])
            description = (
                f"{title}. User reported issue in {category_name.lower()} workflow. "
                f"Impact: {'team blocked' if i % 4 == 0 else 'single user degraded'}. "
                f"Environment: {'remote' if i % 3 == 0 else 'office'}. Case #{i+1}."
            )
            ticket = Ticket(
                user_id=random.choice([admin.user_id, employee.user_id]),
                category_id=category.category_id,
                title=title,
                description=description,
                priority=random.choice(priorities),
                status=status,
                created_date=created_date,
                updated_date=created_date,
                resolved_date=created_date if status == "Resolved" else None,
            )
            db.add(ticket)
            db.flush()
            created_tickets += 1

            if status in {"In Progress", "Resolved"}:
                db.add(
                    TicketStatusLog(
                        ticket_id=ticket.ticket_id,
                        changed_by=admin.user_id,
                        old_status="Open",
                        new_status=status,
                        changed_at=created_date,
                        note=f"Moved to {status}",
                    )
                )

            if status == "Resolved":
                resolution = Resolution(
                    ticket_id=ticket.ticket_id,
                    added_by=admin.user_id,
                    resolution_text=random.choice(resolution_templates[category_name]),
                    resolved_date=created_date,
                    helpful_count=random.randint(0, 8),
                    is_verified=True,
                )
                db.add(resolution)
                created_resolutions += 1

    db.commit()
    indexed = recommender.rebuild_cache(db)
    return {
        "users": db.query(User).count(),
        "categories": db.query(Category).count(),
        "tickets": created_tickets,
        "resolutions": created_resolutions,
        "indexed_rows": indexed,
        "admin_email": ADMIN_EMAIL,
        "admin_password": ADMIN_PASSWORD,
    }


@app.on_event("startup")
def startup_event() -> None:
    with SessionLocal() as db:
        admin = db.query(User).filter(User.email == ADMIN_EMAIL).first()
        if not admin:
            admin = User(
                name="System Admin",
                email=ADMIN_EMAIL,
                password_hash=hash_password(ADMIN_PASSWORD),
                role="admin",
                department="IT",
            )
            db.add(admin)
        else:
            admin.password_hash = hash_password(ADMIN_PASSWORD)
            admin.role = "admin"
            admin.department = "IT"

        second_admin = db.query(User).filter(User.email == SECOND_ADMIN_EMAIL).first()
        if not second_admin:
            second_admin = User(
                name=SECOND_ADMIN_NAME,
                email=SECOND_ADMIN_EMAIL,
                password_hash=hash_password(SECOND_ADMIN_PASSWORD),
                role="admin",
                department="IT",
            )
            db.add(second_admin)
        else:
            second_admin.name = SECOND_ADMIN_NAME
            second_admin.password_hash = hash_password(SECOND_ADMIN_PASSWORD)
            second_admin.role = "admin"
            second_admin.department = "IT"
        db.commit()
        recommender.rebuild_cache(db)


@app.get("/")
def root() -> dict:
    return {"message": "Server running"}


@app.post("/api/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or user.password_hash != hash_password(payload.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if payload.expected_role and user.role != payload.expected_role:
        raise HTTPException(status_code=403, detail=f"Use {user.role} portal for this account")

    token = secrets.token_urlsafe(24)
    auth_tokens[token] = user.user_id
    return {
        "token": token,
        "user": {"user_id": user.user_id, "name": user.name, "email": user.email, "role": user.role},
    }


@app.post("/api/auth/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Email already exists")

    if email in {ADMIN_EMAIL.lower(), SECOND_ADMIN_EMAIL.lower()}:
        raise HTTPException(status_code=403, detail="This email is reserved")

    user = User(
        name=payload.name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        role="user",
        department=payload.department.strip() or "General",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = secrets.token_urlsafe(24)
    auth_tokens[token] = user.user_id
    return {
        "token": token,
        "user": {"user_id": user.user_id, "name": user.name, "email": user.email, "role": user.role},
    }


@app.get("/api/auth/me")
def auth_me(user: User = Depends(get_current_user)):
    return {"user_id": user.user_id, "name": user.name, "email": user.email, "role": user.role}


@app.post("/api/auth/logout")
def auth_logout(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    auth_tokens.pop(token, None)
    return {"ok": True}


@app.post("/api/admin/seed-demo")
def api_seed_demo(
    per_category: int = 30,
    _: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
):
    per_category = max(5, min(per_category, 200))
    return seed_demo_data(db, per_category=per_category)


@app.get("/api/analytics/overview")
def analytics_overview(
    _: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
):
    tickets = db.query(Ticket).all()
    resolved = [t for t in tickets if t.status == "Resolved" and t.resolved_date]
    pending_count = sum(1 for t in tickets if t.status != "Resolved")
    resolved_count = len(resolved)
    avg_resolution_hours = 0.0
    if resolved:
        total_hours = 0.0
        for t in resolved:
            delta = t.resolved_date - t.created_date
            total_hours += max(0.0, delta.total_seconds() / 3600)
        avg_resolution_hours = round(total_hours / len(resolved), 2)

    category_rows = (
        db.query(Category.name, Ticket.ticket_id)
        .join(Ticket, Ticket.category_id == Category.category_id)
        .all()
    )
    category_counter = Counter([name for name, _ in category_rows])
    category_distribution = [{"name": k, "value": v} for k, v in category_counter.items()]

    status_counter = Counter([t.status for t in tickets])
    priority_counter = Counter([t.priority for t in tickets])

    category_resolution_rates = []
    categories = db.query(Category).all()
    for c in categories:
        cat_tickets = [t for t in tickets if t.category_id == c.category_id]
        if not cat_tickets:
            category_resolution_rates.append({"name": c.name, "resolved": 0, "open": 0, "rate": 0})
            continue
        resolved_cat = sum(1 for t in cat_tickets if t.status == "Resolved")
        open_cat = len(cat_tickets) - resolved_cat
        rate = round((resolved_cat / len(cat_tickets)) * 100, 1)
        category_resolution_rates.append(
            {"name": c.name, "resolved": resolved_cat, "open": open_cat, "rate": rate}
        )

    daily_counter = Counter([t.created_date.strftime("%Y-%m-%d") for t in tickets if t.created_date])
    daily_volume = [{"date": k, "count": v} for k, v in sorted(daily_counter.items())][-14:]

    top_helpful = (
        db.query(Resolution)
        .filter(Resolution.is_verified.is_(True))
        .order_by(Resolution.helpful_count.desc())
        .limit(5)
        .all()
    )
    top_resolutions = [
        {
            "resolution_id": r.resolution_id,
            "ticket_id": r.ticket_id,
            "helpful_count": r.helpful_count,
            "resolution_text": r.resolution_text,
        }
        for r in top_helpful
    ]

    latest_tickets = (
        db.query(Ticket, Category)
        .join(Category, Category.category_id == Ticket.category_id)
        .order_by(Ticket.created_date.desc())
        .limit(8)
        .all()
    )
    recent_activity = [
        {
            "ticket_id": t.ticket_id,
            "title": t.title,
            "category": c.name,
            "status": t.status,
            "priority": t.priority,
            "created_date": t.created_date,
        }
        for t, c in latest_tickets
    ]

    return {
        "total_tickets": len(tickets),
        "pending_tickets": pending_count,
        "resolved_tickets": resolved_count,
        "avg_resolution_hours": avg_resolution_hours,
        "category_distribution": category_distribution,
        "status_distribution": dict(status_counter),
        "priority_distribution": dict(priority_counter),
        "category_resolution_rates": category_resolution_rates,
        "daily_volume": daily_volume,
        "top_resolutions": top_resolutions,
        "recent_activity": recent_activity,
    }


@app.get("/api/tickets")
def api_tickets(
    status: str | None = None,
    category: str | None = None,
    priority: str | None = None,
    q: str | None = None,
    _: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
):
    base = (
        db.query(Ticket, Category)
        .join(Category, Category.category_id == Ticket.category_id)
    )
    if status:
        base = base.filter(Ticket.status == status)
    if category:
        base = base.filter(Category.name == category)
    if priority:
        base = base.filter(Ticket.priority == priority)
    if q:
        normalized = q.strip()
        digits = normalized.lower().replace("t-", "")
        like = f"%{normalized}%"
        id_like = f"%{digits}%"
        base = base.filter(
            (Ticket.title.ilike(like))
            | (Ticket.description.ilike(like))
            | (cast(Ticket.ticket_id, String).ilike(id_like))
        )

    rows = base.order_by(Ticket.created_date.desc()).all()
    ticket_ids = [t.ticket_id for t, _ in rows]
    latest_resolution_map = get_latest_resolution_map(db, ticket_ids)
    resolved_by_map = get_resolved_by_map(db, ticket_ids, latest_resolution_map)

    if not recommender.is_ready:
        recommender.rebuild_cache(db)

    category_playbook = {
        "Software": "Check logs, restart app services, and validate recent patch impact.",
        "Access": "Revalidate IAM role mapping, refresh auth tokens, and verify group sync.",
        "Hardware": "Run hardware diagnostics and validate power/cable/peripheral chain.",
        "Network": "Validate VPN/DNS path, then test route/firewall and local adapter health.",
    }
    by_ticket: dict[int, dict] = {}
    for t, c in rows:
        latest_resolution = latest_resolution_map.get(t.ticket_id)
        resolved_actor = resolved_by_map.get(
            t.ticket_id,
            {"resolved_by_user_id": None, "resolved_by_name": None, "resolved_by_email": None},
        )
        if t.ticket_id not in by_ticket:
            suggested = ""
            if latest_resolution:
                suggested = latest_resolution.resolution_text
            else:
                nlp = recommender.get_recommendations(
                    f"{t.title} {t.description}",
                    top_k=1,
                    min_score=0.05,
                )
                if nlp:
                    suggested = nlp[0]["resolution_text"]
                else:
                    suggested = category_playbook.get(c.name, "Use NLP workbench for guided troubleshooting.")
            by_ticket[t.ticket_id] = {
                "ticket_id": t.ticket_id,
                "title": t.title,
                "description": t.description,
                "category": c.name,
                "status": t.status,
                "priority": t.priority,
                "created_date": t.created_date,
                "updated_date": t.updated_date,
                "resolved_date": t.resolved_date,
                "resolution_text": latest_resolution.resolution_text if latest_resolution else "",
                "resolution_id": latest_resolution.resolution_id if latest_resolution else None,
                "ai_suggestion": suggested,
                "resolved_by_user_id": resolved_actor["resolved_by_user_id"],
                "resolved_by_name": resolved_actor["resolved_by_name"],
                "resolved_by_email": resolved_actor["resolved_by_email"],
            }
    return list(by_ticket.values())


@app.get("/api/user/tickets")
def api_user_tickets(
    status: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Ticket, Category)
        .join(Category, Category.category_id == Ticket.category_id)
        .filter(Ticket.user_id == user.user_id)
        .order_by(Ticket.created_date.desc())
        .all()
    )
    ticket_ids = [t.ticket_id for t, _ in rows]
    latest_resolution_map = get_latest_resolution_map(db, ticket_ids)
    resolved_by_map = get_resolved_by_map(db, ticket_ids, latest_resolution_map)

    if not recommender.is_ready:
        recommender.rebuild_cache(db)

    by_ticket: dict[int, dict] = {}
    for t, c in rows:
        if status and t.status != status:
            continue
        latest_resolution = latest_resolution_map.get(t.ticket_id)
        resolved_actor = resolved_by_map.get(
            t.ticket_id,
            {"resolved_by_user_id": None, "resolved_by_name": None, "resolved_by_email": None},
        )
        if t.ticket_id not in by_ticket:
            nlp = recommender.get_recommendations(f"{t.title} {t.description}", top_k=1, min_score=0.05)
            suggested = (
                latest_resolution.resolution_text
                if latest_resolution
                else (nlp[0]["resolution_text"] if nlp else "NLP analysis available in workbench.")
            )
            by_ticket[t.ticket_id] = {
                "ticket_id": t.ticket_id,
                "title": t.title,
                "description": t.description,
                "category": c.name,
                "status": t.status,
                "priority": t.priority,
                "created_date": t.created_date,
                "resolved_date": t.resolved_date,
                "resolution_text": latest_resolution.resolution_text if latest_resolution else "",
                "ai_suggestion": suggested,
                "resolved_by_user_id": resolved_actor["resolved_by_user_id"],
                "resolved_by_name": resolved_actor["resolved_by_name"],
                "resolved_by_email": resolved_actor["resolved_by_email"],
            }
    return list(by_ticket.values())


@app.post("/api/user/tickets")
def api_create_user_ticket(
    payload: UserTicketCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    category = (
        db.query(Category)
        .filter(Category.name.ilike(payload.category.strip()))
        .first()
    )
    if not category:
        raise HTTPException(status_code=400, detail="Invalid category")

    priority = payload.priority.lower()
    if priority not in {"low", "med", "high"}:
        priority = "med"

    ticket = Ticket(
        user_id=user.user_id,
        category_id=category.category_id,
        title=payload.issue.strip(),
        description=payload.description.strip(),
        priority=priority,
        status="Open",
        created_date=datetime.utcnow(),
        updated_date=datetime.utcnow(),
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return {"ticket_id": ticket.ticket_id, "created": True}


@app.post("/api/user/tickets/{ticket_id}/resolve")
def api_user_resolve_ticket(
    ticket_id: int,
    payload: UserTicketResolveRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ticket = (
        db.query(Ticket)
        .filter(Ticket.ticket_id == ticket_id, Ticket.user_id == user.user_id)
        .first()
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    old_status = ticket.status
    ticket.status = "Resolved"
    ticket.resolved_date = datetime.utcnow()
    ticket.updated_date = datetime.utcnow()
    db.add(
        TicketStatusLog(
            ticket_id=ticket.ticket_id,
            changed_by=user.user_id,
            old_status=old_status,
            new_status="Resolved",
            changed_at=datetime.utcnow(),
            note="Resolved from user portal",
        )
    )
    db.add(
        Resolution(
            ticket_id=ticket.ticket_id,
            added_by=user.user_id,
            resolution_text=payload.resolution.strip(),
            resolved_date=datetime.utcnow(),
            helpful_count=0,
            is_verified=False,
        )
    )
    db.commit()
    recommender.rebuild_cache(db)
    return {"ticket_id": ticket.ticket_id, "status": ticket.status, "updated": True}


@app.put("/api/tickets/{ticket_id}")
def api_update_ticket(
    ticket_id: int,
    payload: TicketUpdateRequest,
    admin: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
):
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    valid_statuses = {"Open", "In Progress", "Resolved"}
    if payload.status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Invalid status")

    old_status = ticket.status
    ticket.status = payload.status
    ticket.updated_date = datetime.utcnow()
    if payload.status == "Resolved":
        ticket.resolved_date = datetime.utcnow()
    elif old_status == "Resolved":
        ticket.resolved_date = None

    if old_status != payload.status:
        db.add(
            TicketStatusLog(
                ticket_id=ticket.ticket_id,
                changed_by=admin.user_id,
                old_status=old_status,
                new_status=payload.status,
                changed_at=datetime.utcnow(),
                note="Updated from admin dashboard",
            )
        )

    resolution_text = (payload.resolution or "").strip()
    if resolution_text:
        latest_resolution = (
            db.query(Resolution)
            .filter(Resolution.ticket_id == ticket.ticket_id)
            .order_by(Resolution.resolved_date.desc())
            .first()
        )
        if not latest_resolution or latest_resolution.resolution_text != resolution_text:
            db.add(
                Resolution(
                    ticket_id=ticket.ticket_id,
                    added_by=admin.user_id,
                    resolution_text=resolution_text,
                    resolved_date=datetime.utcnow(),
                    helpful_count=0,
                    is_verified=(payload.status == "Resolved"),
                )
            )

    db.commit()
    recommender.rebuild_cache(db)
    return {"updated": True, "ticket_id": ticket.ticket_id, "status": ticket.status}


@app.get("/nlp", response_class=HTMLResponse)
def nlp_page() -> str:
    page_path = Path(__file__).resolve().parent / "pages" / "nlp.html"
    if not page_path.exists():
        raise HTTPException(status_code=500, detail=f"Missing page file: {page_path}")
    return page_path.read_text(encoding="utf-8")


@app.post("/tickets")
def create_ticket(
    user_id: int,
    title: str,
    description: str,
    category_id: int,
    priority: str,
    db: Session = Depends(get_db),
):
    ticket = Ticket(
        user_id=user_id,
        title=title,
        description=description,
        category_id=category_id,
        priority=priority,
        status="open",
        created_date=datetime.utcnow(),
        updated_date=datetime.utcnow(),
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return {"message": "Ticket created", "ticket_id": ticket.ticket_id}


@app.get("/tickets")
def get_tickets(user_id: int, role: str, db: Session = Depends(get_db)):
    if role == "admin":
        return db.query(Ticket).all()
    return db.query(Ticket).filter(Ticket.user_id == user_id).all()


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@app.put("/tickets/{ticket_id}/resolve")
def self_resolve(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    old_status = ticket.status
    ticket.status = "resolved"
    ticket.resolved_date = datetime.utcnow()
    ticket.updated_date = datetime.utcnow()
    db.add(
        TicketStatusLog(
            ticket_id=ticket.ticket_id,
            changed_by=ticket.user_id,
            old_status=old_status,
            new_status="resolved",
            note="Self-resolved",
        )
    )
    db.commit()
    return {"message": "Ticket marked as resolved"}


@app.post("/resolutions")
def add_resolution(payload: ResolutionCreateRequest, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.ticket_id == payload.ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    admin = db.query(User).filter(User.user_id == payload.added_by).first()
    if not admin or admin.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can add resolution")

    resolution = Resolution(
        ticket_id=payload.ticket_id,
        resolution_text=payload.resolution_text,
        added_by=payload.added_by,
        resolved_date=payload.resolved_date or datetime.utcnow(),
        is_verified=payload.is_verified,
    )
    ticket.status = "resolved"
    ticket.resolved_date = resolution.resolved_date
    ticket.updated_date = datetime.utcnow()

    db.add(resolution)
    db.commit()
    db.refresh(resolution)
    recommender.rebuild_cache(db)

    return {"message": "Resolution added", "resolution_id": resolution.resolution_id}


@app.get("/resolutions/{ticket_id}")
def get_resolutions(ticket_id: int, db: Session = Depends(get_db)):
    rows = db.query(Resolution).filter(Resolution.ticket_id == ticket_id).all()
    if not rows:
        return {"message": "No resolutions found"}
    return rows


@app.post("/recommend")
def recommend(payload: RecommendRequest):
    results = recommender.get_recommendations(
        payload.ticket_text,
        top_k=payload.top_k,
        min_score=payload.min_score,
    )
    return {"count": len(results), "suggestions": results}


@app.post("/recommend/feedback")
def recommendation_feedback(payload: FeedbackRequest, db: Session = Depends(get_db)):
    row = db.query(Resolution).filter(Resolution.resolution_id == payload.resolution_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Resolution not found")

    if payload.helpful:
        row.helpful_count += 1
    else:
        row.helpful_count = max(0, row.helpful_count - 1)

    db.commit()
    db.refresh(row)
    return {"resolution_id": row.resolution_id, "helpful_count": row.helpful_count}


@app.post("/recommend/rebuild")
def rebuild_recommendation(
    x_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
):
    get_admin(db, x_user_id)
    count = recommender.rebuild_cache(db)
    return {"indexed_rows": count}


@app.post("/api/nlp/recommend")
def api_nlp_recommend(payload: RecommendRequest):
    return recommend(payload)


@app.post("/api/nlp/feedback")
def api_nlp_feedback(payload: FeedbackRequest, db: Session = Depends(get_db)):
    return recommendation_feedback(payload, db)


@app.post("/api/nlp/rebuild")
def api_nlp_rebuild(
    x_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
):
    return rebuild_recommendation(x_user_id, db)


@app.get("/api/nlp/status")
def api_nlp_status(db: Session = Depends(get_db)):
    if not recommender.is_ready:
        recommender.rebuild_cache(db)
    verified_count = db.query(Resolution).filter(Resolution.is_verified.is_(True)).count()
    return {
        "engine_ready": recommender.is_ready,
        "indexed_rows": len(recommender.rows),
        "verified_resolutions": verified_count,
    }
