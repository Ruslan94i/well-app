# Контекстные базы ГТМ, ОПЗ и ГДИ

Проект читает внешние производственные события из Excel-файлов в `backend/data/reference/`:

- `gtm.xlsx` - база ГТМ, лист `База ГТМ`;
- `opz.xlsx` - база ОПЗ, лист `ОПЗ_БАЗА`;
- `gdi.xlsx` - реестр ГДИ, лист `ГДИС`.

Backend отдает контекст по endpoint:

```text
GET /api/wells/{well_id}/context
```

Frontend загружает контекст вместе с телеметрией и отображает маркеры на графике.

## Правила отображения

- ГДИ: точка ставится на `Дата окончания`. В hover выводятся `Вид ГДИ`, `Рпл принятое ВДП, кгс/см2` без дробной части, `Кпрод Вогель, , м3/сут/ ат` с точностью до десятых и `Кач-во ГДИ` без дробной части.
- ОПЗ: точка ставится на `Дата ОПЗ`. В hover выводятся `Вид ОПЗ`, `Категория (БП/КРС)`, `Состав`, `Объем`, `Capex/Opex`.
- ГТМ: точка ставится на `Дата запуска скважины`. В hover выводятся `Имя ГТМ`, `Дебит жидкости после ГТМ, м3`, `Комментарий`.

Ключевые файлы:

- `backend/app/api/routes/context.py`
- `backend/app/schemas/context.py`
- `backend/app/services/xlsx_reference.py`
- `frontend/src/types/timeseries.ts`
- `frontend/src/components/TimeSeriesChart.vue`
- `frontend/src/views/WellTimeSeriesView.vue`
