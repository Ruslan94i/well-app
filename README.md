# Well App

Well App - прототип приложения для инженерного анализа скважинной динамики, просмотра телеметрии и многоуровневой разметки эпизодов. Проект помогает сравнивать временные ряды, контекстные события, установленное ЭЦН-оборудование, ручную разметку и авторазметку на едином графике.

## Возможности

- Просмотр телеметрии скважин с масштабированием по времени, быстрыми пресетами зума и прокруткой окна.
- Отображение контекстных треков: ГТМ / ОПЗ / ГДИ, ВСП, установленный ЭЦН, ручная разметка и авторазметка.
- Многоуровневая ручная разметка эпизодов: работа/остановка, ГДИ, УВЧ, РПТЧ, периодическая работа, НУР, тренды Рпл, обводненность, Кпрод, СППВ, осложненный фонд, деградация ЭЦН.
- Импорт результатов rule-based / ML-инференса авторазметки в слой `auto-inference`.
- Экспорт графовых данных в CSV для подготовки ML-датасета.
- Вкладка настройки модели авторазметки с параметрами правил по группам месторождений и сохранением настроек в `localStorage`.

## Стек

- Backend: FastAPI, Uvicorn, Pydantic Settings, Polars, NumPy.
- Frontend: Vue 3, Vite, TypeScript, Tailwind CSS, Naive UI, Plotly.
- Запуск: локально через Python/Node.js или через Docker Compose.

## Быстрый запуск локально

Из корня проекта:

```bash
bash run-dev.sh
```

Обычно сервисы будут доступны здесь:

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`

Если нужно запустить вручную:

```bash
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

```bash
cd frontend
npm run dev
```

## Запуск через Docker Compose

Создайте `.env` из шаблона:

```bash
cp .env.example .env
```

Проверьте порты:

```env
BACKEND_PORT=8000
FRONTEND_PORT=5173
```

Запустите:

```bash
docker compose up --build
```

## Данные и разметка

- `backend/data/` - локальные данные приложения и сохраненная разметка.
- `backend/data/markup.json` - основное хранилище ручной и автоматической разметки.
- `backend/scripts/import_rule_based_inference.py` - импорт multilabel CSV-инференса в слой авторазметки.

Важно: файлы данных и разметки не удаляются без явного решения пользователя.

## Проверки

Backend:

```bash
backend\.venv\Scripts\python.exe -m compileall backend\app backend\scripts
```

Frontend:

```bash
cd frontend
npm run build
```

Проверка доступности frontend:

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:5173/ | Select-Object -ExpandProperty StatusCode
```

## GitHub Description

Рекомендуемое описание репозитория:

```text
Well App: анализ скважинной телеметрии, ЭЦН-контекста, ручной и автоматической разметки эпизодов для ML-датасетов.
```
