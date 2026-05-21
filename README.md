# Well App

Прототип интерфейса для анализа временных рядов, событий и мок-данных по скважинам.

## Быстрый запуск

Открой Git Bash в корне проекта и выполни:

```bash
./run-dev.sh
```

Если не запускается:

```bash
bash run-dev.sh
```

## Запуск через Docker Compose

1. Создай корневой `.env` из шаблона:

```bash
cp .env.example .env
```

2. При необходимости измени порты в `.env`:

```env
BACKEND_PORT=8000
FRONTEND_PORT=5173
```

3. Запусти сервисы:

```bash
docker compose up --build
```

После запуска будут доступны:

* Backend: `http://localhost:<BACKEND_PORT из .env>`
* Frontend: `http://localhost:<FRONTEND_PORT из .env>`

## Что поднимется

* Backend: `http://127.0.0.1:8000`
* Frontend: обычно `http://localhost:5173`
  если порт занят, Vite выберет следующий: `5174`, `5175` и т.д.

## Настройки frontend

Создай файл `frontend/.env`:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_USE_MOCK_TELEMETRY=true
VITE_USE_MOCK_EVENTS=true
```

## Ручной запуск

### Backend

```bash
cd backend
py -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
./.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Что уже настроено

* включён mock-режим telemetry
* есть fallback на mock data при ошибке API
* восстановлены mock time series
* восстановлены mock event tracks
