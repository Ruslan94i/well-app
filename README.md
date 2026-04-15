# Анализ скважинной динамики

Минимальное full-stack приложение для визуализации временных рядов по скважине.

Стек:
- Backend: FastAPI, SQLAlchemy, Polars, NumPy
- Frontend: Vue 3, Vite, Tailwind CSS, Naive UI, Plotly

## Структура проекта

```text
well-app/
  backend/
    app/
      api/
        routes/
      core/
      db/
        models/
      schemas/
      services/
      main.py
    requirements.txt
  frontend/
    src/
      components/
      services/
      types/
      views/
    package.json
    vite.config.ts
  README.md
```

## Backend

### 1. Создать виртуальное окружение

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
```

### 2. Установить зависимости

```powershell
pip install -r requirements.txt
```

### 3. Запустить сервер

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend будет доступен по адресу: `http://localhost:8000`

Swagger UI: `http://localhost:8000/docs`

## Frontend

### 1. Установить зависимости

```powershell
cd frontend
copy .env.example .env
npm install
```

### 2. Запустить dev server

```powershell
npm run dev
```

Frontend будет доступен по адресу: `http://localhost:5173`

## Основной endpoint

`GET /api/wells/{well_id}/timeseries`

Query params:
- `date_from`
- `date_to`

Пример:

```text
http://localhost:8000/api/wells/WELL-101/timeseries?date_from=2025-10-01&date_to=2026-03-31
```

## Что уже реализовано

- mock data на 180 дней
- фильтрация по диапазону дат
- Polars-преобразование перед возвратом JSON
- структура под SQLAlchemy model для daily telemetry
- экран выбора скважины
- выбор диапазона дат
- переключение рядов
- Plotly-график с несколькими осями Y

## Что пока не входит

- реальная БД
- загрузка файлов
- ML
- разметка эпизодов
- авторизация
