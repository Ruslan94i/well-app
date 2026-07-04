# -*- coding: utf-8 -*-
"""
eval_harness.py — регрессионный харнесс: сравнивает авторазметку (эпизоды run_all)
с ручной разметкой (target_* колонки) ПОСУТОЧНО, по каждой категории считает
precision / recall / F1. Один общий скор (macro-F1) — для сравнения версий.

Запуск:
    python eval_harness.py [inference_csv]
По умолчанию берёт exports/episodes_ALL_inference_v10.1.csv
"""
import sys, warnings
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")

TELEM = "/sessions/serene-nice-davinci/mnt/exports/well_graph_data_all_full_2026-06-18.csv"
DEFAULT_INF = "/sessions/serene-nice-davinci/mnt/exports/episodes_ALL_inference_v10.1.csv"
OUT = "/sessions/serene-nice-davinci/mnt/exports/eval_report.csv"

# метка авторазметки -> (target-колонка, условие на значение)
def _notna(s):
    v = s.astype(str)
    return (s.notna()) & (v != "") & (v.str.lower() != "nan")

MAP = {
    "ГДИ":                 ("target_gdi", _notna),
    "УВЧ":                 ("target_uvch", _notna),
    "РПТЧ":                ("target_rptch", _notna),
    "Периодическая работа": ("target_periodic", _notna),
    "НУР":                 ("target_nur", _notna),
    "Снижение Рпл":        ("target_rpl_trend", lambda s: s.astype(str) == "falling"),
    "Рост Рпл":            ("target_rpl_trend", lambda s: s.astype(str) == "rising"),
    "Деградация ЭЦН":      ("target_esp_degradation", _notna),
    "Рост обводненности":  ("target_wct_trend", lambda s: s.astype(str) == "growing"),
    "Снижение Кпрод":      ("target_kprod_trend", lambda s: s.astype(str) == "declining"),
    "Рост Кпрод":          ("target_kprod_trend", lambda s: s.astype(str) == "rising"),
    "Осложнённый фонд":    ("target_complicated_fund", _notna),
    "СППВ":                ("target_sppv", _notna),
    "ВГФ":                 ("target_vgf", _notna),
    "Рост ГФ":             ("target_gas_factor_trend", lambda s: s.astype(str) == "rising"),
    "Снижение ГФ":         ("target_gas_factor_trend", lambda s: s.astype(str) == "falling"),
}
# без разметки в файле (не оцениваем): УМЧ, Деоптимизация, Снижение обводненности, Работа, Остановка


def gt_days(tel, label):
    """множество (well_id, day) где ручная разметка положительна для метки."""
    col, cond = MAP[label]
    if col not in tel.columns:
        return {}
    m = cond(tel[col])
    sub = tel.loc[m, ["well_id", "day"]].drop_duplicates()
    out = {}
    for w, g in sub.groupby("well_id"):
        out[w] = set(g["day"])
    return out


def pred_days(inf, label):
    """множество (well_id, day) покрытых эпизодами авторазметки данной метки."""
    sub = inf[inf["label"] == label]
    out = {}
    for w, g in sub.groupby("well_id"):
        days = set()
        for _, r in g.iterrows():
            days |= set(pd.date_range(pd.to_datetime(r["start"]).normalize(),
                                      pd.to_datetime(r["end"]).normalize(), freq="D"))
        out[w] = days
    return out


def main():
    inf_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INF
    inf = pd.read_csv(inf_path, low_memory=False)
    inf["start"] = pd.to_datetime(inf["start"]); inf["end"] = pd.to_datetime(inf["end"])

    tcols = ["well_id", "telemetry_time"] + sorted({c for c, _ in MAP.values()})
    tel = pd.read_csv(TELEM, usecols=lambda c: c in tcols, low_memory=False)
    tel["day"] = pd.to_datetime(tel["telemetry_time"]).dt.floor("D")

    rows = []
    f1s = []
    for label in MAP:
        gt = gt_days(tel, label)
        pr = pred_days(inf, label)
        wells = set(gt) | set(pr)
        TP = FP = FN = 0
        for w in wells:
            g = gt.get(w, set()); p = pr.get(w, set())
            TP += len(g & p); FP += len(p - g); FN += len(g - p)
        prec = TP / (TP + FP) if (TP + FP) else 0.0
        rec = TP / (TP + FN) if (TP + FN) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        gt_tot = sum(len(s) for s in gt.values())
        n_gt_wells = sum(1 for s in gt.values() if s)
        rows.append((label, n_gt_wells, gt_tot, TP, FP, FN, round(prec, 3), round(rec, 3), round(f1, 3)))
        if gt_tot > 0:
            f1s.append(f1)

    rep = pd.DataFrame(rows, columns=["label", "wells_gt", "gt_days", "TP", "FP", "FN",
                                      "precision", "recall", "F1"]).sort_values("F1", ascending=False)
    rep.to_csv(OUT, index=False, encoding="utf-8-sig")
    macro = round(float(np.mean(f1s)), 3) if f1s else 0.0

    print(f"=== Регрессионный отчёт: {inf_path.split('/')[-1]} ===")
    print(rep.to_string(index=False))
    print(f"\nMACRO-F1 (по категориям с разметкой): {macro}")
    print(f"Отчёт сохранён: {OUT}")
    return macro


if __name__ == "__main__":
    main()
