#!/bin/bash
set -e

echo "Запуск backend..."
cd backend

if [ ! -d ".venv" ]; then
  py -m venv .venv
fi

./.venv/Scripts/python.exe -m pip install -r requirements.txt
./.venv/Scripts/python.exe -m uvicorn app.main:app --reload &

echo "Запуск frontend..."
cd ../frontend

if [ ! -d "node_modules" ]; then
  npm install
fi

npm run dev