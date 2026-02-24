from __future__ import annotations

import streamlit as st

from app.main import recommender
from app.database import SessionLocal
from app.models import Resolution, User


st.set_page_config(page_title="NLP Recommender Check", layout="wide")
st.title("NLP Recommender Check")
st.caption("Connected to app/tickets.db")


def is_admin(db, user_id: int) -> bool:
    user = db.query(User).filter(User.user_id == user_id).first()
    return bool(user and user.role == "admin")


with SessionLocal() as db:
    indexed = recommender.rebuild_cache(db)
    total_resolutions = db.query(Resolution).count()

st.info(f"Indexed rows: {indexed} | total resolutions in DB: {total_resolutions}")

col1, col2, col3 = st.columns([3, 1, 1])
with col1:
    query = st.text_area(
        "Ticket text",
        value="software installation failing due to antivirus",
        height=120,
    )
with col2:
    top_k = st.number_input("Top K", min_value=1, max_value=10, value=3)
with col3:
    min_score = st.number_input("Min Score", min_value=0.0, max_value=1.0, value=0.15, step=0.01)

if st.button("Run Recommendation", type="primary"):
    results = recommender.get_recommendations(query, top_k=int(top_k), min_score=float(min_score))
    if not results:
        st.warning("No recommendation found. Try lower min score or rebuild cache.")
    else:
        for item in results:
            st.markdown(
                f"**#{item['rank']}**  score={item['score']}  ticket={item['ticket_id']}  resolution={item['resolution_id']}"
            )
            st.write(f"Category: {item['category']}")
            st.write(f"Title: {item['title']}")
            st.write(f"Resolution: {item['resolution_text']}")
            st.divider()

st.markdown("---")
st.subheader("Feedback")
f1, f2 = st.columns(2)
with f1:
    resolution_id = st.number_input("Resolution ID", min_value=1, value=1, step=1)
with f2:
    helpful = st.selectbox("Feedback", [True, False], format_func=lambda x: "Helpful" if x else "Not Helpful")

if st.button("Submit Feedback"):
    with SessionLocal() as db:
        row = db.query(Resolution).filter(Resolution.resolution_id == int(resolution_id)).first()
        if not row:
            st.error("Resolution not found")
        else:
            if helpful:
                row.helpful_count += 1
            else:
                row.helpful_count = max(0, row.helpful_count - 1)
            db.commit()
            db.refresh(row)
            st.success(f"helpful_count updated to {row.helpful_count}")

st.markdown("---")
st.subheader("Admin")
a1, a2 = st.columns([1, 2])
with a1:
    admin_id = st.number_input("Admin User ID", min_value=1, value=1, step=1)
with a2:
    st.write("Use this to force refresh TF-IDF cache from database.")

if st.button("Rebuild Cache"):
    with SessionLocal() as db:
        if not is_admin(db, int(admin_id)):
            st.error("Admin user not found or not admin")
        else:
            count = recommender.rebuild_cache(db)
            st.success(f"Cache rebuilt. Indexed rows: {count}")
