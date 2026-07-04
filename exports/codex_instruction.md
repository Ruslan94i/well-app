# Инструкция Codex — внедрить авторазметку эпизодов (один файл-алгоритм + это задание)

## Что есть
**`episode_rules_v10_2.py`** — единственный самодостаточный файл: и алгоритм авторазметки,
и CLI-раннер суточного пересчёта. Зависимости: `pandas`, `numpy`, `pyarrow` (для parquet).
Логику **не менять** — только обвязка вокруг.

Запуск суточного пересчёта:
```bash
python episode_rules_v10_2.py \
  --telem <телеметрия.csv> \
  --wct   <full_inference_water_cut.csv> \
  --out   episodes.parquet \
  --enrich enriched.parquet \   # опц.: построчные auto_target_* + auto_episode_* + kprod_calc
  --kprod  kprod.csv            # опц.: суточный расчётный Кпрод (линия графика)
```
Раннер сам: парсит VSP («|»-строки), подмешивает `wct_pred` по (well_id, дата), гоняет по всем
скважинам, **атомарно** пишет, проставляет `computed_at` (UTC) и `model_version`, не падает из-за
одной скважины.

## ГЛАВНОЕ ТРЕБОВАНИЕ
Приложение должно «летать»: **никакого вызова алгоритма на HTTP-запрос.** Пересчёт — офлайн, по
расписанию (по умолчанию **раз в сутки**), результат в хранилище; API/UI читают только готовое.

## Что внедрить (обвязка)
1. **Планировщик** (cron/Airflow/таймер): запуск `episode_rules_v10_2.py` раз в сутки; пути и час — в конфиге; плюс ручной запуск.
2. **Хранилище `episodes`** (таблица БД или parquet+индекс `(well_id, start)`), заливка **атомарная** (staging→swap).
3. **API**: `GET /wells/{well_id}/episodes?from=&to=&label=&tier=` (только чтение); `GET /episodes/last_computed`.
4. **UI**: на треке «Авторазметка» рисовать категории; **по клику показывать `explanation`** (см. фикс ниже); легенду/цвета строить **динамически из данных**.
5. **Логи**: число скважин/эпизодов, длительность, упавшие скважины, `computed_at`.

## Схема выхода `episodes` (контракт — колонки стабильны)
`well_id, label, start, end, dur_d, confidence, confidence_tier, sig_label, sig_margin, signals, explanation, computed_at, model_version`
Индекс `(well_id, start)`. **`explanation`** — готовый текст в 1 предложение (показывать по клику).

### Категории `label` (21)
Работа, Остановка, ГДИ, РПТЧ, УВЧ, УМЧ, НУР, Периодическая работа, Снижение Рпл, Рост Рпл,
Снижение Кпрод, Рост Кпрод, Осложнённый фонд, Деградация ЭЦН, Деоптимизация, ВГФ, Рост ГФ,
Снижение ГФ, Рост обводненности, Снижение обводненности, СППВ, **Увеличение подачи воды**.
(набор может расти — рендерить дорожки/легенду из данных, не хардкодить)

## Вход (минимум колонок телеметрии)
`well_id, telemetry_time, telemetry_esp_frequency, telemetry_intake_pressure, telemetry_load,
telemetry_qliq, telemetry_gas_liquid_factor, telemetry_bdpv_volume_rate, vsp_status/start/end,
esp_id, tr_reservoir_pressure, tr_liquid_rate, opz_ids`. Лишние колонки игнорируются.
Свежая выгрузка приложения (`well_graph_data_*`) — супер-набор, работает как есть.
Файл `full_inference_water_cut.csv` (`well,date,wct_pred`) — вход от модели обводнённости; без него
категории «Рост/Снижение обводнённости» пустые.

## Заполнение слотов выгрузки приложения (через `--enrich`)
- **`auto_episode_*`** (id/labels/start/end/confidences/**explanations**) — поэпизодно, «|»-склейка
  эпизодов на сутках строки, все списки в одном порядке.
- **`auto_target_*`** — построчные дневные флаги (зеркало ручных `target_*`):

| Метка | Колонка | Значение |
|---|---|---|
| Работа / Остановка | `auto_target_well_state` | `work` / `stop` |
| ГДИ | `auto_target_gdi` | `1.0` |
| УВЧ / УМЧ | `auto_target_uvch` / `auto_target_umch` | `1.0` |
| РПТЧ | `auto_target_rptch` | `1.0` |
| Периодическая работа | `auto_target_periodic` | `1.0` |
| НУР | `auto_target_nur` | `1.0` |
| Снижение / Рост Рпл | `auto_target_rpl_trend` | `falling` / `rising` |
| Деградация ЭЦН | `auto_target_esp_degradation` | `1.0` |
| Рост / Снижение обводненности | `auto_target_wct_trend` | `growing` / `falling` |
| Снижение / Рост Кпрод | `auto_target_kprod_trend` | `declining` / `rising` |
| Осложнённый фонд | `auto_target_complicated_fund` | `1.0` |
| СППВ | `auto_target_sppv` | `1.0` |
| ВГФ | `auto_target_vgf` | `1.0` |
| Рост / Снижение ГФ | `auto_target_gas_factor_trend` | `rising` / `falling` |
| Деоптимизация | `auto_target_deoptimization` | `1.0` |
| **Увеличение подачи воды** | `auto_target_water_supply_up` | `1.0` |

## ФИКС: объяснения показываются как «-»
Причина: слоты `auto_episode_*` не содержали поля под текст. Решение (любое):
- **A (правильно):** тултип/панель берёт `explanation` из таблицы `episodes` по `(well_id, label, start)` — поле непустое у всех эпизодов.
- **B:** использовать слот **`auto_episode_explanations`** из `--enrich` (он параллелен `auto_episode_labels`, тот же порядок) и пробросить в объект эпизода как `explanation`.

## Линия «Кпрод_алгоритм» на графике
Суточный расчётный Кпрод: `--kprod <out>` → файл `well_id,date,kprod_calc` (мёржить по (well_id,дата),
рисовать линией со своей осью), либо колонка `kprod_calc` из `--enrich`.

## Новая дорожка «Увеличение подачи воды»
Категория уже формируется алгоритмом (СППВ/bdpv +20%/сут, нули не считаются). Добавить на трек
«Авторазметка» дорожку из эпизодов `label="Увеличение подачи воды"` (или построчно из
`auto_target_water_supply_up`); тултип — `explanation`.

## Критерии приёмки
- В пути запроса эпизодов нет вызова алгоритма (только чтение БД/файла).
- Суточный джоб атомарно обновляет `episodes`.
- По клику показывается `explanation` (не «-»).
- Падение по одной скважине не теряет остальные; ошибка в логе.
