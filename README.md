Well Dynamics (well-app)
🚀 Quick start
1. Clone repo

git clone https://github.com/Ruslan94i/well-dynamics-internal.git
cd well-app

🖥 Backend

cd backend

python -m venv .venv

Windows:

.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main --reload

Backend:
http://127.0.0.1:8000

🌐 Frontend

cd frontend

npm install
npm run dev

Frontend:
http://localhost:5173 (or next port)

⚙️ Environment

Create:

frontend/.env

VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_USE_MOCK_TELEMETRY=true
VITE_USE_MOCK_EVENTS=true

📊 Notes
Mock telemetry is enabled by default
Event tracks are generated on frontend
Backend is optional for demo
🎯 Purpose

Prototype for:

well production monitoring
event tracking (ESP, OPZ, causes)
time series visualization