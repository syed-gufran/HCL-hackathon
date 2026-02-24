# HCL-hackathon

On Another System
you will have to do:

git clone <repo>
cd project
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
./run_api.sh


## Frontend (React + NLP integration)

cd frontend
npm install
npm run dev

Backend API must be running on http://127.0.0.1:8000 (default).
If needed, set custom API base:

VITE_API_BASE=http://127.0.0.1:8000 npm run dev

## Demo Admin + Seeded Data

Default admin login (backend auth):
- email: `admin@company.com`
- password: `admin123`

Database now seeded with:
- one admin user only
- 4 categories: Software, Access, Hardware, Network
- 40 tickets per category (160 total)

Useful APIs:
- `POST /api/auth/login`
- `GET /api/auth/me` (Bearer token)
- `GET /api/analytics/overview` (Bearer token)
- `GET /api/tickets` (Bearer token)
- `POST /api/admin/seed-demo?per_category=40` (Bearer admin token)
