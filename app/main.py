from __future__ import annotations

import hashlib
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
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.models import Base, Category, Resolution, Ticket, TicketStatusLog, User


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Tickets API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
        ],
        "Access": [
            "SSO login denied",
            "SAP role missing for approvals",
            "Shared folder permission error",
            "MFA device not recognized",
        ],
        "Hardware": [
            "Laptop overheating rapidly",
            "Docking station not detected",
            "Keyboard keys unresponsive",
            "Monitor stays black after boot",
        ],
        "Network": [
            "VPN disconnects every 10 minutes",
            "Wi-Fi authentication loop",
            "Cannot reach intranet portal",
            "Packet loss on video calls",
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
            status = random.choices(statuses, weights=[4, 4, 5], k=1)[0]
            title = random.choice(issue_templates[category_name])
            description = f"{title}. User reported issue in {category_name.lower()} workflow. Case #{i+1}."
            ticket = Ticket(
                user_id=admin.user_id,
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
        has_user = db.query(User).count() > 0
        if not has_user:
            admin = User(
                name="System Admin",
                email=ADMIN_EMAIL,
                password_hash=hash_password(ADMIN_PASSWORD),
                role="admin",
                department="IT",
            )
            db.add(admin)
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
    _: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Ticket, Category, Resolution)
        .join(Category, Category.category_id == Ticket.category_id)
        .outerjoin(Resolution, Resolution.ticket_id == Ticket.ticket_id)
        .order_by(Ticket.created_date.desc())
        .all()
    )
    by_ticket: dict[int, dict] = {}
    for t, c, r in rows:
        if t.ticket_id not in by_ticket:
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
                "resolution_text": "",
                "resolution_id": None,
            }
        if r and not by_ticket[t.ticket_id]["resolution_text"]:
            by_ticket[t.ticket_id]["resolution_text"] = r.resolution_text
            by_ticket[t.ticket_id]["resolution_id"] = r.resolution_id
    return list(by_ticket.values())


@app.get("/nlp", response_class=HTMLResponse)
def nlp_page() -> str:
    page_path = Path(__file__).resolve().parent.parent / "api" / "pages" / "nlp.html"
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
