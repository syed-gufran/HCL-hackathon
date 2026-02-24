from app.database import engine
from app.models import Base

from fastapi import FastAPI
from app.database import engine
from app.models import Base


from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import engine, SessionLocal
from app.models import Ticket, User, TicketStatusLog, Resolution
from datetime import datetime

app = FastAPI()

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app = FastAPI()

Base.metadata.create_all(bind=engine)

@app.get("/")
def root():
    return {"message": "Server running"}


Base.metadata.create_all(bind=engine)



# POST TICKET

@app.post("/tickets")
def create_ticket(
    user_id: int,
    title: str,
    description: str,
    category_id: int,
    priority: str,
    db: Session = Depends(get_db)
):
    ticket = Ticket(
        user_id=user_id,
        title=title,
        description=description,
        category_id=category_id,
        priority=priority,
        status="open",
        created_date=datetime.utcnow(),
        updated_date=datetime.utcnow()
    )

    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    return {"message": "Ticket created", "ticket_id": ticket.ticket_id}

# GET TICKETS
@app.get("/tickets")
def get_tickets(user_id: int, role: str, db: Session = Depends(get_db)):
    
    if role == "admin":
        tickets = db.query(Ticket).all()
    else:
        tickets = db.query(Ticket).filter(Ticket.user_id == user_id).all()

    return tickets

# PUT /tickets/{id}/status (ADMIN)

@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return ticket

# PUT /tickets/{id}/escalate
@app.put("/tickets/{ticket_id}/resolve")
def self_resolve(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.status = "resolved"
    ticket.resolved_date = datetime.utcnow()
    ticket.updated_date = datetime.utcnow()

    db.commit()

    return {"message": "Ticket marked as resolved"}



# RESOLUTIONS

@app.post("/resolutions")
def add_resolution(
    ticket_id: int,
    resolution_text: str,
    added_by: int,
    db: Session = Depends(get_db)
):
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    resolution = Resolution(
        ticket_id=ticket_id,
        resolution_text=resolution_text,
        added_by=added_by
    )

    ticket.status = "resolved"
    ticket.resolved_date = datetime.utcnow()
    ticket.updated_date = datetime.utcnow()

    db.add(resolution)
    db.commit()
    db.refresh(resolution)

    return {
        "message": "Resolution added",
        "resolution_id": resolution.resolution_id
    }


@app.get("/resolutions/{ticket_id}")
def get_resolutions(ticket_id: int, db: Session = Depends(get_db)):
    resolutions = db.query(Resolution).filter(
        Resolution.ticket_id == ticket_id
    ).all()

    if not resolutions:
        return {"message": "No resolutions found"}

    return resolutions

@app.post("/resolutions/bulk")
def bulk_import_resolutions(
    resolutions_data: list[dict],
    db: Session = Depends(get_db)
):
    created = []

    for item in resolutions_data:
        resolution = Resolution(
            ticket_id=item["ticket_id"],
            resolution_text=item["resolution_text"],
            added_by=item["added_by"],
            is_verified=item.get("is_verified", False)
        )
        db.add(resolution)
        created.append(resolution)

    db.commit()

    return {"message": f"{len(created)} resolutions imported"}