# -*- coding: utf-8 -*-
"""
episode_rules_v9_3.py — episode_rules_v9_9.py — v9.9: (1) нециклич. Рост Рпл по Рпл-точкам ВНЕ НУР;
(2) циклич. Рост Рпл при перекрытии Снижением Кпрод>=75% убирается (деградация, Ic_914);
(3) циклич. Снижение Кпрод только на скважинах с кластерами ОПЗ (убирает Кпрод-шум Ic_367 и др.);
(4) нециклич. Снижение Рпл, примыкающее к Кпрод без восстановления интейка при стаб. плато, -> Снижение Кпрод (Vt_3311).
Изменения относительно v4:
  1. nur_gate_stop_h = 12.0 (было 0.5) — убраны ложные НУР от периодических остановок
  2. НУР: пропуск если первый рабочий день > nur_max_d суток после пуска (ещё одна длинная остановка вмешалась)
  3. НУР: ноль в Рпр «до остановки» трактуется как отсутствие данных; fallback смотрит на 5 сут вперёд
  4. УВЧ: подавление если любая остановка закончилась в предшествующие 2 сут (возврат частоты ≠ УВЧ)
  5. Кпрод: не выделяется внутри НУР («либо одно, либо другое»)
  6. Рост Рпл: только монотонный рост Рпл, не в первые 7 сут после крупной остановки
  7. РПТЧ: фильтр range>15Гц (пуск/останов) + межсуточный критерий (уставки меняются ≥3 раза, std≥1Гц)
  8. Снижение Рпл: критерий C — долгосрочный тренд в рамках одного рабочего сегмента (45-суточное окно)
"""
# v9 (физика Кпрод): Снижение Кпрод и Снижение Рпл различаются по ТЕМПУ
#   падения РАСЧЁТНОГО Кпрод = Qж/(Рпл-Рзаб):
#     - быстрое падение (>= kprod_fast_pct_week %/нед) -> Снижение Кпрод (деградация);
#     - плавное -> это просто Снижение Рпл (истощение/тренд Рпл).
#   Снимает артефакты: при залипшем Qж и тренде Рпл расчётный Кпрод почти не
#   падает (медленно) -> НЕ Кпрод (напр. Ic_367). Реальная деградация (Ic_914,
#   падает свежий Qж) -> быстрый темп -> Кпрод. НУР сюда не входит (свой триггер).
# v8 сигнатурный слой (баланс правил и сигнатур):
#   - Правила решают, КАКИЕ эпизоды есть (детекторы без изменений к v7).
#   - Сигнатуры решают УВЕРЕННОСТЬ и дают совещательную метку:
#       * НУР <-> Снижение Рпл: sig_label/sig_margin (привязка к остановке, пик
#         после пуска, скорость/длит. спада, тренд Qж). При сильном расхождении
#         с меткой правила -> tier='low' (флаг на ревью), сама метка НЕ меняется.
#       * Снижение Кпрод: высокая уверенность ТОЛЬКО при подтверждении падением Qж
#         (Ic_367 «шум Рпр» без подтверждения -> medium/low; Ic_914 реальный -> high).
#   - SIG_RELABEL (по умолч. False): мягкая переразметка пограничных НУР<->Снижение
#     при марже >= SIG_RELABEL_MARGIN. Выкл, чтобы не двигать одобренную разметку.
# v7 адресные правки (по экспертному фидбэку):
#   - ГДИ: gdi_min_pts 5->4 (быстрая КВД из 4 точек) + датчик Рпр должен работать
#   - Снижение Кпрод: НЕ срабатывает, когда скважина стоит (нет рабочих суток в интервале)
#   - РПТЧ: критерий разворотов в СКОЛЬЗЯЩЕМ окне -> ловит начало РПТЧ в середине сегмента
#   - УВЧ: критерий превышения доостановочного уровня / устоявшейся полки
#   - ГДИ/РПТЧ/Рост Рпл: пороги достоверности данных, без целых-Гц
# v6 дополнения (signatures pipeline):
#   A. SIGNATURES — датасет идеального поведения по категориям (из экспертной разметки)
#   B. РПТЧ критерий В: доля суток с «целой» уставкой Гц ≥ rptch_round_frac
#   C. НУР: проверка монотонности снижения Рпр (nur_monotone_ratio)
#   D. Снижение Рпл критерий Б: фильтр «единого скачка» (snizh_step_ratio)
#   E. score_episode() — confidence 0–1 для каждого найденного эпизода
#   F. run_all() возвращает колонку confidence
import pandas as pd, numpy as np

PARAMS = dict(
    # Остановка / Работа
    stop_freq_hz        = 5.0,
    stop_min_dur_min    = 30,
    vsp_override_min_run_d = 3,  # сут реальной работы внутри vsp-простоя, чтобы признать простой ошибочным и обрезать
    long_stop_h         = 12.0,
    skip_restart_h      = 6.0,
    # ГДИ
    gdi_min_pts         = 5,   # мин. точек Рпр в простое
    gdi_min_run         = 4,   # мин. длина рост-серии КВД (был 5 - резал быстрые ГДИ из 4 точек)
    gdi_max_d           = 20,  # сут: (зарезервировано) ограничение длительности ГДИ — сейчас не применяется
    gdi_dip_bar         = 2.0,
    gdi_total_rise_bar  = 5.0,   # бар: мин. суммарный рост Рпр в КВД (был 10 - резал реальные ГДИ)
    gdi_min_stop_h      = 48.0,
    gdi_min_valid_frac  = 0.6,   # мин. доля НЕнулевых точек Рпр в простое: датчик должен работать (иначе это просто остановка)
    # РПТЧ
    rptch_osc_hz        = 1.5,   # Гц: внутрисуточный размах = «колеблющиеся» сутки
    rptch_max_range_hz  = 15.0,  # Гц: range выше — день пуска/останова, не РПТЧ
    rptch_density       = 0.20,
    rptch_min_osc_days  = 2,
    rptch_merge_gap_d   = 60,  # сут: РПТЧ перекрывает остановки (расширяем на весь рабочий период)
    rptch_interday_std  = 1.0,   # Гц: стд суточных средних частоты для межсуточного критерия
    rptch_interday_rev  = 3,     # мин. кол-во смен направления (reversals) суточных средних
    rptch_interday_min_d = 14,   # мин. рабочих суток для применения межсуточного критерия
    rptch_rev_rate      = 0.30,  # развороты/сутки: настоящий РПТЧ = частые хождения вверх-вниз (Ic_370~0.5), а не редкие ступени (Ic_349~0.02)
    rptch_roll_win      = 21,    # сут: окно для скользящей оценки плотности разворотов (начало РПТЧ среди сегмента)
    rptch_roll_min_std  = 0.1,   # Гц: мин. амплитуда в окне (РПТЧ может быть мелкоамплитудным: 59.7<->60.0)
    rptch_post_restart_d = 60,   # сут: окно стабилизации после пуска — развороты там НЕ считаем (рамп != РПТЧ; напр. Ya_357)
    rptch_restart_stop_h = 24,   # ч: стоп длиннее -> после него окно стабилизации
    # УВЧ
    uvch_rise_hz        = 0.9,   # Гц: мин. ПРЕВЫШЕНИЕ пика над базой (ступени >=1.0, шум/возврат <=0.8)
    uvch_prestab_hz     = 99.0,
    uvch_end_flat_hz    = 0.08,  # Гц: рост сглаж. частоты ниже порога = выход на полку (был 0.2)
    uvch_stop_suppress_d = 1,    # сут: КОРОТКАЯ остановка в эти сутки до старта прогона -> подавить УВЧ (был 2: блип за 2-3 сут глушил реальную ступень)
    # (длинные остановки ≥ long_stop_h не подавляют — после НУР/ГДИ рост частоты честен)
    uvch_smooth_d       = 3,     # сут: окно MA-сглаживания суточной частоты (гасит осцилляции РПТЧ)
    uvch_min_run_d      = 2,     # сут: мин. длительность восходящего прогона частоты
    uvch_start_step     = 0.1,   # Гц: рост сглаж. частоты, открывающий восходящий прогон
    uvch_slow_win       = 45,    # сут: окно для ПОЛОГОГО УВЧ на циклич. скважинах
    uvch_slow_net       = 1.5,   # Гц: мин. рост частоты за окно (медленный устойчивый УВЧ)
    uvch_min_start_hz   = 30.0,  # Гц: рост, стартующий с частоты ниже -> пусковой рамп, не УВЧ
    uvch_recover_lookback_d = 7,    # сут: окно «прогон стартует после остановки» -> сравнение с доостановочным уровнем
    uvch_plateau_d      = 2,     # сут устойчивой частоты после простоя = новая полка (рост от неё = УВЧ, а не восстановление)
    uvch_plateau_tol    = 0.5,   # Гц: разброс на «полке»
    # УВЧ больше НЕ подавляется внутри РПТЧ: устойчивый рост уставок виден поверх осцилляций
    # НУР
    nur_gate_stop_h     = 12.0,  # ч: мин. остановка для НУР (стабильные скважины)
    nur_gate_periodic   = 6.0,   # ч: мин. остановка для НУР на ЦИКЛИЧЕСКИХ скважинах (короткие стопы дают НУР)
    cyclic_stop_rate    = 2.5,   # стоп/мес: выше -> скважина циклическая (адаптивный гейт НУР)
    nur_steep_slope     = 1.0,   # бар/сут: на циклич. скважине НУР тянется пока спад Рпр КРУТОЙ; ниже -> пологий стабильный режим, НУР кончается
    nur_rise_pct        = 0.0,
    nur_end_slope       = 0.3,
    nur_end_confirm_d   = 2,
    nur_max_d           = 30,
    nur_min_d           = 1.0,
    nur_min_drop_bar    = 2.0,
    nur_fallback_days   = 5,     # сут вперёд для fallback-проверки (не было данных «до»)
    nur_max_gap_to_post = 30,    # сут: если первый рабочий день > N сут — пропустить (вмешалась другая остановка)
    nur_peak_search_d   = 5,     # сут: окно поиска ПИКА интейка после пуска (пик может быть отложен)
    nur_peak_tol_bar    = 1.0,   # бар: пик должен подняться не ниже (Рпр_до - tol)
    nur_rise_tol        = 0.15,  # бар: допуск при отслеживании новых минимумов на снижении
    nur_rise_confirm_d  = 2,     # сут устойчивого роста интейка -> конец НУР
    # Периодическая работа
    per_window_d        = 14,
    per_start_n         = 8,
    per_keep_n          = 3,
    per_merge_gap_d     = 30,   # сут: периодич. режим перекрывает остановки
    per_strong_days     = 30,    # сут: мин. число дней с плотным циклом (count>=per_start_n) в стретче, чтобы считать режим УСТОЙЧИВО периодическим и расширять на весь стретч (Ic_805/Vt_606)
    # Снижение Рпл
    snizh_run_d         = 2,
    snizh_total_bar     = 2.0,
    snizh_max_slope     = 2.0,
    snizh_tol           = 0.3,
    snizh_win_d         = 14,
    snizh_win_drop      = 3.0,
    snizh_max_dfreq     = 2.0,
    snizh_seg_win_d     = 45,    # сут: окно долгосрочного критерия C
    snizh_seg_drop_bar  = 4.0,   # бар: снижение за seg_win_d сут в критерии C
    snizh_seg_min_pts   = 45,    # мин. рабочих точек в сегменте для критерия C
    # Рост Рпл
    rost_rise_bar       = 5.0,   # бар: мин. суммарный рост Рпл (был 2.0 - ловил любой дрейф)
    rost_max_gap_d      = 45,    # сут: макс. интервал между соседними точками Рпл в прогоне
    rost_max_ip_drop    = 2.0,
    rost_mono_tol       = 0.5,   # бар: допустимая просадка между точками внутри монотонного прогона
    rost_min_steps      = 2,     # мин. число восходящих шагов (>=3 точки) - фильтр одиночного скачка
    rost_max_step_bar   = 30.0,  # бар: одиночный скачок Рпл выше = артефакт датчика -> разрыв прогона
    # Рост обводненности
    wcut_window_d       = 14,
    wcut_rise_pp        = 3.0,
    # Снижение Кпрод (v9: по темпу расчётного Кпрод)
    kprod_drop_pct      = 15.0,  # (легаси, не используется в v9)
    kprod_max_gap_d     = 45,    # (легаси)
    kprod_fast_pct_week = 10.0,  # %/нед: НИЖНИЙ (глобальный) порог темпа Кпрод
    kprod_noise_mult    = 2.0,   # k: порог = max(floor, k*шум), шум авто из ВОССТАНОВЛЕНИЙ Кпрод (единое правило для всех, без per-well настроек)
    kprod_rate_win      = 14,    # сут: окно оценки темпа падения расчётного Кпрод
    kprod_min_d         = 3,     # мин. длительность эпизода Снижение Кпрод (v9.1: короче, чтобы ловить резкие спады)
    kprod_tol           = 0.03,  # допуск шума в спад-ране
    kprod_min_drop      = 0.10,  # мин. суммарное падение Кпрод в эпизоде (доля)
    kprod_min_pts       = 20,    # мин. суток расчётного Кпрод для применения
    kprod_merge_gap_d   = 10,    # склейка соседних интервалов
    # Осложнённый фонд (по кластеру ОПЗ/обработок)
    cf_win_d            = 60,    # окно подсчёта ОПЗ
    cf_min_opz          = 3,     # >= N обработок в окне = осложнённый фонд (повторные интервенции)
    cf_ext_d            = 45,    # расширение вокруг кластера ОПЗ (хвост спада после обработок)
    cf_merge_gap_d      = 60,    # объединять ОПЗ-кластеры с разрывами до N сут (режим непрерывен)
    kprod_pulse_drop    = 0.06,  # доля: падение расч.Кпрод для импульса (снижен с 0.10 -> ловит мелкие спады)
    kprod_pulse_span    = 5,     # сут назад для оценки падения
    kprod_pulse_gap     = 4,     # склейка соседних импульсов
    kprod_term_win      = 45,    # сут: окно терминального спада Кпрод (нециклич.)
    kprod_term_mono     = 0.7,   # доля убыв. шагов
    kprod_term_drop     = 0.35,  # доля: суммарный спад Кпрод
    kprod_term_rec      = 0.4,   # доля: макс. допустимое восстановление после спада (иначе шум-отскок)
    kprod_rise_pulse    = 0.12,  # доля: рост расч.Кпрод для импульса Рост Кпрод (рост реже/больше падений)
    rpl_env_min_bar     = 5.0,   # бар: мин. изменение огибающей Рпр для Рпл-тренда (циклич.)
    rpl_env_tol         = 1.0,   # бар: допуск немонотонности огибающей
    rost_seg_rise_bar   = 3.0,   # бар: мин. рост Рпр ВНУТРИ рабочего сегмента для Рост Рпл (циклич.)
    rost_kprod_overlap_max = 0.75,  # циклич.: Рост Рпл, перекрытый Снижением Кпрод >= доли, — деградация, не рост (Ic_914)
    kprod_freq_stable_hz   = 3.0,  # Гц: Снижение Кпрод только при |dЧастоты|<порога; крупное изменение -> операционный артефакт (Vt_4401/Vt_605)
    rpl_model_min_bar      = 5.0,  # бар: мин. спад модели Рпл для Снижения Рпл в непрерывной работе (Vt_605 авг-ноя)
    rpl_model_tol          = 1.0,
    rpl_model_max_gap_d    = 45,
    rpl_model_fstab_hz     = 3.0,  # Гц: частота стабильна (истощение, не режим)
    rpl_model_cyc_max      = 1.0,  # стоп-переходов/14сут: ниже -> непрерывная работа (не периодика; отсекает Vt_419/Ya_289)
    rpl_model_min_d        = 30,
    # --- газовый фактор (ВГФ / Рост ГФ / Снижение ГФ) ---
    glf_min_pts            = 15,   # мин. сырых точек ГЖФ в эпизоде (иначе low/не считаем — «пара точек ≠ высокий ГЖФ»)
    vgf_glf_thr            = 60.0, # порог сглаж. ГЖФ для ВГФ
    vgf_bridge_d           = 25,   # сут: заполнение разрывов ГЖФ внутри эпизода ВГФ
    vgf_min_d              = 14,   # сут: мин. длительность ВГФ
    gf_trend_frac          = 0.4,  # доля: мин. относительное изменение ГЖФ для Рост/Снижение ГФ
    gf_trend_min_d         = 21,   # сут: мин. длительность тренда ГФ
    vgf_qdrop_frac         = 0.12, # доля падения Qж за эпизод -> подтверждение
    vgf_stop_rate          = 2.0,  # остановок/мес -> нестабильность (подтверждение)
    vgf_stop_glf_min       = 18.0, # мин. медиана ГЖФ для стоп-управляемого ВГФ (Mc_1004/Mc_20414)
    kprod_reclass_gap_d   = 10,    # нециклич.: зазор (сут) примыкания Снижения Рпл к Кпрод для переклассификации
    kprod_reclass_tol     = 2.0,   # бар: интейк в начале Рпл ниже доснижения базы (не восстановился)
    kprod_reclass_stable_pct = 5.0,  # %/мес: до Кпрод интейк стабилен -> терминальная деградация (Vt_3311), а не истощение
    rost_seg_min_d      = 7,     # сут: мин. длительность роста внутри сегмента
    cf_min_kprod        = 2,     # >= N Снижений Кпрод в окне -> Осложнённый фонд
    cf_kprod_win        = 30,    # окно вывода Осложнённого фонда из Кпрод
    # Деградация ЭЦН
    degr_drop_pct       = 10.0,
    degr_max_gap_d      = 30,
    degr_max_dfreq      = 1.0,
    # СППВ
    sppv_bdpv_min       = 0.5,
    sppv_gap_d          = 14,  # сут: СППВ перекрывает остановки/перерывы
    # ── Signatures v6 ──────────────────────────────────────────────────────
    # РПТЧ критерий В: целочисленные уставки Гц
    rptch_round_tol     = 0.25,  # Гц: |f_daily % 1| < tol → «целая» уставка
    rptch_round_frac    = 0.60,  # мин. доля суток с «целой» уставкой
    rptch_round_min_d   = 5,     # мин. рабочих суток в сегменте для этого критерия
    # НУР: монотонность снижения
    nur_monotone_ratio  = 0.50,  # мин. доля пар(t,t+1) где Рпр[t] > Рпр[t+1]
    # Снижение Рпл: фильтр «единого скачка» (остановка ≠ тренд)
    snizh_step_ratio    = 0.65,  # если один шаг > N*total_drop → скачок, не тренд
    snizh_step_min_pts  = 5,     # мин. точек в окне для применения фильтра
)

# ══════════════════════════════════════════════════════════════════════════
# SIGNATURES — датасет идеального поведения скважины по категориям эпизодов.
# Источник: экспертная разметка + фидбэк по скважинам из чата.
# Используется в score_episode() для confidence-скоринга.
# ══════════════════════════════════════════════════════════════════════════
SIGNATURES = {
    'НУР': dict(
        description=(
            'После крупной остановки (≥12ч) Рпр поднимается выше '
            'доостановочного уровня, затем МОНОТОННО снижается ≥2 бар. '
            'Частота восстановлена. Снижение не должно быть единым скачком.'
        ),
        features=dict(
            post_above_pre   =(2.0, 'Рпр[0] после пуска ≥ Рпр до остановки − 1 бар'),
            monotone_decline =(1.5, 'Доля убывающих пар ≥ nur_monotone_ratio'),
            total_drop       =(1.5, 'Суммарный drop ≥ nur_min_drop_bar'),
            freq_restarted   =(0.5, 'Частота > stop_freq_hz × 2 в среднем'),
        ),
    ),
    'РПТЧ': dict(
        description=(
            'Частота осциллирует между уставками — предпочтительно ЦЕЛЫМИ '
            'значениями Гц (52, 53, 54…). Межсуточный std ≥1 Гц, '
            '≥3 смены направления. Или: ≥20% суток с внутрисуточным размахом ≥1.5 Гц.'
        ),
        features=dict(
            round_hz_fraction=(1.5, 'Доля суток с целой уставкой Гц ≥ rptch_round_frac'),
            interday_std     =(2.0, 'std суточных средних ≥ rptch_interday_std'),
            reversals        =(1.5, '≥ rptch_interday_rev смен направления'),
            intraday_range   =(1.0, 'Доля суток range ≥ rptch_osc_hz'),
        ),
    ),
    'УВЧ': dict(
        description=(
            'Устойчивый рост частоты ≥0.3 Гц не менее 2 суток. '
            'НЕ является возвратом после кратковременной (<12ч) паузы. '
            'Линейный тренд частоты положительный.'
        ),
        features=dict(
            net_rise         =(2.0, 'Ср. частота конца > начала на ≥ uvch_rise_hz'),
            no_short_stop    =(1.5, 'Нет кратких остановок за предшествующие N сут'),
            positive_slope   =(1.0, 'Линейный тренд частоты > 0'),
        ),
    ),
    'Снижение Рпл': dict(
        description=(
            'Плавное монотонное снижение Рпр (MA15) ≥3 бар за 14 сут '
            'или ≥4 бар за 45 сут. Частота при этом не падает. '
            'Снижение распределено во времени — НЕ единый скачок.'
        ),
        features=dict(
            ip_ma_declining  =(2.0, 'MA3(Рпр) в конце < начала − 0.5 бар'),
            not_step_function=(1.5, 'Макс. одиночный шаг < snizh_step_ratio × total_drop'),
            freq_stable      =(1.0, '|Δчастота| ≤ snizh_max_dfreq за период'),
            total_drop       =(1.5, 'Суммарный drop превышает порог'),
        ),
    ),
    'ГДИ': dict(
        description=(
            'Длинная остановка ≥48ч. Во время простоя Рпр монотонно растёт '
            '(кривая восстановления давления, КВД). Суммарный рост ≥10 бар.'
        ),
        features=dict(
            stop_long        =(2.0, 'Длительность ≥ gdi_min_stop_h ч'),
            ip_rises_in_stop =(2.0, 'Рпр растёт во время остановки'),
            ip_total_rise    =(1.5, 'Суммарный рост ≥ gdi_total_rise_bar бар'),
        ),
    ),
    'Периодическая работа': dict(
        description=(
            '≥8 остановок за 14-суточное скользящее окно. '
            'Остановки чередуются с работой ритмично — '
            'коэффициент вариации интервалов ≤ 0.5.'
        ),
        features=dict(
            stop_density     =(2.0, 'Остановок за окно ≥ per_start_n'),
            rhythm_regularity=(1.0, 'std/mean интервалов ≤ 0.5'),
        ),
    ),
}

# ── Сигнатурный слой (v8) ──────────────────────────────────────────────────
SIG_RELABEL        = False   # мягкая переразметка пограничных НУР<->Снижение Рпл
SIG_RELABEL_MARGIN = 0.45    # минимальная маржа сигнатуры для переразметки
SIG = dict(
    w_poststop=2.0, w_peak=1.5, w_speed=1.0, w_dur=1.0, w_qliq=1.5,
    tau_gap_d=5.0, fast_barday=0.30, short_d=20.0, peak_search=5,
    margin_low=0.10, margin_high=0.25,
)

F = 'telemetry_esp_frequency'; IP = 'telemetry_intake_pressure'
QL = 'telemetry_qliq'; WC = 'telemetry_water_cut'; LD = 'telemetry_load'
BD = 'telemetry_bdpv_volume_rate'; BUF = 'telemetry_buffer_pressure'
GLF = 'telemetry_gas_liquid_factor'  # газожидкостной фактор (ГЖФ)
CAS = 'telemetry_casing_pressure'


# ──────────────────────────────────────────────────────────────────────────
def merge_iv(iv, gap=pd.Timedelta(0)):
    iv = sorted([(s, e) for s, e in iv if pd.notna(s) and pd.notna(e) and e > s])
    out = []
    for s, e in iv:
        if out and s <= out[-1][1] + gap:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out

def subtract_iv(iv, holes, min_dur=pd.Timedelta(hours=1)):
    """Вычесть интервалы holes из iv (разрезая/обрезая перекрытия)."""
    holes = merge_iv([(s, e) for s, e in holes])
    out = []
    for s, e in iv:
        segs = [(s, e)]
        for hs, he in holes:
            nxt = []
            for a, b in segs:
                if he <= a or hs >= b:
                    nxt.append((a, b))
                else:
                    if a < hs: nxt.append((a, hs))
                    if he < b: nxt.append((he, b))
            segs = nxt
        out += [(a, b) for a, b in segs if (b - a) >= min_dur]
    return out


def in_any(t, iv):
    return any(s <= t <= e for s, e in iv)

def split_at(iv, breaks):
    out = []
    for s, e in iv:
        cuts = sorted([b for b in breaks if s < b < e])
        prev = s
        for c in cuts:
            out.append((prev, c)); prev = c
        out.append((prev, e))
    return out


# ──────────────────────────────────────────────────────────────────────────
class WellCtx:
    def __init__(self, tele, vsp, P=PARAMS):
        self.P = P
        self.tele = tele.sort_index()
        self.t0, self.t1 = self.tele.index.min(), self.tele.index.max()
        freq = self.tele[F].dropna()
        self.freq = freq

        iv = []
        if vsp is not None and len(vsp):
            d = vsp[vsp['status'].str.contains('downtime', case=False, na=False)]
            frun = freq[freq >= P['stop_freq_hz']]   # моменты явной работы насоса
            for _, r in d.iterrows():
                s = max(r['start'], self.t0)
                e = min(r['end'] if pd.notna(r['end']) else self.t1, self.t1)
                if e <= s: continue
                rin = frun[(frun.index >= s) & (frun.index <= e)]
                if len(rin):
                    span_d = (rin.index.max() - rin.index.min()).days
                    if span_d >= P['vsp_override_min_run_d']:
                        e = min(e, rin.index.min())
                if e > s: iv.append((s, e))
        run_s = None; prev_t = None
        for t, v in freq.items():
            if v < P['stop_freq_hz']:
                if run_s is None: run_s = t
                prev_t = t
            else:
                if run_s is not None:
                    if (prev_t - run_s) >= pd.Timedelta(minutes=P['stop_min_dur_min']):
                        iv.append((run_s, prev_t))
                    run_s = None
        if run_s is not None and (prev_t - run_s) >= pd.Timedelta(minutes=P['stop_min_dur_min']):
            iv.append((run_s, prev_t))

        self.stops = merge_iv(iv, gap=pd.Timedelta(minutes=10))
        self.long_stops = [(s, e) for s, e in self.stops
                           if (e - s) >= pd.Timedelta(hours=P['long_stop_h'])]

        idx = self.tele.index
        m = np.ones(len(idx), bool)
        for s, e in self.stops:
            m &= ~((idx >= s) & (idx <= e))
        for s, e in self.long_stops:
            cut = e + pd.Timedelta(hours=P['skip_restart_h'])
            m &= ~((idx > e) & (idx < cut))
        if F in self.tele:
            fv = pd.to_numeric(self.tele[F], errors='coerce')
            m &= ~(fv < P['stop_freq_hz']).values
        self.wmask = pd.Series(m, index=idx)

        tw = self.tele[self.wmask.values]
        self.wd = tw.select_dtypes(include=[np.number]).resample('1D').mean()
        self.days = self.wd.index

        self.esp_breaks = []
        if 'esp_id' in self.tele:
            e = self.tele['esp_id'].ffill()
            ch = e.ne(e.shift()) & e.notna() & e.shift().notna()
            self.esp_breaks = list(self.tele.index[ch])

        self.stop_starts = [s for s, _ in self.stops]
        _span_d = max((self.t1 - self.t0).days, 1)
        self.cyclic = (len(self.stops) / _span_d * 30.0) >= P['cyclic_stop_rate']

        # v9: РАСЧЁТНЫЙ Кпрод = Qж / (Рпл - Рзаб), Рзаб = рабочий интейк (подвижный).
        # Qж и Рпл берём как есть (ffill held-значений), темп падения важнее уровня.
        self.kprod = pd.Series(dtype=float)
        if 'tr_liquid_rate' in self.tele and 'tr_reservoir_pressure' in self.tele:
            q = pd.to_numeric(self.tele['tr_liquid_rate'], errors='coerce').ffill()
            rpl = pd.to_numeric(self.tele['tr_reservoir_pressure'], errors='coerce').ffill()
            ipf = pd.to_numeric(self.tele[IP], errors='coerce').where(self.wmask.values)
            ipf = ipf.where(ipf > 0)
            dd = rpl - ipf
            K = (q / dd).where(dd > 1)
            self.kprod = K.resample('1D').mean().dropna()

    def work_segments(self):
        segs, prev = [], self.t0
        for s, e in self.long_stops:
            if s > prev: segs.append((prev, s))
            prev = e
        if self.t1 > prev: segs.append((prev, self.t1))
        return split_at(segs, self.esp_breaks)

    def rpr_envelope(self):
        # МЕЖЦИКЛОВАЯ огибающая: представительный Рпр (медиана) по каждому рабочему
        # сегменту между остановками. Внутрицикловый шум усредняется.
        ip = self.wd[IP].dropna()
        env = {}
        for s2, e2 in self.work_segments():
            seg = ip[(ip.index >= s2.normalize()) & (ip.index <= e2.normalize())]
            if len(seg) >= 3:
                env[s2 + (e2 - s2) / 2] = float(seg.median())
        return pd.Series(env).sort_index()

    def pre_stop_ip_mean(self, stop_start, days=3):
        """Среднее Рпр по рабочим точкам за days сут до остановки (нули = нет данных)."""
        ip = self.tele[IP][self.wmask.values].dropna()
        ip = ip[ip > 0]   # нули трактуем как отсутствие данных
        w = ip[(ip.index < stop_start) & (ip.index >= stop_start - pd.Timedelta(days=days))]
        return w.mean() if len(w) else np.nan


# ──────────────────────────────────────────────────────────────────────────
def det_stop(ctx):  return list(ctx.stops)

def det_work(ctx):
    out, prev = [], ctx.t0
    for s, e in ctx.stops:
        if s > prev: out.append((prev, s))
        prev = e
    if ctx.t1 > prev: out.append((prev, ctx.t1))
    return split_at(out, ctx.esp_breaks)


def det_gdi(ctx, gdi_events=None):
    P = ctx.P; out = []
    ip = ctx.tele[IP].dropna()
    ev = [] if gdi_events is None else list(gdi_events)
    for s, e in ctx.stops:
        if (e - s) < pd.Timedelta(hours=P['gdi_min_stop_h']): continue
        if any(max((min(ee if pd.notna(ee) else es + pd.Timedelta(days=1), e)
                    - max(es, s)).total_seconds(), 0) > 0 for es, ee in ev):
            out.append((s, e)); continue
        seg = ip[(ip.index >= s) & (ip.index <= e)]
        if len(seg) < P['gdi_min_pts']: continue
        # Датчик Рпр должен работать: иначе нули/пропуски и «рост» — артефакт,
        # а простой не несёт информации о пластовом давлении -> это не ГДИ.
        seg_valid = seg[seg > 0]
        if len(seg) == 0 or len(seg_valid) / len(seg) < P['gdi_min_valid_frac']: continue
        if len(seg_valid) < P['gdi_min_pts']: continue
        v = seg_valid.values
        best = cur = 1
        for j in range(1, len(v)):
            if v[j] >= v[j-1] - P['gdi_dip_bar']: cur += 1; best = max(best, cur)
            else: cur = 1
        if best < P['gdi_min_run']: continue
        if v.max() - v[0] < P['gdi_total_rise_bar']: continue
        out.append((s, e))
    return merge_iv(out)


def det_rptch(ctx):
    """Два критерия (ИЛИ):
    А) ≥20% рабочих суток с внутрисуточным range Гц ≥ 1.5 (исключая дни range>15 = пуск/останов).
    Б) Межсуточный: std суточных средних ≥ 1.0 Гц + ≥3 смены направления (уставки меняются циклически)
       при мин. 14 рабочих суток в сегменте."""
    P = ctx.P; out = []
    fw = ctx.tele[F][ctx.wmask.values].dropna()
    if not len(fw): return out
    # Внутрисуточный range
    rng = fw.resample('1D').agg(lambda x: x.max() - x.min() if len(x) > 1 else np.nan)
    # Суточные средние для межсуточного критерия
    f_daily = fw.resample('1D').mean()
    # Маска окна стабилизации после длинного пуска (рамп != РПТЧ)
    _keep = pd.Series(True, index=f_daily.index)
    for _ss, _ee in ctx.stops:
        if (_ee - _ss) >= pd.Timedelta(hours=P['rptch_restart_stop_h']):
            _keep[(f_daily.index > _ee) & (f_daily.index <= _ee + pd.Timedelta(days=P['rptch_post_restart_d']))] = False
    f_daily_b = f_daily[_keep]

    for s, e in ctx.work_segments():
        s_n = s.normalize(); e_n = e.normalize()
        # --- Критерий А: внутрисуточный ---
        d_seg = rng[(rng.index >= s_n) & (rng.index <= e_n)].dropna()
        # Исключить дни с range > rptch_max_range_hz (рампа пуска/останова)
        d_valid = d_seg[d_seg < P['rptch_max_range_hz']]
        if len(d_valid) > 0:
            osc = (d_valid >= P['rptch_osc_hz']).sum()
            if osc >= P['rptch_min_osc_days'] and osc / max(len(d_valid), 1) >= P['rptch_density']:
                out.append((s, e)); continue

        # --- Критерий Б: межсуточные хождения частоты в СКОЛЬЗЯЩЕМ окне ---
        # РПТЧ = ЧАСТЫЕ развороты (плотность), и он может НАЧАТЬСЯ в середине
        # сегмента (переход со стабильной частоты на хождения). Поэтому считаем
        # плотность разворотов в окне rptch_roll_win, а не по всему сегменту.
        # (критерий «целых Гц» удалён как ложный: стабильная целая частота != РПТЧ).
        fd = f_daily_b[(f_daily_b.index >= s_n) & (f_daily_b.index <= e_n)].dropna()
        if len(fd) < P['rptch_interday_min_d']: continue
        # (1) ВЕСЬ сегмент: устойчиво высокая плотность разворотов (Ic_370 на всю жизнь)
        std_day = fd.std()
        diff = fd.diff().dropna()
        reversals = int((diff * diff.shift(1) < 0).sum())
        rev_rate = reversals / max(len(fd), 1)
        if (std_day >= P['rptch_interday_std'] and reversals >= P['rptch_interday_rev']
                and rev_rate >= P['rptch_rev_rate']):
            out.append((s, e)); continue
        # (2) иначе СКОЛЬЗЯЩЕЕ окно: РПТЧ может начаться в середине сегмента (Ic_359
        #     с 5 ноя). Амплитуда может быть мелкой (rptch_roll_min_std), главное —
        #     плотность разворотов.
        W = P['rptch_roll_win']; mp = max(W // 2, P['rptch_interday_rev'] + 1)
        sgn = np.sign(fd.diff())
        rev = (sgn * sgn.shift(1) < 0).astype(float)
        roll_rate = rev.rolling(W, center=True, min_periods=mp).mean()
        roll_std  = fd.rolling(W, center=True, min_periods=mp).std()
        osc = (roll_rate >= P['rptch_rev_rate']) & (roll_std >= P['rptch_roll_min_std'])
        out += _flag_to_iv(osc.fillna(False))

    return merge_iv(out, gap=pd.Timedelta(days=P['rptch_merge_gap_d']))


def det_uvch(ctx, rptch_iv=None):
    """УВЧ v8 — устойчивый рост частоты на НОВЫЙ уровень.
    Ключ: УВЧ засчитывается, только если частота ПРЕВЫШАЕТ доостановочный
    уровень (выход на новую уставку). Простой возврат к прежней частоте после
    остановки = восстановление, а не УВЧ — отсекается тем же критерием.
      * суточная рабочая частота, дни с остановкой исключаются (чистый тренд);
      * восходящие прогоны ищутся по сглаж. частоте (полка завершает прогон);
      * амплитуда = пик(сырая частота) - база:
          база = доостановочный уровень, если прогон стартует <=
                 uvch_recover_lookback_d сут после остановки (нужно ПРЕВЫСИТЬ);
          иначе база = уровень полки прямо перед прогоном;
      * засчитывается при амплитуде >= uvch_rise_hz и длит. >= uvch_min_run_d.
    rptch_iv в сигнатуре для совместимости вызова, не используется."""
    P = ctx.P; out = []
    f0 = ctx.wd[F].dropna()
    if len(f0) < 3:
        return out
    stop_days = set()
    for ss, se in ctx.stops:
        dd = ss.normalize()
        while dd <= se.normalize():
            stop_days.add(dd); dd += pd.Timedelta(days=1)
    f = f0[~f0.index.normalize().isin(stop_days)]
    if len(f) < 3:
        return out
    fs = f.rolling(P['uvch_smooth_d'], min_periods=1).mean()
    days = list(fs.index); vs = list(fs.values); n = len(days)
    fraw = f

    def recent_stops(t):
        return [(ss, se) for ss, se in ctx.stops
                if (t - pd.Timedelta(days=P['uvch_recover_lookback_d'])) <= se <= t + pd.Timedelta(hours=23)]

    i = 0
    while i < n - 1:
        if vs[i + 1] - vs[i] < P['uvch_start_step']:
            i += 1; continue
        j = i + 1
        while j < n - 1 and (vs[j + 1] - vs[j]) >= P['uvch_end_flat_hz']:
            j += 1
        s_run, e_run = days[i], days[j]
        dur_d = (e_run - s_run).days
        peak = float(fraw[(fraw.index >= s_run) & (fraw.index <= e_run)].max())

        rec = recent_stops(s_run)
        if rec:
            se_max = max(se for _, se in rec); ss0 = min(ss for ss, _ in rec)
            prior = f0[(f0.index < ss0) & (f0.index >= ss0 - pd.Timedelta(days=5))]
            pre_base = float(prior.median()) if len(prior) else None
            # устоявшаяся полка ПОСЛЕ простоя (новый уровень) — рост от неё = УВЧ
            post_pre = fraw[(fraw.index > se_max) & (fraw.index < s_run)]
            established = (len(post_pre) >= P['uvch_plateau_d'] and
                          (post_pre.max() - post_pre.min()) <= P['uvch_plateau_tol'])
            if pre_base is None or established:
                # база = локальная полка (хватает любого роста на новый уровень)
                if len(post_pre):
                    base = float(post_pre.median())
                else:
                    pr = fraw[fraw.index < s_run]
                    base = float(pr.iloc[-1]) if len(pr) else float(vs[i])
            else:
                # ещё идёт восстановление — нужно ПРЕВЫСИТЬ доостановочный уровень
                base = pre_base
        else:
            pr = fraw[fraw.index < s_run]
            base = float(pr.iloc[-1]) if len(pr) else float(vs[i])

        net = peak - base
        # игнорируем рост, стартующий с низкой частоты (<uvch_min_start_hz) — это
        # пусковой рамп выхода на режим, а не УВЧ
        start_low = float(fraw.loc[s_run]) < P['uvch_min_start_hz'] if s_run in fraw.index else False
        if dur_d >= P['uvch_min_run_d'] and net >= P['uvch_rise_hz'] and not start_low:
            out.append((s_run, e_run + pd.Timedelta(hours=23)))
        i = max(j, i + 1)
    # ПОЛОГИЙ УВЧ на циклических скважинах: медленный устойчивый рост частоты,
    # который run-детектор (порог start_step) пропускает (напр. 50.8->52.6 за 2.5 мес).
    if getattr(ctx, 'cyclic', False):
        fd = ctx.wd[F].dropna()
        if len(fd) > P['uvch_slow_win']:
            full = fd.reindex(pd.date_range(fd.index.min(), fd.index.max(), freq='D')).interpolate(limit=5)
            sm = full.rolling(7, min_periods=3).mean()
            rise = sm - sm.shift(P['uvch_slow_win'])
            flag = pd.Series((rise >= P['uvch_slow_net']).fillna(False), index=sm.index)
            out += merge_iv(_flag_to_iv(flag), gap=pd.Timedelta(days=10))
    return merge_iv(out)


def det_nur(ctx):
    """НУР v7 — пик-якорь + мягкое завершение.
    После остановки (>= nur_gate_stop_h) интейк восстанавливается ВЫШЕ
    доостановочного уровня (пик ищется в первые nur_peak_search_d сут, т.к. пик
    может быть ОТЛОЖЕН), затем МОНОТОННО снижается >= nur_min_drop_bar.
    Снижение тянется, пока интейк ставит новые минимумы (допуск nur_rise_tol),
    и закрывается на устойчивом развороте вверх (nur_rise_confirm_d сут).
    Это чинит: (а) отложенный пик (раньше end_i=0), (б) обрыв на затухающем
    наклоне (раньше снижение <0.3 бар/сут резало эпизод раньше времени)."""
    P = ctx.P; out = []
    ip = ctx.wd[IP].dropna()
    if not len(ip): return out
    for s, e in ctx.stops:
        _gate = P['nur_gate_periodic'] if getattr(ctx, 'cyclic', False) else P['nur_gate_stop_h']
        if (e - s) < pd.Timedelta(hours=_gate): continue
        pre = ctx.pre_stop_ip_mean(s)
        post = ip[ip.index >= e.normalize()].dropna()
        if len(post) < 3: continue
        # вмешалась другая длинная остановка — первый рабочий день слишком далеко
        if (post.index[0] - e).days > P['nur_max_gap_to_post']:
            continue
        # --- ПИК интейка в первые nur_peak_search_d сут (восстановление за простой) ---
        search = post[post.index <= post.index[0] + pd.Timedelta(days=P['nur_peak_search_d'])]
        peak_pos = int(np.argmax(search.values))
        peak_val = float(search.values[peak_pos])
        if pd.notna(pre) and pre > 0:
            if peak_val < pre - P['nur_peak_tol_bar']:
                continue          # интейк не поднялся выше доостановочного — не НУР
        else:
            # нет данных «до» — fallback: явное снижение в первые N сут
            fb = min(P['nur_fallback_days'], len(post) - 1)
            if post.iloc[0] - post.iloc[fb] < P['nur_min_drop_bar']:
                continue
        # --- снижение ОТ ПИКА: тянем, пока ставятся новые минимумы ---
        decl = post.iloc[peak_pos:]
        days = list(decl.index); vals = list(decl.values)
        end_i = 0
        if getattr(ctx, 'cyclic', False):
            # ЦИКЛИЧЕСКАЯ: НУР = только КРУТАЯ фаза; конец при выполаживании спада
            # (дальше пологий «условно стабильный» режим, в НУР не входит).
            slow = 0
            for k in range(1, len(days)):
                if (days[k] - days[0]).days > P['nur_max_d']: break
                if (vals[k - 1] - vals[k]) >= P['nur_steep_slope']:
                    end_i = k; slow = 0
                else:
                    slow += 1
                    if slow >= P['nur_rise_confirm_d']: break
        else:
            rmin = vals[0]; rise = 0
            for k in range(1, len(days)):
                if (days[k] - days[0]).days > P['nur_max_d']: break
                if vals[k] <= rmin + P['nur_rise_tol']:
                    rmin = min(rmin, vals[k]); end_i = k; rise = 0
                else:
                    rise += 1
                    if rise >= P['nur_rise_confirm_d']: break
        if end_i < 1: continue
        # монотонность снижения
        if end_i >= 3:
            pairs = [vals[k] - vals[k + 1] for k in range(end_i)]
            mono = sum(1 for x in pairs if x >= -P['nur_rise_tol']) / len(pairs)
            if mono < P['nur_monotone_ratio']:
                continue
        if vals[0] - vals[end_i] < P['nur_min_drop_bar']: continue
        st, en = days[0], days[end_i] + pd.Timedelta(hours=23)
        if (en - st) >= pd.Timedelta(days=P['nur_min_d']):
            out.append((st, en))
    return merge_iv(out, gap=pd.Timedelta(hours=12))


def det_periodic(ctx):
    """Периодическая работа = частые циклы стоп-старт. v9.5: считаем ПЕРЕХОДЫ
    частоты в стоп (freq>=порог -> <порог) ЛЮБОЙ длительности. v9.9: на скважинах
    с УСТОЙЧИВО периодическим режимом (стретч циклирования содержит >= per_strong_days
    сут плотного цикла count>=per_start_n) режим расширяется на ВЕСЬ смежный стретч
    циклирования (count>=1) — Ic_805/Vt_606/Vt_655 и т.п.; на прочих скважинах —
    прежняя пороговая логика (не раздуваем краткие всплески циклов на непериодич. фонде)."""
    P = ctx.P
    fv = pd.to_numeric(ctx.tele[F], errors='coerce') if F in ctx.tele else pd.Series(dtype=float)
    fv = fv.dropna()
    if len(fv) < 5:
        return []
    on = (fv >= P['stop_freq_hz']).astype(int)
    cross = (on.diff() == -1)              # переход в стоп
    onsets = fv.index[cross.values]
    if len(onsets) == 0:
        return []
    days = pd.date_range(ctx.t0.normalize(), ctx.t1.normalize(), freq='D')
    ss = pd.Series(1, index=pd.DatetimeIndex(onsets)).resample('1D').sum()
    cnt = ss.reindex(days, fill_value=0).rolling(P['per_window_d'], min_periods=1).sum()
    # стретчи циклирования (хоть какие-то циклы в окне: count>=1)
    active = (cnt >= 1).values; n = len(days)
    stretches = []; i = 0
    while i < n:
        if not active[i]:
            i += 1; continue
        j = i
        while j < n and active[j]:
            j += 1
        stretches.append((i, j)); i = j
    # устойчивый периодич. режим: существует стретч с >= per_strong_days сут count>=per_start_n
    qualifies = any((cnt.iloc[a:b] >= P['per_start_n']).sum() >= P['per_strong_days']
                    for a, b in stretches)
    if qualifies:
        out = []
        for a, b in stretches:
            if (cnt.iloc[a:b] >= P['per_start_n']).any():   # стретч с реальными кластерами цикла
                out.append((max(days[a] - pd.Timedelta(days=P['per_window_d'] - 1), ctx.t0),
                            days[b - 1]))
        return merge_iv(out, gap=pd.Timedelta(days=P['per_merge_gap_d']))
    # прежняя пороговая логика (вход >= per_start_n, держим пока >= per_keep_n)
    out, st = [], None
    for dts in days:
        c = cnt[dts]
        if st is None and c >= P['per_start_n']:
            st = dts - pd.Timedelta(days=P['per_window_d'] - 1)
        elif st is not None and c < P['per_keep_n']:
            out.append((max(st, ctx.t0), dts)); st = None
    if st is not None:
        out.append((max(st, ctx.t0), days[-1]))
    return merge_iv(out, gap=pd.Timedelta(days=P['per_merge_gap_d']))


def _trend_runs(series, min_run_d, total_thr, max_slope=None, sign=-1, tol=0.3):
    s = series.dropna()
    out = []
    if len(s) < 2: return out
    days = list(s.index); vals = s.values
    i = 0
    while i < len(days) - 1:
        j = i
        while j < len(days) - 1 and sign * (vals[j+1] - vals[j]) > -tol:
            j += 1
        if j > i:
            span_d = (days[j] - days[i]).days
            delta = sign * (vals[j] - vals[i])
            slope = delta / max(span_d, 1)
            if span_d >= min_run_d and delta >= total_thr and \
               (max_slope is None or slope <= max_slope):
                out.append((days[i], days[j], delta))
        i = max(j, i + 1)
    return out


def _rpl_model_decline(ctx, nur_iv=()):
    """Снижение Рпл по монотонному спаду модели Рпл (tr_reservoir_pressure, вне НУР)
    в НЕПРЕРЫВНОЙ работе (мало стоп-переходов) при СТАБИЛЬНОЙ частоте — истощение
    пласта внутри длинного рабочего сегмента (Vt_605 авг-ноя). Периодич. скважины
    отсекаются гейтом непрерывности (их спад Рпр — операционные циклы)."""
    P = ctx.P
    rp = ctx.tele.get('tr_reservoir_pressure')
    if rp is None:
        return []
    rp = rp.dropna(); rp = rp[rp.diff().fillna(1.0).abs() > 1e-9]
    rp = rp[~rp.index.to_series().apply(lambda t: in_any(t, nur_iv))]
    if len(rp) < 2:
        return []
    f = ctx.wd[F]
    fv = pd.to_numeric(ctx.tele[F], errors='coerce').dropna()
    on = (fv >= P['stop_freq_hz']).astype(int); cross = (on.diff() == -1)
    onsets = pd.DatetimeIndex(fv.index[cross.values])
    days = list(rp.index); vals = list(rp.values); out = []; i = 0
    while i < len(days) - 1:
        if vals[i + 1] - vals[i] > P['rpl_model_tol']:
            i += 1; continue
        j = i
        while j < len(days) - 1:
            g = (days[j + 1] - days[j]).days
            if g < 1 or g > P['rpl_model_max_gap_d']:
                break
            if vals[j + 1] - vals[j] > P['rpl_model_tol']:
                break
            j += 1
        net = vals[i] - vals[j]; dur = (days[j] - days[i]).days
        if j > i and net >= P['rpl_model_min_bar'] and dur >= P['rpl_model_min_d']:
            seg = f[(f.index >= days[i]) & (f.index <= days[j])].dropna()
            dfr = (seg.iloc[-max(1, len(seg)//3):].median() - seg.iloc[:max(1, len(seg)//3)].median()) if len(seg) >= 3 else 0.0
            cyc = ((onsets >= days[i]) & (onsets <= days[j])).sum() / max(dur, 1) * 14
            if abs(dfr) <= P['rpl_model_fstab_hz'] and cyc < P['rpl_model_cyc_max']:
                out.append((days[i], days[j] + pd.Timedelta(hours=23)))
        i = max(j, i + 1)
    return merge_iv(out)


def det_snizh_rpl(ctx, nur_iv, gdi_iv, rptch_iv=()):
    """Снижение Рпл — объединение трёх критериев (вне НУР/ГДИ/РПТЧ):
    А) непрерывный trend-run ≥2 сут, ≥2 бар, скорость ≤2 бар/сут;
    Б) скользящее окно 14 сут: падение сглаж. Рпр ≥3 бар при |Δчастоты|≤2 Гц;
    В) долгосрочный тренд в рамках одного рабочего сегмента:
       падение сглаж. Рпр (MA15) ≥4 бар за 45-суточное окно."""
    P = ctx.P
    if getattr(ctx, 'cyclic', False):
        env = ctx.rpr_envelope()
        _env = ([(s, e + pd.Timedelta(hours=23))
                 for s, e in _env_runs(env, -1, P['rpl_env_min_bar'], P['rpl_env_tol'])]
                if len(env) >= 3 else [])
        # v9.9: + спад МОДЕЛИ Рпл в НЕПРЕРЫВНОЙ работе при стабильной частоте —
        # истощение внутри длинного сегмента, невидимое межцикловой огибающей (Vt_605).
        _cont = _rpl_model_decline(ctx, nur_iv)
        return merge_iv(_env + _cont)
    ip = ctx.wd[IP].rolling(3, min_periods=2).mean()
    f  = ctx.wd[F]
    out = []

    # А: trend-runs
    runs = _trend_runs(ip, P['snizh_run_d'], P['snizh_total_bar'],
                       max_slope=P['snizh_max_slope'], sign=-1, tol=P['snizh_tol'])
    for s, e, d in runs:
        if in_any(s, nur_iv) or in_any(e, nur_iv): continue
        if in_any(s, gdi_iv): continue
        fseg = f[(f.index >= s) & (f.index <= e)].dropna()
        if len(fseg) >= 2 and abs(fseg.iloc[-1] - fseg.iloc[0]) > P['snizh_max_dfreq']:
            continue
        out.append((s, e + pd.Timedelta(hours=23)))

    # Б: скользящее окно
    W = P['snizh_win_d']
    dip = ip - ip.shift(W); dfr = f - f.shift(W)
    flag = pd.Series(False, index=ctx.days)
    for d in ctx.days:
        if pd.isna(dip.get(d)) or dip[d] > -P['snizh_win_drop']: continue
        if pd.isna(dfr.get(d)) or abs(dfr[d]) > P['snizh_max_dfreq']: continue
        if in_any(d, nur_iv) or in_any(d, rptch_iv): continue
        # Фильтр «единого скачка»: если одно суточное изменение Рпр
        # составляет > snizh_step_ratio доли всего падения за окно —
        # это скорее артефакт остановки, а не плавный тренд Рпл
        win_start = d - pd.Timedelta(days=W)
        ip_win = ip[(ip.index >= win_start) & (ip.index <= d)].dropna()
        if len(ip_win) >= P['snizh_step_min_pts']:
            total_drop = ip_win.iloc[0] - ip_win.iloc[-1]
            if total_drop > 0:
                max_step = ip_win.diff().abs().dropna().max()
                if max_step / total_drop > P['snizh_step_ratio']:
                    continue   # единый скачок — пропускаем
        flag[d] = True
    out += _flag_to_iv(flag)

    # В: долгосрочный тренд в ESP-сегменте (ловит медленный многомесячный тренд)
    W_seg = P['snizh_seg_win_d']
    drop_seg = P['snizh_seg_drop_bar']
    for seg_s, seg_e in ctx.work_segments():
        seg_ip = ip[(ip.index >= seg_s.normalize()) & (ip.index <= seg_e.normalize())].dropna()
        if len(seg_ip) < P['snizh_seg_min_pts']: continue
        # MA15 для шумоподавления, затем 45-суточное изменение
        sm = seg_ip.rolling(15, min_periods=7).mean()
        sm_drop = sm - sm.shift(W_seg)
        flag_c = pd.Series(False, index=ctx.days)
        for d, v in sm_drop.dropna().items():
            if v > -drop_seg: continue
            # Критерий C — долгосрочный тренд: РПТЧ не фильтруем
            # (медленный спад Рпл виден поверх осцилляций частоты)
            if in_any(d, nur_iv): continue
            if d in flag_c.index:
                flag_c[d] = True
        out += _flag_to_iv(flag_c)

    res = merge_iv(out, gap=pd.Timedelta(days=3))
    res = subtract_iv(res, nur_iv)   # НУР и Снижение Рпл не должны накладываться
    return res


def det_rost_rpl(ctx, uvch_iv, nur_iv):
    if getattr(ctx, 'cyclic', False):
        # Рост Рпл ТОЛЬКО ВНУТРИ рабочих сегментов (не через остановки): устойчивый
        # рост Рпр в пределах одного непрерывного интервала работы. Соединять
        # медианы сегментов через остановки (огибающая) для РОСТА нельзя —
        # это даёт ложный рост (напр. Ya_357, где внутри сегментов Рпр только падает).
        ip = ctx.wd[IP].dropna()
        P = ctx.P; out = []
        for s2, e2 in ctx.work_segments():
            seg = ip[(ip.index >= s2.normalize()) & (ip.index <= e2.normalize())]
            seg = seg[~seg.index.to_series().apply(lambda t: in_any(t, nur_iv))]  # вне НУР (восстановление != рост Рпл)
            seg = seg.rolling(3, min_periods=1).mean().dropna()
            if len(seg) < P['rost_seg_min_d']:
                continue
            k = max(1, len(seg) // 3)
            # НЕТТО рост сегмента (конец выше начала), а не локальные подъёмы хвоста
            # восстановления -> реальный рост Рпл при работе (Ya_357/Ya_289 -> 0)
            if seg.iloc[-k:].median() - seg.iloc[:k].median() >= P['rost_seg_rise_bar']:
                out.append((seg.index[0], seg.index[-1] + pd.Timedelta(hours=23)))
        return merge_iv(out)
    """Рост Рпл — МОНОТОННЫЙ рост пластового давления. v7:
      • Вместо прежнего фильтра «не начинать в первые N сут после крупной
        остановки» применяется критерий монотонности: ищем максимальные
        монотонно-возрастающие прогоны точек Рпл (каждый шаг не падает больше
        rost_mono_tol; интервал между точками <= rost_max_gap_d).
      • Прогон засчитывается, если содержит >= rost_min_steps восходящих шагов
        (>=3 точки) И суммарный рост >= rost_rise_bar. Одиночный скачок
        (напр. возврат давления после остановки) монотонным прогоном не является.
      • Доп. фильтры сохранены: Рпр (интейк) не должен сильно падать; начало вне НУР."""
    P = ctx.P
    rp = ctx.tele.get('tr_reservoir_pressure')
    if rp is None:
        return []
    rp = rp.dropna()
    rp = rp[rp.diff().fillna(1.0).abs() > 1e-9]   # только точки изменения Рпл
    # v9.9: исключаем Рпл-точки внутри НУР — восстановление давления после
    # остановки/НУР не пластовый рост (осреднение Рпл с НУР даёт ложный рост, Ic_370).
    rp = rp[~rp.index.to_series().apply(lambda t: in_any(t, nur_iv))]
    if len(rp) < 2:
        return []
    ip = ctx.wd[IP].rolling(3, min_periods=2).mean()
    days = list(rp.index); vals = list(rp.values)
    out = []
    i = 0
    while i < len(days) - 1:
        # Прогон начинается только с восходящего шага
        if vals[i + 1] - vals[i] < P['rost_mono_tol']:
            i += 1; continue
        j = i; steps = 0
        while j < len(days) - 1:
            gap = (days[j + 1] - days[j]).days
            if gap < 1 or gap > P['rost_max_gap_d']:
                break
            if vals[j + 1] - vals[j] < -P['rost_mono_tol']:
                break                      # просадка > tol → конец монотонного прогона
            if vals[j + 1] - vals[j] > P['rost_max_step_bar']:
                break                      # нефизичный скачок (мусор датчика) → конец прогона
            if vals[j + 1] - vals[j] >= P['rost_mono_tol']:
                steps += 1                 # явный восходящий шаг
            j += 1
        net = vals[j] - vals[i]
        if j > i and steps >= P['rost_min_steps'] and net >= P['rost_rise_bar']:
            s_ep, e_ep = days[i], days[j]
            # Критерий = монотонность Рпл. Прежний veto по падению Рпр снят:
            # рост Рпл при снижении Рпр (интейка) физически согласован.
            if not in_any(s_ep, nur_iv):
                out.append((s_ep, e_ep))
        i = max(j, i + 1)
    return merge_iv(out)


def det_wcut_rise(ctx):
    P = ctx.P
    wc = ctx.wd.get(WC)
    if wc is None: return []
    sm = wc.rolling(P['wcut_window_d'], min_periods=5).mean()
    d = sm - sm.shift(P['wcut_window_d'])
    return _flag_to_iv(d > P['wcut_rise_pp'])


def _env_runs(env, sign, min_bar, tol):
    """Монотонные прогоны огибающей Рпр (sign=+1 рост / -1 снижение)."""
    vals = list(env.values); idx = list(env.index); out = []; i = 0
    while i < len(vals) - 1:
        j = i
        while j < len(vals) - 1 and sign * (vals[j + 1] - vals[j]) >= -tol:
            j += 1
        if j > i and sign * (vals[j] - vals[i]) >= min_bar:
            out.append((idx[i], idx[j]))
        i = max(j, i + 1)
    return out


def det_kprod_rise(ctx, opz_iv=(), nur_iv=()):
    """Рост Кпрод — устойчивый РОСТ расч. Кпрод (зеркально Снижению). Реже и
    обычно крупнее, поэтому порог импульса выше (kprod_rise_pulse)."""
    P = ctx.P
    K = getattr(ctx, 'kprod', pd.Series(dtype=float))
    if getattr(ctx, 'cyclic', False):
        opz_iv = [(ctx.t0, ctx.t1)]
    if len(K) < 5 or not opz_iv:
        return []
    out = []
    # Рост Кпрод ТОЛЬКО ВНУТРИ рабочих сегментов (рост на восстановлении после
    # стопа через границу остановки — не считается).
    for s2, e2 in ctx.work_segments():
        Ks = K[(K.index >= s2.normalize()) & (K.index <= e2.normalize())]
        Ks = Ks[~Ks.index.to_series().apply(lambda t: in_any(t, nur_iv))]  # вне НУР (восстановление != рост Кпрод)
        Ks = Ks.rolling(3, min_periods=1).mean().dropna()
        if len(Ks) < P['kprod_min_d']:
            continue
        k = max(1, len(Ks) // 3)
        a = Ks.iloc[:k].median(); b = Ks.iloc[-k:].median()
        # НЕТТО рост расч. Кпрод в сегменте (вне восстановления)
        if a > 0 and (b - a) / a >= P['kprod_rise_pulse']:
            out.append((Ks.index[0], Ks.index[-1]))
    return merge_iv(out, gap=pd.Timedelta(days=P['kprod_merge_gap_d']))


def _kprod_env_decl(ctx):
    """Нетто-изменение огибающей расч.Кпрод (медиана по рабочим сегментам) за жизнь.
    < 0 -> деградация продуктивности; ~0 / > 0 -> скважина не деградирует."""
    K = getattr(ctx, 'kprod', pd.Series(dtype=float))
    seg = []
    for s, e in ctx.work_segments():
        v = K[(K.index >= s) & (K.index <= e)]
        if len(v) >= 3:
            seg.append(v.median())
    if len(seg) < 3 or seg[0] <= 0:
        return 0.0
    return (seg[-1] - seg[0]) / seg[0]


def det_kprod_drop(ctx, opz_iv=(), nur_iv=()):
    """v9.3: Снижение Кпрод = импульсы падения РАСЧЁТНОГО Кпрод ВНУТРИ кластеров ОПЗ
    (opz_iv, независимый сигнал). Эксперт метит Кпрод как частые короткие спады именно в период
    повторных обработок/отказов (Ic_805, Ic_914). Вне осложнённого фонда отдельные
    дипы Кпрод эксперт не выделяет -> не флагаем (убирает фантомы на нормальных
    скважинах: Mc_1003, Vt_606, Vt_655-вне CF и т.д.)."""
    P = ctx.P
    K = getattr(ctx, 'kprod', pd.Series(dtype=float))
    # НЕциклическая: Снижение Кпрод = ТЕРМИНАЛЬНЫЙ монотонный спад расч.Кпрод
    # (падает и НЕ восстанавливается). Отличает реальную деградацию (Vt_3311,
    # Ic_370, Da_515) от шумовых отскоков; ОПЗ не требуется.
    if not getattr(ctx, 'cyclic', False):
        if len(K) < P['kprod_term_win']:
            return []
        Ks = K.rolling(7, min_periods=3).mean().dropna()
        win = P['kprod_term_win']; out = []; i = win
        while i < len(Ks):
            seg = Ks.iloc[i - win:i + 1]; d = seg.diff().dropna()
            fr = (d < 0).mean()
            tot = (seg.iloc[0] - seg.iloc[-1]) / seg.iloc[0] if seg.iloc[0] > 0 else 0
            if fr >= P['kprod_term_mono'] and tot >= P['kprod_term_drop']:
                endv = seg.iloc[-1]; after = Ks.iloc[i + 1:]
                if len(after) == 0 or after.max() <= endv + P['kprod_term_rec'] * (seg.iloc[0] - endv):
                    out.append((seg.index[0], seg.index[-1])); i += win; continue
            i += 1
        return merge_iv(out, gap=pd.Timedelta(days=P['kprod_merge_gap_d']))
    # Циклическая (Вариант B): детектируем по ВСЕЙ жизни. ОПЗ — НЕ определяющий, а
    # ПОДТВЕРЖДАЮЩИЙ фактор (учитывается в уверенности score_episode). Скважина может
    # деградировать без ОПЗ; задача — найти Снижение Кпрод из сигнала.
    opz_iv = [(ctx.t0, ctx.t1)]
    if len(K) < 5:
        return []
    Ks = K.rolling(3, min_periods=1).mean().dropna()
    idx = list(Ks.index); v = list(Ks.values)
    span = P['kprod_pulse_span']; drop = P['kprod_pulse_drop']
    flag = pd.Series(False, index=Ks.index)
    for i in range(len(v)):
        if not in_any(idx[i], opz_iv):
            continue
        for j in range(max(0, i - span), i):
            if v[j] > 0 and (v[j] - v[i]) / v[j] >= drop:
                flag[idx[i]] = True; break
    out = _flag_to_iv(flag)
    return merge_iv(out, gap=pd.Timedelta(days=P['kprod_pulse_gap']))


def det_degr(ctx, rost_iv):
    P = ctx.P
    qr = ctx.tele.get('tr_liquid_rate')
    if qr is None: return []
    qr = qr.dropna()
    qr = qr[qr.diff().fillna(1.0).abs() > 1e-9]
    f = ctx.wd[F]
    out = []
    for i in range(1, len(qr)):
        g = (qr.index[i] - qr.index[i-1]).days
        if g < 1 or g > P['degr_max_gap_d']: continue
        if qr.iloc[i-1] <= 0: continue
        if (qr.iloc[i-1] - qr.iloc[i]) / qr.iloc[i-1] * 100 < P['degr_drop_pct']:
            continue
        s, e = qr.index[i-1], qr.index[i]
        fs = f[(f.index >= s.normalize()) & (f.index <= e.normalize())].dropna()
        if len(fs) >= 2 and abs(fs.iloc[-1] - fs.iloc[0]) > P['degr_max_dfreq']:
            continue
        out.append((s, e))
    return merge_iv(out)


def det_sppv(ctx):
    P = ctx.P
    bd = ctx.tele.get(BD)
    if bd is None: return []
    bd = bd.dropna()
    daily = bd[bd > 0].resample('1D').sum()
    days = daily[daily > P['sppv_bdpv_min']].index
    if not len(days): return []
    out, st, prev = [], days[0], days[0]
    for d in days[1:]:
        if (d - prev).days > P['sppv_gap_d']:
            out.append((st, prev + pd.Timedelta(hours=23))); st = d
        prev = d
    out.append((st, prev + pd.Timedelta(hours=23)))
    # v9.8.1: продлить каждый СППВ-интервал до ближайших ДЛИТЕЛЬНЫХ остановок
    # (>= 1 сут) — заполнить рабочий участок между такими остановками.
    lstops = [(ss, ee) for ss, ee in ctx.stops if (ee - ss) >= pd.Timedelta(days=1)]
    bounds = [ctx.t0] + [ee for _, ee in lstops] + [ss for ss, _ in lstops] + [ctx.t1]
    ext = []
    for s0, e0 in out:
        lo = max([b for b in bounds if b <= s0], default=ctx.t0)
        hi = min([b for b in bounds if b >= e0], default=ctx.t1)
        ext.append((lo, hi))
    return merge_iv(ext)


def _flag_to_iv(flag):
    f = flag.fillna(False)
    out, st, prev = [], None, None
    for d, v in f.items():
        if v:
            if st is None: st = d
            prev = d
        else:
            if st is not None and prev is not None and (d - prev).days > 1:
                out.append((st, prev + pd.Timedelta(hours=23))); st = None
    if st is not None:
        out.append((st, prev + pd.Timedelta(hours=23)))
    return out


# ──────────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════
# Сигнатурный разделитель НУР <-> Снижение Рпл (используется для УВЕРЕННОСТИ
# и совещательной метки; детекторы не меняет).
# ══════════════════════════════════════════════════════════════════════════
def _sig_clip01(x):
    return float(max(0.0, min(1.0, x)))


def sig_features(ctx, start, end):
    """Признаки интервала (0..1, ближе к 1 = больше похоже на НУР)."""
    S = SIG
    ipd = ctx.wd[IP].dropna()
    s_n, e_n = start.normalize(), end.normalize()
    seg = ipd[(ipd.index >= s_n) & (ipd.index <= e_n)]
    seg = seg[seg > 0]
    f = {}
    # 1) близость старта к концу недавней остановки
    gap = np.inf
    for ss, se in ctx.stops:
        if se <= start:
            gap = min(gap, (start - se).total_seconds() / 86400.0)
    f['poststop'] = _sig_clip01(np.exp(-gap / S['tau_gap_d'])) if np.isfinite(gap) else 0.0
    # 2) пик Рпр после пуска выше доостановочного уровня
    pre = ctx.pre_stop_ip_mean(start)
    if len(seg) >= 3:
        head = seg[seg.index <= seg.index[0] + pd.Timedelta(days=S['peak_search'])]
        peak = head.max(); peak_pos = int(np.argmax(head.values))
        rose_above = (pd.notna(pre) and peak >= pre - 1.0)
        f['peak'] = _sig_clip01(0.6 * float(rose_above) + 0.4 * float(peak_pos >= 1))
    else:
        f['peak'] = 0.0
    # 3) скорость падения (быстро=НУР)
    if len(seg) >= 3:
        dur = max((seg.index[-1] - seg.index[0]).days, 1)
        drop = seg.iloc[:3].mean() - seg.iloc[-3:].mean()
        f['speed'] = _sig_clip01((drop / dur) / (2 * S['fast_barday']))
    else:
        f['speed'] = 0.5
    # 4) длительность (короче=НУР)
    dur_d = max((e_n - s_n).days, 1)
    f['dur'] = _sig_clip01(1.0 - (dur_d - S['short_d']) / (3 * S['short_d']))
    # 5) тренд Qж: растёт=НУР, падает=Снижение Рпл
    ql = ctx.wd[QL].dropna() if QL in ctx.wd else pd.Series(dtype=float)
    qseg = ql[(ql.index >= s_n) & (ql.index <= e_n)]; qseg = qseg[qseg > 0]
    if len(qseg) >= 4:
        sl = np.polyfit(np.arange(len(qseg)), qseg.values, 1)[0]
        f['qliq'] = _sig_clip01(0.5 + (sl / (qseg.mean() or 1.0)) * 30.0)
    else:
        f['qliq'] = 0.5
    return f


def sig_score(ctx, start, end):
    S = SIG; f = sig_features(ctx, start, end)
    wmap = dict(poststop=S['w_poststop'], peak=S['w_peak'], speed=S['w_speed'],
               dur=S['w_dur'], qliq=S['w_qliq'])
    wsum = sum(wmap.values())
    nur = sum(wmap[k] * f[k] for k in wmap) / wsum
    sniz = sum(wmap[k] * (1.0 - f[k]) for k in wmap) / wsum
    label = 'НУР' if nur >= sniz else 'Снижение Рпл'
    margin = abs(nur - sniz)
    tier = 'high' if margin >= S['margin_high'] else ('medium' if margin >= S['margin_low'] else 'low')
    return dict(label=label, margin=round(margin, 3), tier=tier,
                nur=round(nur, 3), sniz=round(sniz, 3))


def score_episode(ctx, ep_type, start, end):
    """
    Сигнальная модель confidence.

    Правило уже сработало — значит базовые условия (gate, drop, slope) пройдены.
    score_episode проверяет ТОЛЬКО дополнительные подтверждающие сигналы:
      • «shape» — чистота паттерна Рпр/частоты (монотонность, отсутствие скачков, тренд)
      • «ql_*»  — подтверждение через дебит жидкости (Qж)

    Уровни:
      high   — shape-сигналы не противоречат И Qж подтверждает
      medium — shape ОК, но Qж недоступен / нейтрален
      low    — хотя бы один shape-сигнал ПРОТИВОРЕЧИТ (подозрение на артефакт)

    Возвращает:
      score  : float 0–1
      tier   : 'high' | 'medium' | 'low'
      signals: dict[str, bool | None]  (None = нет данных)
    """
    P = ctx.P
    s_n, e_n = start.normalize(), end.normalize()

    def _w(col):
        if col not in ctx.wd: return pd.Series(dtype=float)
        return ctx.wd[col][(ctx.wd.index >= s_n) & (ctx.wd.index <= e_n)].dropna()

    def _fw():
        fw = ctx.tele[F][ctx.wmask.values]
        return fw[(fw.index >= start) & (fw.index <= end)].resample('1D').mean().dropna()

    def _lin_slope(s):
        s = s.dropna()
        if len(s) < 3: return None
        return float(np.polyfit(np.arange(len(s)), s.values, 1)[0])

    signals = {}   # signal_name → bool | None

    # ─── НУР ─────────────────────────────────────────────────────────────
    if ep_type == 'НУР':
        ip = _w(IP)
        # shape: Рпр снижается плавно (не резкими скачками)
        if len(ip) >= 3:
            diffs = [ip.iloc[k] - ip.iloc[k+1] for k in range(len(ip)-1)]
            mono = sum(1 for d in diffs if d >= -P['nur_end_slope']) / len(diffs)
            # smooth = монотонная доля высокая, но не обязательно 100%
            signals['ip_smooth']   = mono >= 0.55   # смягчён vs nur_monotone_ratio
            total_drop = ip.iloc[0] - ip.iloc[-1]
            max_step = ip.diff().abs().dropna().max() if len(ip) > 1 else 0
            # step_ok = нет единого скачка съедающего >70% снижения
            signals['ip_no_spike'] = (max_step / total_drop <= 0.70) if total_drop > 0.5 else True
        else:
            signals['ip_smooth']   = None
            signals['ip_no_spike'] = None
        # Qж: дебит растёт при восстановлении скважины после останова
        ql = _w(QL)
        slope = _lin_slope(ql)
        signals['ql_recovers'] = None if slope is None else slope > 0

    # ─── РПТЧ ────────────────────────────────────────────────────────────
    elif ep_type == 'РПТЧ':
        fd = _fw()
        if len(fd) < 5:
            signals['freq_data'] = None
        else:
            # round_hz: хотя бы половина суток — целые (или полуцелые) уставки Гц
            remainder = fd.apply(lambda x: min(x % 1, 1 - x % 1))
            signals['round_hz'] = (remainder < P['rptch_round_tol']).mean() >= 0.40  # смягчён
            # Qж осциллирует вместе с частотой (CV Qж > 3%)
        ql = _w(QL)
        if len(ql) >= 5 and ql.mean() > 0:
            signals['ql_oscillates'] = ql.std() / ql.mean() > 0.03
        else:
            signals['ql_oscillates'] = None

    # ─── УВЧ ─────────────────────────────────────────────────────────────
    elif ep_type == 'УВЧ':
        f = _w(F)
        if len(f) >= 2:
            slope = _lin_slope(f)
            # shape: устойчивый рост (не разовый скачок вниз-вверх)
            signals['freq_trend_up'] = None if slope is None else slope > 0
            net = f.iloc[-1] - f.iloc[0]
            signals['freq_net_ok']   = net >= P['uvch_rise_hz']
        else:
            signals['freq_trend_up'] = None
            signals['freq_net_ok']   = None
        # Qж растёт — производство увеличивается при росте частоты
        ql = _w(QL)
        slope_ql = _lin_slope(ql)
        signals['ql_rises'] = None if slope_ql is None else slope_ql > 0

    # ─── Снижение Рпл ────────────────────────────────────────────────────
    elif ep_type == 'Снижение Рпл':
        ip = _w(IP)
        f  = _w(F)
        # shape: частота стабильна (не снижение нагрузки оператором)
        if len(f) >= 2:
            signals['freq_stable'] = abs(f.iloc[-1] - f.iloc[0]) <= P['snizh_max_dfreq']
        else:
            signals['freq_stable'] = None
        # not_step: падение распределено во времени, не единый скачок
        if len(ip) >= P['snizh_step_min_pts']:
            total_drop = ip.iloc[0] - ip.iloc[-1]
            if total_drop > 0:
                max_step = ip.diff().abs().dropna().max()
                signals['ip_gradual'] = max_step / total_drop <= P['snizh_step_ratio']
            else:
                signals['ip_gradual'] = None
        else:
            signals['ip_gradual'] = None
        # Qж тоже снижается — главное подтверждение истощения пласта
        ql = _w(QL)
        if len(ql) >= 5 and ql.mean() > 0:
            ql_drop_frac = (ql.iloc[:max(1,len(ql)//3)].mean() -
                            ql.iloc[-max(1,len(ql)//3):].mean()) / ql.mean()
            signals['ql_declining'] = ql_drop_frac > 0.04
        else:
            signals['ql_declining'] = None

    # ─── ГДИ ─────────────────────────────────────────────────────────────
    elif ep_type == 'ГДИ':
        ip_stop = ctx.tele[IP][(ctx.tele.index >= start) & (ctx.tele.index <= end)].dropna()
        # shape: Рпр растёт во время остановки (КВД)
        if len(ip_stop) >= 2:
            signals['ip_kvd_rising'] = ip_stop.iloc[-1] > ip_stop.iloc[0]
        else:
            signals['ip_kvd_rising'] = None
        # Qж = 0 во время остановки
        ql_raw = ctx.tele.get(QL)
        if ql_raw is not None:
            ql_seg = ql_raw[(ql_raw.index >= start) & (ql_raw.index <= end)].dropna()
            signals['ql_zero'] = len(ql_seg) == 0 or ql_seg.mean() < 0.5
        else:
            signals['ql_zero'] = None

    # ─── Периодическая работа ────────────────────────────────────────────
    elif ep_type == 'Периодическая работа':
        stop_times = [ss for ss, _ in ctx.stops if start <= ss <= end]
        if len(stop_times) >= 3:
            ivls = [(stop_times[k+1]-stop_times[k]).total_seconds()/3600
                    for k in range(len(stop_times)-1)]
            mean_i = float(np.mean(ivls))
            cv = float(np.std(ivls)) / mean_i if mean_i > 0 else 1
            signals['rhythm_ok'] = cv <= 0.6   # интервалы относительно регулярны
        else:
            signals['rhythm_ok'] = None
        ql = _w(QL)
        if len(ql) >= 7 and ql.mean() > 0:
            signals['ql_cyclic'] = ql.std() / ql.mean() > 0.06
        else:
            signals['ql_cyclic'] = None

    # ─── Снижение Кпрод ──────────────────────────────────────────────────
    elif ep_type == 'Снижение Кпрод':
        # высокая уверенность ТОЛЬКО при подтверждении падением дебита жидкости
        # (Ic_367 «шум Рпр» без падения Qж -> medium; Ic_914 реальный спад -> high)
        ql = _w(QL)
        if len(ql) >= 4 and ql.mean() > 0:
            t = max(1, len(ql) // 3)
            drop = (ql.iloc[:t].mean() - ql.iloc[-t:].mean()) / ql.mean()
            signals['ql_confirms'] = drop > 0.05
        else:
            signals['ql_confirms'] = None
        # ОПЗ — ПОДТВЕРЖДАЮЩИЙ фактор (не определяющий): эпизод в кластере ОПЗ -> выше
        # уверенность; отсутствие ОПЗ не понижает (подтверждающая группа ql_*).
        try:
            _opzc = det_opz_clusters(ctx)
            signals['ql_opz'] = (bool(in_any(start, _opzc) or in_any(end, _opzc)) if _opzc else None)
        except Exception:
            signals['ql_opz'] = None

    elif ep_type == 'ВГФ':
        return _score_vgf(ctx, start, end)
    elif ep_type in ('Рост ГФ', 'Снижение ГФ'):
        return _score_gf_trend(ctx, start, end)

    else:
        return dict(score=1.0, tier='high', signals={})

    # ─── Tiering ─────────────────────────────────────────────────────────
    # Философия: правило уже сработало. Ищем противоречия (→ LOW)
    # или подтверждение Qж (→ HIGH).
    ql_keys   = {k for k in signals if k.startswith('ql_')}
    main_keys = {k for k in signals if k not in ql_keys}

    # np.bool_ совместимость: используем == вместо is
    def _is_false(v): return v is not None and v == False
    def _is_true(v):  return v is not None and v == True

    main_false   = sum(1 for k in main_keys if _is_false(signals[k]))
    ql_confirmed = any(_is_true(signals.get(k)) for k in ql_keys)

    if main_false > 0:
        tier = 'low'      # хотя бы один shape-сигнал ПРОТИВОРЕЧИТ
    elif ql_confirmed:
        tier = 'high'     # shape ОК + Qж подтверждает
    else:
        tier = 'medium'   # shape ОК, Qж недоступен или нейтрален

    def _b(v): return 1.0 if _is_true(v) else (0.0 if _is_false(v) else 0.5)
    score = round(float(np.mean([_b(v) for v in signals.values()])) if signals else 0.5, 3)
    return dict(score=score, tier=tier, signals={k: signals[k] for k in sorted(signals)})


# ─────────────────────────────────────────────────────────────────────────
def det_opz_clusters(ctx):
    """Кластеры ОПЗ (НЕзависимый событийный сигнал «скважину повторно обрабатывают»): >= cf_min_opz ОПЗ в окне
    cf_win_d суток. Кластер обработок = «остановка-обработка-запуск» повторяется
    (экспертный признак осложнённого фонда). Одиночные/редкие ОПЗ (рутинные) не в счёт.
    Калибровка: точно ловит ручные CF (Ic_805/Ic_914/Vt_4401)."""
    P = ctx.P
    if 'opz_ids' not in ctx.tele:
        return []
    sub = ctx.tele['opz_ids'].dropna()
    seen = {}
    for t, o in sub.items():
        for pid in str(o).replace('|', ',').split(','):
            pid = pid.strip()
            if pid and pid != 'nan':
                seen.setdefault(pid, t)
    dts = sorted(set(pd.Timestamp(x).normalize() for x in seen.values()))
    if len(dts) < P['cf_min_opz']:
        return []
    win = pd.Timedelta(days=P['cf_win_d']); ext = pd.Timedelta(days=P['cf_ext_d'])
    mg = pd.Timedelta(days=P['cf_merge_gap_d'])
    out = []
    for t in dts:
        cnt = sum(1 for x in dts if (t - win) <= x <= t)
        if cnt >= P['cf_min_opz']:
            s_, e_ = t - ext, t + ext
            if out and s_ <= out[-1][1] + mg:   # объединяем кластеры через разрывы
                out[-1] = (out[-1][0], max(out[-1][1], e_))
            else:
                out.append((s_, e_))
    # ограничить рамками телеметрии
    out = [(max(s_, ctx.t0), min(e_, ctx.t1)) for s_, e_ in out]
    return merge_iv(out)


def det_complicated_fund(ctx, kprod_iv):
    """Осложнённый фонд ВЫВОДИТСЯ из Кпрод: период, где Снижение Кпрод случается
    ПОВТОРНО (>= cf_min_kprod эпизодов в скользящем окне cf_kprod_win сут).
    Соответствует словам эксперта: «Кпрод снижался несколько раз за месяц»."""
    P = ctx.P
    iv = list(kprod_iv)
    if len(iv) < P['cf_min_kprod']:
        return []
    starts = pd.DatetimeIndex(sorted(s for s, _ in iv))
    win = pd.Timedelta(days=P['cf_kprod_win']); ext = pd.Timedelta(days=P['cf_ext_d'])
    out = []
    for t in starts:
        cnt = sum(1 for x in starts if (t - win) <= x <= t)
        if cnt >= P['cf_min_kprod']:
            # охватить кластер Кпрод-эпизодов
            grp = [(s_, e_) for s_, e_ in iv if (t - win) <= s_ <= t]
            s0 = min(s_ for s_, _ in grp) - ext; e0 = max(e_ for _, e_ in grp) + ext
            if out and s0 <= out[-1][1]:
                out[-1] = (out[-1][0], max(out[-1][1], e0))
            else:
                out.append((s0, e0))
    return merge_iv([(max(s_, ctx.t0), min(e_, ctx.t1)) for s_, e_ in out])


def _glf_daily(ctx, win=14):
    """Сглаженный ГЖФ: обрезка выбросов (p5..p95), дневная медиана, rolling-медиана.
    Возвращает (series, n_сырых_точек)."""
    s = ctx.tele.get(GLF)
    if s is None:
        return pd.Series(dtype=float), 0
    s = pd.to_numeric(s, errors='coerce').dropna(); s = s[s > 0]
    npts = len(s)
    if npts < 5:
        return pd.Series(dtype=float), npts
    lo, hi = s.quantile(0.05), s.quantile(0.95)
    s = s[(s >= lo) & (s <= hi)]
    return s.resample('1D').median().rolling(win, min_periods=3).median(), npts


def _bridge_runs(flag, bridge, min_d):
    out = []; st = None; last = None
    for d, v in flag.items():
        if v:
            if st is None: st = d
            last = d
        elif st is not None and (d - last).days > bridge:
            out.append((st, last)); st = None
    if st is not None:
        out.append((st, last))
    return [(s, e + pd.Timedelta(hours=23)) for s, e in out if (e - s).days >= min_d]


def _glf_trend_runs(g, sign, frac, min_d, tol_frac=0.15):
    g = g.dropna()
    if len(g) < 3:
        return []
    vals = list(g.values); idx = list(g.index); out = []; i = 0
    while i < len(vals) - 1:
        j = i
        while j < len(vals) - 1:
            base = vals[i] if vals[i] > 0 else 1.0
            if sign * (vals[j + 1] - vals[j]) / base >= -tol_frac:
                j += 1
            else:
                break
        if j > i and vals[i] > 0:
            net = sign * (vals[j] - vals[i]) / vals[i]
            if net >= frac and (idx[j] - idx[i]).days >= min_d:
                out.append((idx[i], idx[j] + pd.Timedelta(hours=23)))
        i = max(j, i + 1)
    return merge_iv(out)


def det_vgf(ctx):
    """ВГФ — устойчиво повышенный сглаженный ГЖФ (>= порога), сплошным эпизодом с
    заполнением разрывов. Уровень уверенности (подтверждение Qж/Рпр/нестабильность,
    либо разрежённость) считается в score_episode."""
    P = ctx.P
    g, npts = _glf_daily(ctx)
    if g.dropna().empty:
        return []
    grid = pd.date_range(g.dropna().index.min(), g.dropna().index.max(), freq='D')
    gd = g.reindex(grid).ffill(limit=30)
    flag = gd >= P['vgf_glf_thr']
    return _bridge_runs(flag, P['vgf_bridge_d'], P['vgf_min_d'])


def det_gf_rise(ctx):
    g, _ = _glf_daily(ctx)
    return _glf_trend_runs(g, +1, ctx.P['gf_trend_frac'], ctx.P['gf_trend_min_d'])


def det_gf_drop(ctx):
    g, _ = _glf_daily(ctx)
    return _glf_trend_runs(g, -1, ctx.P['gf_trend_frac'], ctx.P['gf_trend_min_d'])


def _glf_episode_pts(ctx, start, end):
    raw = ctx.tele.get(GLF)
    if raw is None:
        return pd.Series(dtype=float)
    raw = pd.to_numeric(raw, errors='coerce').dropna(); raw = raw[raw > 0]
    return raw[(raw.index >= start.normalize()) & (raw.index <= end.normalize())]


def _score_vgf(ctx, start, end):
    P = ctx.P
    s_n, e_n = start.normalize(), end.normalize()
    raw = _glf_episode_pts(ctx, start, end)
    sparse = len(raw) < P['glf_min_pts']
    noisy = (raw.std() / raw.mean() > 1.5) if (len(raw) > 3 and raw.mean() > 0) else False
    # Qж падает
    ql = pd.to_numeric(ctx.tele.get(QL), errors='coerce').dropna() if QL in ctx.tele else pd.Series(dtype=float)
    ql = ql[(ql.index >= s_n) & (ql.index <= e_n)]; ql = ql[ql > 0]
    qdrop = False
    if len(ql) >= 6:
        k = max(1, len(ql) // 3)
        a = ql.iloc[:k].median()
        qdrop = a > 0 and (a - ql.iloc[-k:].median()) / a >= P['vgf_qdrop_frac']
    # Рпр растёт
    ip = ctx.wd[IP][(ctx.wd.index >= s_n) & (ctx.wd.index <= e_n)].dropna() if IP in ctx.wd else pd.Series(dtype=float)
    iprise = (len(ip) >= 4 and ip.iloc[-1] - ip.iloc[0] > 3)
    # нестабильность (частые остановки в эпизоде)
    span_d = max((e_n - s_n).days, 1)
    stops_in = sum(1 for ss, ee in ctx.stops if s_n <= ss <= e_n)
    unstable = (stops_in / span_d * 30.0) >= P['vgf_stop_rate']
    confirms = int(qdrop) + int(iprise) + int(unstable)
    g_med = float(raw.median()) if len(raw) else 0.0
    if sparse or noisy or g_med < P['vgf_glf_thr']:
        tier = 'low'      # разрежённость/шум или ГЖФ ниже порога (стоп-управляемый ВГФ)
    elif qdrop and (iprise or unstable):
        tier = 'high'
    else:
        tier = 'medium'
    return dict(score=round(min(0.4 + 0.2 * confirms, 1.0), 2), tier=tier,
                signals=dict(qdrop=bool(qdrop), iprise=bool(iprise), unstable=bool(unstable),
                             sparse=bool(sparse), noisy=bool(noisy)))


def _score_gf_trend(ctx, start, end):
    raw = _glf_episode_pts(ctx, start, end)
    tier = 'low' if len(raw) < ctx.P['glf_min_pts'] else 'medium'
    return dict(score=0.6 if tier == 'medium' else 0.3, tier=tier,
                signals=dict(n_glf=int(len(raw))))


def label_well(tele, vsp, P=PARAMS, gdi_events=None):
    ctx = WellCtx(tele, vsp, P)
    res = {}
    res['Остановка'] = det_stop(ctx)
    res['Работа']    = det_work(ctx)
    res['ГДИ']       = det_gdi(ctx, gdi_events)
    res['РПТЧ']      = det_rptch(ctx)
    res['УВЧ']       = det_uvch(ctx, res['РПТЧ'])
    res['НУР']       = det_nur(ctx)
    res['Периодическая работа'] = det_periodic(ctx)
    res['Снижение Рпл']  = det_snizh_rpl(ctx, res['НУР'], res['ГДИ'], res['РПТЧ'])
    res['Рост Рпл']      = det_rost_rpl(ctx, res['УВЧ'], res['НУР'])
    res['Рост обводненности'] = det_wcut_rise(ctx)
    _opz = det_opz_clusters(ctx)
    res['Снижение Кпрод']    = det_kprod_drop(ctx, _opz, res['НУР'])
    # v9.9 (Вариант B): Снижение Кпрод только при СТАБИЛЬНОЙ частоте. Любое крупное
    # изменение частоты (рост ИЛИ падение) делает скачок расч.Кпрод операционным
    # (меняются отборы/депрессия), а не деградацией. Универсально (Vt_4401/Vt_605).
    if getattr(ctx, 'cyclic', False) and res['Снижение Кпрод']:
        _f = ctx.wd[F].dropna(); _kept = []
        for _s, _e in res['Снижение Кпрод']:
            _seg = _f[(_f.index >= _s.normalize()) & (_f.index <= _e.normalize())]
            _dfr = 0.0
            if len(_seg) >= 3:
                _k = max(1, len(_seg) // 3)
                _dfr = float(_seg.iloc[-_k:].median() - _seg.iloc[:_k].median())
            if abs(_dfr) < P['kprod_freq_stable_hz']:
                _kept.append((_s, _e))
        res['Снижение Кпрод'] = _kept
    res['Рост Кпрод']        = det_kprod_rise(ctx, _opz, res['НУР'])
    res['Осложнённый фонд'] = det_complicated_fund(ctx, res['Снижение Кпрод'])
    res['Деградация ЭЦН']    = det_degr(ctx, res['Рост Рпл'])
    # v9.9: циклич. — Рост Рпл, целиком в Снижении Кпрод, есть деградация (Qж падает ->
    # депрессия падает -> интейк растёт), не пластовый рост. Перекрытие>=порога -> убрать.
    if getattr(ctx, 'cyclic', False) and res['Рост Рпл'] and res['Снижение Кпрод']:
        _kept = []
        for _rs, _re in res['Рост Рпл']:
            _span = (_re - _rs).total_seconds(); _ov = 0.0
            for _ks, _ke in res['Снижение Кпрод']:
                _d = (min(_re, _ke) - max(_rs, _ks)).total_seconds()
                if _d > 0: _ov += _d
            if _span <= 0 or _ov / _span < P['rost_kprod_overlap_max']:
                _kept.append((_rs, _re))
        res['Рост Рпл'] = _kept
    res['СППВ']      = det_sppv(ctx)
    res['ВГФ']       = det_vgf(ctx)
    # стоп-управляемый ВГФ (низкая уверенность): цикличная скв. с частыми
    # остановками и снижениями Кпрод — низ пласта не работает, газ идёт верхами
    # -> соли -> рост ГФ -> остановки для дегазации ЭЦН (Mc_1004/Mc_20414).
    _g_sd, _np_sd = _glf_daily(ctx)
    if (getattr(ctx, 'cyclic', False) and len(res.get('Снижение Кпрод', [])) >= 3
            and _np_sd >= P['glf_min_pts'] and not _g_sd.dropna().empty
            and float(_g_sd.median()) >= P['vgf_stop_glf_min']):
        _kp = res['Снижение Кпрод']
        _hull = (min(s for s, e in _kp), max(e for s, e in _kp))
        res['ВГФ'] = merge_iv(list(res['ВГФ']) + [_hull])
    res['Рост ГФ']   = det_gf_rise(ctx)
    res['Снижение ГФ'] = det_gf_drop(ctx)
    # v9: Снижение Рпл и Снижение Кпрод не пересекаются (только нециклич.; на
    # циклич. огибающая Рпл — фоновый межцикловый тренд, его не дробим Кпродом)
    if not getattr(ctx, 'cyclic', False):
        res['Снижение Рпл'] = subtract_iv(res['Снижение Рпл'], res['Снижение Кпрод'])
    # v9.9: нециклич. — Снижение Рпл, ПРИМЫКАЮЩЕЕ к Снижению Кпрод, есть продолжение
    # деградации (не истощение), ЕСЛИ интейк не вернулся на доснижения уровень И до Кпрод
    # было стабильное плато интейка. Тогда переносим интервал в Снижение Кпрод (Vt_3311).
    if not getattr(ctx, 'cyclic', False) and res['Снижение Кпрод'] and res['Снижение Рпл']:
        _ip = ctx.wd[IP].dropna(); _ip = _ip[_ip > 0]
        _gap = pd.Timedelta(days=P['kprod_reclass_gap_d'])
        _moved, _keep = [], []
        for _rs, _re in res['Снижение Рпл']:
            _adj = [(a, b) for a, b in res['Снижение Кпрод'] if pd.Timedelta(0) <= (_rs - b) <= _gap]
            _ok = False
            if _adj:
                _ks, _ke = max(_adj, key=lambda x: x[1])
                _base = _ip[(_ip.index >= _ks - pd.Timedelta(days=30)) & (_ip.index < _ks)].median()
                _atr  = _ip[(_ip.index >= _rs) & (_ip.index <= _rs + pd.Timedelta(days=15))].median()
                _pre  = _ip[(_ip.index >= _ks - pd.Timedelta(days=120)) & (_ip.index < _ks)]
                if len(_pre) >= 5 and pd.notna(_base) and pd.notna(_atr) and _base > 0:
                    _x = (_pre.index - _pre.index[0]).days.values
                    _rel = abs(float(np.polyfit(_x, _pre.values, 1)[0]) / _pre.mean() * 30 * 100)
                    if _atr < _base - P['kprod_reclass_tol'] and _rel < P['kprod_reclass_stable_pct']:
                        _ok = True
            (_moved if _ok else _keep).append((_rs, _re))
        if _moved:
            res['Снижение Кпрод'] = merge_iv(list(res['Снижение Кпрод']) + _moved,
                                             gap=pd.Timedelta(days=P['kprod_reclass_gap_d'] + 1))
            res['Снижение Рпл'] = _keep
    _split_keys = ['НУР','Рост обводненности','Снижение Кпрод','Деградация ЭЦН','РПТЧ']
    if not getattr(ctx, 'cyclic', False):
        _split_keys += ['Снижение Рпл','Рост Рпл']
    for k in _split_keys:
        res[k] = split_at(res[k], ctx.esp_breaks)
    # Сигнатурный слой: опциональная мягкая переразметка пограничных эпизодов
    if SIG_RELABEL:
        nur, sniz = list(res.get('НУР', [])), list(res.get('Снижение Рпл', []))
        nn, ns = [], []
        for s_, e_ in nur:
            sg = sig_score(ctx, s_, e_)
            (ns if (sg['label'] == 'Снижение Рпл' and sg['margin'] >= SIG_RELABEL_MARGIN) else nn).append((s_, e_))
        for s_, e_ in sniz:
            sg = sig_score(ctx, s_, e_)
            (nn if (sg['label'] == 'НУР' and sg['margin'] >= SIG_RELABEL_MARGIN) else ns).append((s_, e_))
        res['НУР'] = merge_iv(nn)
        res['Снижение Рпл'] = subtract_iv(merge_iv(ns), res['НУР'])

    # v9.8: в ДЛИННЫХ остановках (>12ч) допустима ТОЛЬКО ГДИ — вычитаем длинные
    # стопы из всех прочих диагностических категорий. Короткие стопы НЕ дробим.
    # ГДИ — событие простоя (оставляем); РПТЧ/Периодическая/СППВ — РЕЖИМЫ,
    # охватывают остановки (не дробим). Точечные/трендовые категории вычищаем
    # из длинных остановок (там должна быть только ГДИ).
    # На ЦИКЛИЧЕСКИХ скважинах >=12ч стопы — часть цикла (не дробим тренды/НУР).
    # Вычищаем длинные простои только на НЕциклических (там >=12ч = реальный idle);
    # РПТЧ/Периодическая/СППВ — режимы, охватывают остановки (всегда не дробим).
    if not getattr(ctx, 'cyclic', False):
        _keep_span = ('ГДИ', 'Работа', 'Остановка', 'РПТЧ', 'Периодическая работа', 'СППВ')
        for _k in list(res.keys()):
            if _k in _keep_span:
                continue
            res[_k] = subtract_iv(res[_k], ctx.long_stops)

    conf = {}
    for lbl, ivs in res.items():
        lst = []
        for s_, e_ in ivs:
            sc = score_episode(ctx, lbl, s_, e_)
            if lbl in ('НУР', 'Снижение Рпл'):
                sg = sig_score(ctx, s_, e_)
                sc['sig_label'] = sg['label']; sc['sig_margin'] = sg['margin']
                # сигнатура уверенно противоречит правилу -> понизить уверенность (флаг ревью)
                if sg['label'] != lbl and sg['margin'] >= SIG['margin_high']:
                    sc['tier'] = 'low'
            lst.append(sc)
        conf[lbl] = lst
    return res, ctx, conf


def run_all(tele_all, vsp_all, wells=None, P=PARAMS, events=None):
    rows = []
    wells = wells if wells is not None else sorted(tele_all['well_id'].unique())
    for wid in wells:
        tw = tele_all[tele_all['well_id'] == wid].set_index('telemetry_time').sort_index()
        vw = vsp_all[vsp_all['well_id'] == wid]
        if tw.empty: continue
        gev = None
        if events is not None:
            g = events[(events['well_id'] == wid) & (events['kind'] == 'gdi')]
            gev = list(zip(g['start'], g['end']))
        res, _, conf = label_well(tw, vw, P, gdi_events=gev)
        for lbl, ivs in res.items():
            dflt = [{'score': 1.0, 'tier': 'high', 'signals': {}}] * len(ivs)
            scores = conf.get(lbl, dflt)
            for (s, e), sc in zip(ivs, scores):
                rows.append((
                    wid, lbl, s, e,
                    round((e - s).total_seconds() / 86400, 2),
                    sc['score'],
                    sc['tier'],
                    sc.get('sig_label', ''),
                    sc.get('sig_margin', ''),
                    str(sc['signals']),
                ))
    return pd.DataFrame(rows, columns=[
        'well_id', 'label', 'start', 'end', 'dur_d',
        'confidence', 'confidence_tier', 'sig_label', 'sig_margin', 'signals',
    ])
