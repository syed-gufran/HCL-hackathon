# HCL-hackathon

Clean cloud-ready layout:
- `backend/app/` -> FastAPI app, DB models, NLP engine, HTML page
- `frontend/` -> React (Vite)

## Backend

```bash
cd backend
pip install -r requirements.txt
./run_api.sh
```

Backend entrypoint:
- `app.main:app`

Backend URLs:
- API: `http://127.0.0.1:8000`
- NLP page: `http://127.0.0.1:8000/nlp`
- Docs: `http://127.0.0.1:8000/docs`

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend URL:
- `http://127.0.0.1:5173`

If backend is on different host/port:

```bash
cd frontend
VITE_API_BASE=http://127.0.0.1:8000 npm run dev
```
