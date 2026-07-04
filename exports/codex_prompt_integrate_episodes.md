# Промпт для Codex — интеграция авторазметки эпизодов (с предрасчётом раз в сутки)

## Контекст
В репозитории появился модуль авторазметки эпизодов работы скважин: `episode_rules_v10_1.py`.
Главная функция:

```python
run_all(tele_all, vsp_all, wells=None, P=PARAMS, events=None) -> pandas.DataFrame
```

Возвращает таблицу эпизодов со столбцами:
`well_id, label, start, end, dur_d, confidence, confidence_tier, sig_label, sig_margin, signals, explanation`

где `explanation` — готовое объяснение в 1 предложение (показывать в UI по клику на классификатор), а `label` — одна из ~20 категорий (Работа, Остановка, ГДИ, РПТЧ, УВЧ, УМЧ, НУР, Периодическая работа, Снижение/Рост Рпл, Снижение/Рост Кпрод, Осложнённый фонд, Деградация ЭЦН, Деоптимизация, ВГФ, Рост/Снижение ГФ, Рост/Снижение обводненности, СППВ).

**Алгоритм тяжёлый**: для каждой скважины строится `WellCtx` и прогоняется множество детекторов. Его НЕЛЬЗЯ вызывать в цикле обработки HTTP-запросов.

## Входные данные
1. Телеметрия: CSV вида `well_graph_data_all_full_*.csv` (колонки `well_id, telemetry_time, telemetry_*`, `tr_*`, `vsp_status/start/end`, `esp_id`, `opz_*` и т.д.).
2. Прогноз обводнённости: `full_inference_water_cut.csv` (`well, date, wct_pred, ...`). Перед расчётом подмешать `wct_pred` в телеметрию по ключу (well_id, дата).
3. VSP-режимы хранятся в телеметрии "|"-разделёнными строками — их надо распарсить (хелпер ниже).

Подготовка входа (использовать как есть):

```python
def build_vsp(df, wid):
    rows = []
    for st, ss, se in zip(df['vsp_status'], df['vsp_start_time'], df['vsp_end_time']):
        if pd.isna(st):
            continue
        a, b, c = str(st).split('|'), str(ss).split('|'), str(se).split('|')
        n = max(len(a), len(b), len(c))
        for i in range(n):
            rows.append((wid,
                         a[i].strip() if i < len(a) else '',
                         b[i].strip() if i < len(b) else '',
                         c[i].strip() if i < len(c) else ''))
    v = pd.DataFrame(rows, columns=['well_id', 'status', 'start', 'end']).drop_duplicates()
    v['start'] = pd.to_datetime(v['start'], errors='coerce')
    v['end'] = pd.to_datetime(v['end'], errors='coerce')
    return v.dropna(subset=['start'])

# подмешать прогноз обводнённости
wct = pd.read_csv(WCT_PATH); wct.columns = [c.strip().lstrip('﻿') for c in wct.columns]
wct['date'] = pd.to_datetime(wct['date']).dt.floor('D')
wct = wct.rename(columns={'well': 'well_id'})[['well_id', 'date', 'wct_pred']]
tele['day'] = pd.to_datetime(tele['telemetry_time']).dt.floor('D')
tele = tele.merge(wct, left_on=['well_id', 'day'], right_on=['well_id', 'date'], how='left').drop(columns=['date', 'day'])
```

## ГЛАВНОЕ ТРЕБОВАНИЕ — производительность
Приложение должно «летать»: **никакого пересчёта авторазметки на лету (на каждый запрос)**.
Расчёт выполняется **офлайн, по расписанию раз в сутки** (время настраиваемое), результат складывается в хранилище, а API/UI читают только готовые эпизоды. На чтение эпизодов одной скважины должно уходить миллисекунды.

## Задача
1. **Batch-задача `recompute_episodes`** (cron/планировщик, по умолчанию 1 раз в сутки, час задаётся в конфиге):
   - загрузить телеметрию и прогноз обводнённости, подмешать `wct_pred`;
   - по каждой скважине вызвать `run_all` (обернуть в try/except: ошибка по одной скважине не должна валить остальные, залогировать и продолжить);
   - собрать общий DataFrame, проставить `computed_at` (UTC) и `model_version` (например, `episode_rules_v10_1`);
   - **атомарно** заменить предыдущую версию (запись в staging-таблицу/файл, затем swap), чтобы UI никогда не читал полу-записанные данные.
2. **Хранилище** — таблица `episodes` (или parquet + индекс по well_id, если без БД). Схема:
   `well_id (idx), label, start (ts), end (ts), dur_d, confidence, confidence_tier, sig_label, sig_margin, signals (text), explanation (text), computed_at (ts), model_version`.
   Индекс по `(well_id, start)`.
3. **API**: `GET /wells/{well_id}/episodes?from=&to=&label=&tier=` — читает из таблицы (НИКАКОГО вызова `run_all`). Плюс `GET /episodes/last_computed` (отдаёт `computed_at`, чтобы UI показал «данные на …»).
4. **UI**: по клику на классификатор показывать поле `explanation`; уже готово, ничего считать не нужно.
5. **Конфиг**: пути к входным файлам, расписание (cron-строка), `model_version`, флаг `incremental`.
6. (Опционально, если просто) **Инкрементальность**: пересчитывать только скважины, у которых появились новые сутки телеметрии, остальное брать из кэша — чтобы суточный прогон был ещё быстрее.

## Ограничения
- **Не менять логику детекторов** в `episode_rules_v10_1.py` — только обвязка (загрузка, подготовка входа, расписание, хранение, API). Импортировать модуль как есть.
- Зависимости: pandas, numpy (и то, что уже использует модуль). Версии не понижать.
- Часовые пояса: `start/end/computed_at` хранить консистентно (UTC), форматирование — на стороне UI.
- Логирование: число скважин/эпизодов, длительность прогона, список упавших скважин.

## Критерии приёмки
- Эпизоды для любой скважины отдаются API без вызова `run_all` (проверить, что в запрос-пути нет тяжёлого расчёта).
- Полный суточный пересчёт выполняется одним планируемым джобом и атомарно обновляет данные.
- `explanation` присутствует у каждого эпизода и показывается в UI по клику.
- При падении расчёта по одной скважине остальные сохраняются; ошибка залогирована.
- Указать, как запускать пересчёт вручную (CLI-команда) и как настроить расписание.
