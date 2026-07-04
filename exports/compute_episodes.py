# -*- coding: utf-8 -*-
"""
compute_episodes.py — суточный батч-пересчёт авторазметки эпизодов.

Точка входа для офлайн-пересчёта (раз в сутки по расписанию). Загружает телеметрию
и прогноз обводнённости, прогоняет алгоритм авторазметки (episode_rules) и пишет
таблицу эпизодов (с готовой колонкой `explanation`) атомарно. Приложение/API читают
готовый файл — НИКАКОГО пересчёта на лету.

Пример:
    python compute_episodes.py \
        --telem well_graph_data_all_full_2026-06-18.csv \
        --wct   full_inference_water_cut.csv \
        --out   episodes.parquet \
        --model-version episode_rules_v10_2

CLI коды возврата: 0 — успех; 1 — фатальная ошибка загрузки.
"""
import argparse
import datetime as dt
import logging
import os
import sys

import numpy as np
import pandas as pd

import episode_rules_v10_2 as er   # сам алгоритм; интерфейс run_all(tele, vsp) -> DataFrame

log = logging.getLogger("compute_episodes")

OUT_COLUMNS = [
    "well_id", "label", "start", "end", "dur_d",
    "confidence", "confidence_tier", "sig_label", "sig_margin", "signals",
    "explanation", "computed_at", "model_version",
]

# Маппинг метки авторазметки -> построчная колонка auto_target_* (зеркало ручных target_*)
# Кодировка значений совпадает с ручной разметкой ('1.0' — признак; trend — falling/rising/...).
LABEL_TO_AUTO = {
    "Работа":                 ("auto_target_well_state", "work"),
    "Остановка":              ("auto_target_well_state", "stop"),
    "ГДИ":                    ("auto_target_gdi", "1.0"),
    "УВЧ":                    ("auto_target_uvch", "1.0"),
    "УМЧ":                    ("auto_target_umch", "1.0"),
    "РПТЧ":                   ("auto_target_rptch", "1.0"),
    "Периодическая работа":    ("auto_target_periodic", "1.0"),
    "НУР":                    ("auto_target_nur", "1.0"),
    "Снижение Рпл":           ("auto_target_rpl_trend", "falling"),
    "Рост Рпл":               ("auto_target_rpl_trend", "rising"),
    "Деградация ЭЦН":         ("auto_target_esp_degradation", "1.0"),
    "Рост обводненности":     ("auto_target_wct_trend", "growing"),
    "Снижение обводненности": ("auto_target_wct_trend", "falling"),
    "Снижение Кпрод":         ("auto_target_kprod_trend", "declining"),
    "Рост Кпрод":             ("auto_target_kprod_trend", "rising"),
    "Осложнённый фонд":       ("auto_target_complicated_fund", "1.0"),
    "СППВ":                   ("auto_target_sppv", "1.0"),
    "ВГФ":                    ("auto_target_vgf", "1.0"),
    "Рост ГФ":                ("auto_target_gas_factor_trend", "rising"),
    "Снижение ГФ":            ("auto_target_gas_factor_trend", "falling"),
    "Деоптимизация":          ("auto_target_deoptimization", "1.0"),
    "Увеличение подачи воды":  ("auto_target_water_supply_up", "1.0"),
}


def attach_auto_target(tele: pd.DataFrame, episodes: pd.DataFrame) -> pd.DataFrame:
    """Заполнить ПОСТРОЧНЫЕ колонки auto_target_* из эпизодов (зеркало ручных target_*).
    Строка получает значение, если её telemetry_time попадает в интервал эпизода
    соответствующей категории. Колонки создаются при отсутствии."""
    out = tele.copy()
    ts = pd.to_datetime(out["telemetry_time"], errors="coerce")
    for col in {c for c, _ in LABEL_TO_AUTO.values()}:
        if col not in out.columns:
            out[col] = np.nan
    ep = episodes.copy()
    ep["start"] = pd.to_datetime(ep["start"]); ep["end"] = pd.to_datetime(ep["end"])
    for wid, g in ep.groupby("well_id"):
        mwell = (out["well_id"] == wid).values
        idxw = out.index[mwell]; tsw = ts[mwell]
        for _, r in g.iterrows():
            mp = LABEL_TO_AUTO.get(r["label"])
            if not mp:
                continue
            col, val = mp
            sel = idxw[((tsw >= r["start"]) & (tsw <= r["end"])).values]
            out.loc[sel, col] = val
    return out


def attach_auto_episode(tele: pd.DataFrame, episodes: pd.DataFrame) -> pd.DataFrame:
    """Заполнить ПОСТРОЧНЫЕ слоты auto_episode_* (поэпизодно, "|"-склейка эпизодов,
    перекрывающих сутки строки), ВКЛЮЧАЯ auto_episode_explanations. Все списки строятся
    в одном порядке -> labels/start/end/confidences/explanations согласованы.
    Это закрывает баг «объяснения = -»: слот объяснений теперь есть в выгрузке."""
    from collections import defaultdict
    out = tele.copy()
    day = pd.to_datetime(out["telemetry_time"], errors="coerce").dt.floor("D")
    cols = {"auto_episode_labels": "label", "auto_episode_start_dates": "start",
            "auto_episode_end_dates": "end", "auto_episode_confidences": "confidence_tier",
            "auto_episode_explanations": "explanation"}
    for c in cols:
        out[c] = ""
    ep = episodes.copy()
    ep["start"] = pd.to_datetime(ep["start"]); ep["end"] = pd.to_datetime(ep["end"])
    for wid, g in ep.groupby("well_id"):
        mwell = (out["well_id"] == wid).values
        idxw = out.index[mwell]; dayw = day[mwell]
        per_day = defaultdict(lambda: defaultdict(list))
        for _, r in g.iterrows():
            for d in pd.date_range(r["start"].normalize(), r["end"].normalize(), freq="D"):
                per_day[d]["label"].append(str(r.get("label", "")))
                per_day[d]["start"].append(str(r.get("start", "")))
                per_day[d]["end"].append(str(r.get("end", "")))
                per_day[d]["confidence_tier"].append(str(r.get("confidence_tier", "")))
                per_day[d]["explanation"].append(str(r.get("explanation", "")))
        for c, src in cols.items():
            out.loc[idxw, c] = dayw.map(lambda d: "|".join(per_day.get(d, {}).get(src, []))).values
    return out


def compute_kprod(tel: pd.DataFrame, wells=None) -> pd.DataFrame:
    """Суточный РАСЧЁТНЫЙ Кпрод по каждой скважине -> (well_id, date, kprod_calc).
    Расчётный Кпрод = ctx.kprod из episode_rules (Qж/(Рпл-Рзаб), единственное место с TR).
    Для отображения линией на графике ('Кпрод_алгоритм')."""
    wells = wells or sorted(tel["well_id"].dropna().unique())
    parts = []
    for wid in wells:
        a = tel[tel["well_id"] == wid]
        if a["telemetry_time"].notna().sum() < 20:
            continue
        try:
            ctx = er.WellCtx(a.set_index("telemetry_time").sort_index(), build_vsp(a, wid))
            k = getattr(ctx, "kprod", None)
            if k is None or len(k.dropna()) == 0:
                continue
            d = k.dropna().resample("1D").median().dropna()
            parts.append(pd.DataFrame({"well_id": wid,
                                       "date": d.index.normalize(),
                                       "kprod_calc": np.round(d.values, 3)}))
        except Exception as ex:
            log.exception("расчётный Кпрод для %s упал: %s", wid, ex)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["well_id", "date", "kprod_calc"])


def build_vsp(df: pd.DataFrame, wid: str) -> pd.DataFrame:
    """Распарсить '|'-разделённые VSP-режимы из строк телеметрии в таблицу интервалов."""
    rows = []
    for st, ss, se in zip(df["vsp_status"], df["vsp_start_time"], df["vsp_end_time"]):
        if pd.isna(st):
            continue
        a, b, c = str(st).split("|"), str(ss).split("|"), str(se).split("|")
        n = max(len(a), len(b), len(c))
        for i in range(n):
            rows.append((wid,
                         a[i].strip() if i < len(a) else "",
                         b[i].strip() if i < len(b) else "",
                         c[i].strip() if i < len(c) else ""))
    v = pd.DataFrame(rows, columns=["well_id", "status", "start", "end"]).drop_duplicates()
    v["start"] = pd.to_datetime(v["start"], errors="coerce")
    v["end"] = pd.to_datetime(v["end"], errors="coerce")
    return v.dropna(subset=["start"])


def load_inputs(telem_path: str, wct_path: str | None) -> pd.DataFrame:
    """Телеметрия + (опционально) подмешанный суточный прогноз обводнённости wct_pred."""
    tel = pd.read_csv(telem_path, low_memory=False)
    if "telemetry_time" not in tel.columns:
        raise ValueError("в телеметрии нет колонки telemetry_time")
    tel["telemetry_time"] = pd.to_datetime(tel["telemetry_time"], errors="coerce")

    if wct_path and os.path.exists(wct_path):
        wct = pd.read_csv(wct_path, low_memory=False)
        wct.columns = [c.strip().lstrip("﻿") for c in wct.columns]
        wct["date"] = pd.to_datetime(wct["date"]).dt.floor("D")
        wct = wct.rename(columns={"well": "well_id"})[["well_id", "date", "wct_pred"]]
        tel["day"] = tel["telemetry_time"].dt.floor("D")
        tel = tel.merge(wct, left_on=["well_id", "day"], right_on=["well_id", "date"], how="left")
        tel = tel.drop(columns=[c for c in ("date", "day") if c in tel.columns])
        log.info("wct_pred подмешан: %d / %d строк", int(tel["wct_pred"].notna().sum()), len(tel))
    else:
        log.warning("файл прогноза обводнённости не задан/не найден — категории "
                    "Рост/Снижение обводнённости будут пустыми")
    return tel


def compute(tel: pd.DataFrame, model_version: str, wells=None) -> pd.DataFrame:
    """Прогнать авторазметку по каждой скважине. Ошибка по одной скважине не валит остальные."""
    computed_at = dt.datetime.now(dt.timezone.utc)
    wells = wells or sorted(tel["well_id"].dropna().unique())
    parts, failed = [], []
    for wid in wells:
        a = tel[tel["well_id"] == wid]
        if a["telemetry_time"].notna().sum() < 20:
            continue
        try:
            df = er.run_all(a.set_index("telemetry_time").reset_index(),
                            build_vsp(a, wid), wells=[wid])
            parts.append(df)
        except Exception as ex:
            failed.append(wid)
            log.exception("скважина %s упала: %s", wid, ex)
    if not parts:
        return pd.DataFrame(columns=OUT_COLUMNS)
    out = pd.concat(parts, ignore_index=True)
    out["computed_at"] = computed_at.isoformat()
    out["model_version"] = model_version
    for c in OUT_COLUMNS:
        if c not in out.columns:
            out[c] = ""
    out = out[OUT_COLUMNS]
    log.info("эпизодов: %d | скважин: %d | упало: %d %s",
             len(out), out["well_id"].nunique(), len(failed), failed or "")
    return out


def write_atomic(df: pd.DataFrame, out_path: str):
    """Атомарная запись: во временный файл, затем rename (UI не читает полу-записанное)."""
    tmp = out_path + ".tmp"
    if out_path.lower().endswith(".parquet"):
        df.to_parquet(tmp, index=False)
    else:
        df.to_csv(tmp, index=False, encoding="utf-8-sig")
    os.replace(tmp, out_path)
    log.info("записано: %s", out_path)


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Суточный пересчёт авторазметки эпизодов")
    ap.add_argument("--telem", required=True, help="CSV телеметрии (well_graph_data_all_full_*.csv)")
    ap.add_argument("--wct", default=None, help="CSV прогноза обводнённости (full_inference_water_cut.csv)")
    ap.add_argument("--out", required=True, help="выходной файл (.parquet или .csv)")
    ap.add_argument("--model-version", default=getattr(er, "MODEL_VERSION", "episode_rules_v10_2"))
    ap.add_argument("--wells", default=None, help="подмножество скважин через запятую (опц.)")
    ap.add_argument("--enrich", default=None, help="доп. выход: телеметрия + построчные auto_target_* (+ kprod_calc) для чарта/экспорта приложения")
    ap.add_argument("--kprod", default=None, help="доп. выход: суточный расчётный Кпрод (well_id,date,kprod_calc) для линии Кпрод_алгоритм")
    args = ap.parse_args(argv)

    try:
        tel = load_inputs(args.telem, args.wct)
    except Exception as ex:
        log.error("ошибка загрузки входных данных: %s", ex)
        return 1

    wells = [w.strip() for w in args.wells.split(",")] if args.wells else None
    out = compute(tel, args.model_version, wells)
    write_atomic(out, args.out)

    kp = None
    if args.kprod or args.enrich:
        kp = compute_kprod(tel, wells)
    if args.kprod:
        write_atomic(kp, args.kprod)
        log.info("расчётный Кпрод (суточный): %s", args.kprod)
    if args.enrich:
        enriched = attach_auto_target(tel, out)
        enriched = attach_auto_episode(enriched, out)   # + auto_episode_explanations (фикс "объяснения = -")
        if kp is not None and len(kp):
            enriched["__day"] = pd.to_datetime(enriched["telemetry_time"], errors="coerce").dt.floor("D")
            enriched = enriched.merge(kp.rename(columns={"date": "__day"}), on=["well_id", "__day"], how="left").drop(columns="__day")
        write_atomic(enriched, args.enrich)
        log.info("обогащённая телеметрия (auto_target_* + kprod_calc): %s", args.enrich)
    print(f"OK: {len(out)} эпизодов по {out['well_id'].nunique()} скважинам -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
