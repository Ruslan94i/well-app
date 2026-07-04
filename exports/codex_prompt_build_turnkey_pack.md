# Codex prompt: сборка Well App «под ключ»

Используй этот промпт, когда нужно собрать переносимый архив проекта Well App,
который другой пользователь распакует и поднимет в чистом окружении, и в котором
сразу видны: настоящая телеметрия, расходомер (VFM), обводнённость (модель + ХАЛ),
авто- и ручная разметка эпизодов, контроль фонда и настройка модели авторазметки.

---

## Задача

Собери архив `well_app_turnkey_FIXED_<YYYY-MM-DD>.zip` из корня проекта. Перед
сборкой ОБЯЗАТЕЛЬНО проверь и, если нужно, восстанови перечисленные ниже фиксы и
состав данных. Затем собери архив по правилам ниже и прогони самопроверку.
Ничего не удаляй из `backend/data/` без явного разрешения.

## 1. Данные, которые ВСЕГДА должны попасть в архив

Эти файлы часто «терялись» — они не в git (в `.gitignore`), но нужны для работы:

- `backend/data/markup.json` — ручная + авто-разметка (источник истины).
- Вся папка `backend/data/reference/`, обязательно включая:
  - `vfm_daily.csv` — модель расходомера (VFM);
  - `water_cut_algorithm_model.joblib` — модель обводнённости;
  - `water_cut_hal.csv` — точки обводнённости ХАЛ;
  - `auto_episode_segments.csv`, `episodes.csv`, `candidate_auto_episode_segments.csv` — авторазметка;
  - `artificial_lift.xlsx` (ЭЦН), `gtm.xlsx`, `opz.xlsx`, `gdi.xlsx`;
  - `fund_control_*.csv`, `tr_monitoring.csv`, `predicted_qliq*.{csv,json}`, `well_params.json`.
- `well_metrics_v9.csv` в корне — основная телеметрия для графиков.
- `exports/episode_rules_v10_2.py` — активный алгоритм авторазметки (на него
  ссылается `config.episodes_compute_script_path`), а также `compute_episodes.py`
  и прочие `episode_rules_v*.py` / `*.md` из `exports/` (без тяжёлых CSV-дампов).
- Исходники: `backend/app/`, `backend/scripts/`, `frontend/src/` и конфиги
  фронта/бэка, `docker-compose.yml`, `run-dev.sh`, `README.md`, `AGENTS.md`.

## 2. Фиксы в коде, которые должны присутствовать (проверь, при отсутствии — внеси)

1. `backend/app/services/auto_episodes.py`: в `AUTO_EPISODE_FILE_CANDIDATES`
   должен быть `auto_episode_segments.csv` (иначе `/auto-episodes` пустой).
2. `backend/requirements.txt`: должны быть `scikit-learn` и `joblib`
   (нужны для загрузки `water_cut_algorithm_model.joblib`).
3. `backend/app/core/config.py`: НЕ должно быть жёстко зашитого внешнего пути
   `D:\...\telemetry`. Путь телеметрии = внешний диск, если существует, иначе
   `backend/data/reference/`; переопределяется env `TELEMETRY_DATA_PATH`.
4. Реальные данные по умолчанию (mock выключен): `frontend/.env`, корневой
   `.env.example` и `docker-compose.yml` → `VITE_USE_MOCK_TELEMETRY=false`,
   `VITE_USE_MOCK_EVENTS=false`, `VITE_API_BASE_URL=http://127.0.0.1:8000`.
5. `frontend/src/views/WellTimeSeriesView.vue`: событийные треки в реальном
   режиме строятся из API, мок-генератор — только при `VITE_USE_MOCK_EVENTS=true`.
6. `backend/app/services/csv_timeseries.py`: в фолбэк-загрузчике
   `_load_timeseries_frame_cached` должна подмешиваться `reference/water_cut_hal.csv`
   (иначе точки ХАЛ пропадают без агрегированной телеметрии).

## 3. Что НЕ включать в архив

`.git`, любые `.venv`/`venv`, `node_modules`, `frontend/dist`, `__pycache__`,
`*.pyc`, `*.log`, `.mypy_cache`/`.ruff_cache`/`.pytest_cache`, `project-private/`,
`tmp_attr_test/`, `backend/data/_agg_checkpoints/`, бэкапы разметки
(`markup.before_restore_*.json`, `markup.full_with_auto_backup.json`), тяжёлые
исторические CSV-дампы из `exports/` (`well_graph_data_all*.csv` и т.п.), а также
любые ранее собранные архивы и распакованные папки (`*.zip`, `well_app_turnkey*/`,
`well_app_*dump*/`, `well_app_*package*/`, `well_app_*release*/`) — чтобы не было
вложенности архива в архив.

## 4. Порядок сборки

1. Скопируй проект во временную папку стейджинга по правилам разделов 1 и 3.
2. Добавь `START_HERE.md` (инструкция запуска: Docker / локально, что должно
   работать, troubleshooting: прогрев `markup.json` ~38 МБ и `/api/health`, VPN,
   перехватывающий 127.0.0.1, возможный порт Vite 5174).
3. Собери zip из папки стейджинга.

## 5. Самопроверка перед выдачей (обязательно)

- В архиве присутствуют: `backend/data/markup.json`, `well_metrics_v9.csv`,
  `backend/data/reference/water_cut_hal.csv`, `vfm_daily.csv`,
  `water_cut_algorithm_model.joblib`, `auto_episode_segments.csv`, `episodes.csv`,
  `exports/episode_rules_v10_2.py`, `frontend/.env`, `START_HERE.md`.
- В архиве НЕТ: `.venv/`, `node_modules/`, `.git/`, `*.pyc`, вложенного
  `well_app_turnkey/well_app_turnkey...`, посторонних `*.zip`.
- Smoke-тест бэкенда (в чистом venv по `requirements.txt`): `/api/health` → ok;
  `/api/wells` → непустой список; таймсерия любой скважины содержит ненулевые
  `water_cut_hal`; авторазметка (`/episodes`) непустая; VFM-кэш строится из
  `vfm_daily.csv`; модель обводнённости грузится без ошибок joblib/sklearn.
- Выведи итог: имя архива, размер, число файлов и результат проверок.
