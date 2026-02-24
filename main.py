from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Generator

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(Enum("user", "admin", name="user_role"), nullable=False)
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    tickets: Mapped[list["Ticket"]] = relationship(back_populates="user")


class Category(Base):
    __tablename__ = "categories"

    category_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    icon: Mapped[str] = mapped_column(String(10), nullable=False)


class Ticket(Base):
    __tablename__ = "tickets"

    ticket_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[str] = mapped_column(
        Enum("low", "med", "high", name="ticket_priority"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        Enum("open", "in_progress", "resolved", "closed", "reopened", name="ticket_status"),
        nullable=False,
        default="open",
    )
    created_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="tickets")
    resolutions: Mapped[list["Resolution"]] = relationship(back_populates="ticket")
    status_logs: Mapped[list["TicketStatusLog"]] = relationship(back_populates="ticket")


class Resolution(Base):
    __tablename__ = "resolutions"

    resolution_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.ticket_id"), nullable=False)
    resolution_text: Mapped[str] = mapped_column(Text, nullable=False)
    added_by: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    resolved_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    helpful_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    ticket: Mapped["Ticket"] = relationship(back_populates="resolutions")


class TicketStatusLog(Base):
    __tablename__ = "ticket_status_log"

    log_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.ticket_id"), nullable=False)
    old_status: Mapped[str] = mapped_column(String(30), nullable=False)
    new_status: Mapped[str] = mapped_column(String(30), nullable=False)
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    ticket: Mapped["Ticket"] = relationship(back_populates="status_logs")


@dataclass
class TicketVectorRow:
    ticket_id: int
    title: str
    category: str
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
        self.tfidf_matrix = None
        self.rows: list[TicketVectorRow] = []
        self._is_fitted = False

    def rebuild_cache(self, session: Session) -> int:
        query_rows = (
            session.query(Ticket, Resolution)
            .join(Resolution, Resolution.ticket_id == Ticket.ticket_id)
            .filter(Resolution.is_verified.is_(True))
            .all()
        )

        self.rows = []
        corpus: list[str] = []

        for ticket, resolution in query_rows:
            combined = f"{ticket.title} {ticket.description} {resolution.resolution_text}"
            processed = preprocess(combined)
            if not processed:
                continue

            self.rows.append(
                TicketVectorRow(
                    ticket_id=ticket.ticket_id,
                    title=ticket.title,
                    category=ticket.category,
                    resolution_id=resolution.resolution_id,
                    resolution_text=resolution.resolution_text,
                )
            )
            corpus.append(processed)

        if not corpus:
            self.tfidf_matrix = None
            self._is_fitted = False
            return 0

        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)
        self._is_fitted = True
        return len(self.rows)

    def get_recommendations(
        self, new_ticket_text: str, top_k: int = 3, min_score: float = 0.15
    ) -> list[dict]:
        if not self._is_fitted or self.tfidf_matrix is None:
            return []

        processed = preprocess(new_ticket_text)
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
                    "matched_ticket_id": row.ticket_id,
                    "matched_title": row.title,
                    "category": row.category,
                    "resolution_id": row.resolution_id,
                    "resolution_text": row.resolution_text,
                }
            )
            rank += 1

        return suggestions


def migrate_resolutions_schema_sqlite(db_engine) -> None:
    with db_engine.begin() as conn:
        table_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='resolutions'")
        ).first()
        if not table_exists:
            return

        cols = conn.execute(text("PRAGMA table_info(resolutions)")).fetchall()
        col_names = {c[1] for c in cols}
        if "created_date" not in col_names:
            return

        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.execute(
            text(
                """
                CREATE TABLE resolutions_new (
                    resolution_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER NOT NULL,
                    resolution_text TEXT NOT NULL,
                    added_by INTEGER NOT NULL,
                    resolved_date DATETIME NOT NULL,
                    helpful_count INTEGER NOT NULL DEFAULT 0,
                    is_verified BOOLEAN NOT NULL DEFAULT 0,
                    FOREIGN KEY(ticket_id) REFERENCES tickets (ticket_id),
                    FOREIGN KEY(added_by) REFERENCES users (user_id)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO resolutions_new (
                    resolution_id, ticket_id, resolution_text, added_by,
                    resolved_date, helpful_count, is_verified
                )
                SELECT
                    resolution_id, ticket_id, resolution_text, added_by,
                    resolved_date, helpful_count, is_verified
                FROM resolutions
                """
            )
        )
        conn.execute(text("DROP TABLE resolutions"))
        conn.execute(text("ALTER TABLE resolutions_new RENAME TO resolutions"))
        conn.execute(text("PRAGMA foreign_keys=ON"))


def build_engine(database_url: str = "sqlite:///helpdesk.db"):
    engine = create_engine(database_url, echo=False, future=True)
    Base.metadata.create_all(engine)
    if database_url.startswith("sqlite:///"):
        migrate_resolutions_schema_sqlite(engine)
    return engine


DATABASE_URL = "sqlite:///helpdesk.db"
engine = build_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
recommender = NLPRecommendationEngine(max_features=5000)
app = FastAPI(title="Helpdesk NLP API")


class RecommendRequest(BaseModel):
    ticket_text: str = Field(min_length=1)
    top_k: int = 3


class RecommendFeedbackRequest(BaseModel):
    resolution_id: int
    helpful: bool


class ResolutionCreateRequest(BaseModel):
    ticket_id: int
    resolution_text: str = Field(min_length=1)
    is_verified: bool = False
    resolved_date: datetime | None = None


class BulkImportRequest(BaseModel):
    csv_path: str = "Historical_ticket_data.csv"


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_admin_user(
    db: Session = Depends(get_db),
    x_user_id: int | None = Header(default=None),
) -> User:
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="x-user-id header is required")

    user = db.get(User, x_user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def ensure_default_admin(db: Session) -> None:
    existing_admin = db.query(User).filter(User.role == "admin").first()
    if existing_admin:
        return

    admin = User(
        name="System Admin",
        email="admin@example.com",
        password_hash="dev-only",
        role="admin",
        department="IT",
    )
    db.add(admin)
    db.commit()


@app.on_event("startup")
def on_startup() -> None:
    with SessionLocal() as db:
        ensure_default_admin(db)
        recommender.rebuild_cache(db)


@app.post("/recommend")
def recommend(payload: RecommendRequest) -> dict:
    results = recommender.get_recommendations(payload.ticket_text, top_k=payload.top_k)
    return {"count": len(results), "suggestions": results}


@app.post("/recommend/feedback")
def recommend_feedback(payload: RecommendFeedbackRequest, db: Session = Depends(get_db)) -> dict:
    resolution = db.get(Resolution, payload.resolution_id)
    if resolution is None:
        raise HTTPException(status_code=404, detail="Resolution not found")

    if payload.helpful:
        resolution.helpful_count += 1
    else:
        resolution.helpful_count = max(0, resolution.helpful_count - 1)

    db.add(resolution)
    db.commit()
    db.refresh(resolution)

    return {
        "resolution_id": resolution.resolution_id,
        "helpful_count": resolution.helpful_count,
        "updated": True,
    }


@app.post("/recommend/rebuild")
def rebuild_recommendation_cache(
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> dict:
    row_count = recommender.rebuild_cache(db)
    return {"message": "TF-IDF cache rebuilt", "indexed_rows": row_count}


@app.post("/resolutions")
def add_resolution(
    payload: ResolutionCreateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> dict:
    ticket = db.get(Ticket, payload.ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    resolution = Resolution(
        ticket_id=payload.ticket_id,
        resolution_text=payload.resolution_text,
        added_by=admin.user_id,
        resolved_date=payload.resolved_date or datetime.utcnow(),
        is_verified=payload.is_verified,
    )
    db.add(resolution)

    ticket.updated_date = datetime.utcnow()
    if payload.is_verified:
        ticket.status = "resolved"
        ticket.resolved_date = resolution.resolved_date

    db.commit()
    db.refresh(resolution)

    recommender.rebuild_cache(db)

    return {
        "resolution_id": resolution.resolution_id,
        "ticket_id": resolution.ticket_id,
        "is_verified": resolution.is_verified,
    }


@app.get("/resolutions/{ticket_id}")
def get_ticket_resolutions(ticket_id: int, db: Session = Depends(get_db)) -> dict:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    rows = (
        db.query(Resolution)
        .filter(Resolution.ticket_id == ticket_id)
        .order_by(Resolution.resolved_date.desc())
        .all()
    )

    return {
        "ticket_id": ticket_id,
        "count": len(rows),
        "resolutions": [
            {
                "resolution_id": r.resolution_id,
                "resolution_text": r.resolution_text,
                "added_by": r.added_by,
                "resolved_date": r.resolved_date,
                "helpful_count": r.helpful_count,
                "is_verified": r.is_verified,
            }
            for r in rows
        ],
    }


@app.post("/resolutions/bulk")
def bulk_import_historical_data(
    payload: BulkImportRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> dict:
    csv_path = Path(payload.csv_path)
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail=f"CSV file not found: {payload.csv_path}")

    inserted_tickets = 0
    inserted_resolutions = 0

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ticket_external_id = row.get("ticket_id", "").strip()
            issue_category = row.get("issue_category", "General").strip() or "General"
            resolution_text = row.get("resolution_text", "").strip()
            is_verified = row.get("is_verified", "true").strip().lower() in {"true", "1", "yes"}
            helpful_count = int(row.get("helpful_count", "0") or 0)

            resolved_raw = row.get("resolved_date", "").strip()
            created_raw = row.get("created_date", "").strip()
            created_date = datetime.fromisoformat(created_raw) if created_raw else datetime.utcnow()
            resolved_date = datetime.fromisoformat(resolved_raw) if resolved_raw else datetime.utcnow()

            if not ticket_external_id or not resolution_text:
                continue

            ticket = (
                db.query(Ticket)
                .filter(Ticket.title == f"Imported {ticket_external_id}")
                .first()
            )
            if ticket is None:
                ticket = Ticket(
                    user_id=admin.user_id,
                    title=f"Imported {ticket_external_id}",
                    description=f"Historical issue: {issue_category}",
                    category=issue_category[:50],
                    priority="med",
                    status="resolved" if is_verified else "closed",
                    created_date=created_date,
                    updated_date=created_date,
                    resolved_date=resolved_date if is_verified else None,
                )
                db.add(ticket)
                db.flush()
                inserted_tickets += 1

            existing_resolution = (
                db.query(Resolution)
                .filter(
                    Resolution.ticket_id == ticket.ticket_id,
                    Resolution.resolution_text == resolution_text,
                )
                .first()
            )
            if existing_resolution:
                continue

            resolution = Resolution(
                ticket_id=ticket.ticket_id,
                resolution_text=resolution_text,
                added_by=admin.user_id,
                resolved_date=resolved_date,
                helpful_count=helpful_count,
                is_verified=is_verified,
            )
            db.add(resolution)
            inserted_resolutions += 1

    db.commit()
    indexed = recommender.rebuild_cache(db)

    return {
        "inserted_tickets": inserted_tickets,
        "inserted_resolutions": inserted_resolutions,
        "indexed_rows": indexed,
    }


if __name__ == "__main__":
    with SessionLocal() as session:
        ensure_default_admin(session)
        recommender.rebuild_cache(session)

    demo_text = "VPN login not working after password reset on office laptop"
    print(recommender.get_recommendations(demo_text, top_k=3, min_score=0.15))
