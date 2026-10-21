"""Pes の推定（get_pes_from_transpulm）: Hamilton の経肺圧（Ptranspulm）と気道内圧（Paw）から、食道内圧（Pes）を求める事後解析モジュール。

Hamilton は 4 段目に Ptranspulm（= Paw − Pes）を表示できる。エンジン（hamilton_ventocr 0.2.0、設定 post_ocr.ptranspulm）が読んだ
Ptranspulm の波形から、Pes_est = Paw − Ptranspulm と、呼吸ごとの Pes・経肺圧の指標を求める。

定義（Study Recorder の MonitorParameters と、Ptranspulm 2026-10-09 の 1,199 呼吸で比べて決めた。README・CHANGELOG）:
- 4 段目の線は Paw の線より約 1 点（0.02 秒）早く描かれている。Pes_est[i] = Paw[i] − Ptranspulm[i − align_points]（既定 1）。
  呼吸の最初の点には、前の呼吸の最後の Ptranspulm を使う（前の呼吸とつながっていなければ NaN）
- Pes_max・Pes_min = その呼吸の Pes_est の最大・最小、dPes = Pes_max − Pes_min
- Ptrans_I = 吸気の終わり（Paw の最大のあとで Paw がいちばん急に下がる点）の直前 end_insp_window_sec の Ptranspulm（ずらしたもの）の平均
- Ptrans_E = その呼吸の最後の点の Ptranspulm（ずらさない）、dPtrans = Ptrans_I − Ptrans_E
"""
import numpy as np
import pandas as pd

MODULE_VERSION = "0.1.1"

try:  # アプリ（VentOCR 0.7.0〜）の例外。無ければ同じ名前で定義する（アプリは名前で判別する）
    from ventocr_core.modules import NotApplicable
except Exception:  # noqa: BLE001
    class NotApplicable(Exception):
        """解析全体が対象外（失敗ではない）。"""

PAW, PTRANS, PES = "Pressure", "Ptranspulm", "Pes_est"
END_INSP_METHOD = "steepest Paw drop after the Paw peak (within end_insp_search_sec of the breath start); mean of the preceding window"

DEFAULTS = {
    "align_points": 1,           # Ptranspulm を何点前の行から取るか
    "end_insp_window_sec": 0.1,  # Ptrans_I に使う、吸気の終わりの直前の時間
    "end_insp_search_sec": 3.0,  # 吸気の終わりを探す範囲（呼吸の始まりから）
    "min_points": 10,            # これより点の少ない呼吸は計算しない（Too_Short）
    "max_missing_frac": 0.1,     # Paw か Ptranspulm の空欄がこの割合を超えたら計算しない（Wave_Missing。欠けた所に山があると最大・最小を外す）
}
METRICS = ["Pes_max", "Pes_min", "dPes", "Ptrans_I", "Ptrans_E", "dPtrans"]


def _options(settings):
    opts = dict(DEFAULTS)
    for section in (settings or {}).values() if isinstance(settings, dict) else ():
        if isinstance(section, dict):
            opts.update({k: v for k, v in section.items() if k in DEFAULTS})
    opts.update({k: v for k, v in (settings or {}).items() if k in DEFAULTS})
    return opts


def _skip_reason(row):
    """Breaths.csv の列から、計算しない理由（無ければ None）。"""
    alert = str(row.get("Alert", "") or "")
    if int(pd.to_numeric(row.get("Abnormal", 0), errors="coerce") or 0) == 1 or "Abnormal" in alert:
        return "Abnormal"
    if "Fragment" in alert:
        return "Fragment"
    if "Clipped" in alert:
        return "Clipped"
    if "Partial" in alert:
        return "Wave_Missing"
    return None


def _contiguous(prev, cur):
    """前の呼吸の波形が、この呼吸の波形の直前までつながっているか（掃引の通しの位置 X、無ければ時刻 t で判断）。"""
    if prev is None or len(prev) == 0 or len(cur) == 0:
        return False
    if "X" in prev and "X" in cur and pd.notna(prev["X"].iloc[-1]) and pd.notna(cur["X"].iloc[0]):
        return int(cur["X"].iloc[0]) - int(prev["X"].iloc[-1]) == 1
    if "t" in prev and "t" in cur and len(cur) >= 2:
        step = float(np.nanmedian(np.diff(cur["t"].to_numpy(float))))
        return abs(float(cur["t"].iloc[0]) - float(prev["t"].iloc[-1]) - step) <= 0.5 * step
    return False


def aligned_ptranspulm(cur, prev, k):
    """行 i に組む Ptranspulm[i − k]。最初の k 点は前の呼吸の最後の k 点（つながっていなければ NaN）。"""
    pt = cur[PTRANS].to_numpy(float)
    if k <= 0:
        return pt.copy()
    head = np.full(k, np.nan)
    if _contiguous(prev, cur) and PTRANS in prev and len(prev) >= k:
        head = prev[PTRANS].to_numpy(float)[-k:]
    return np.concatenate([head, pt[:-k]])[:len(pt)]


def end_of_inspiration(paw, t, search_sec):
    """吸気の終わり = Paw の最大のあとで、Paw がいちばん急に下がる点（行番号）。探すのは呼吸の始まりから search_sec まで。"""
    n = len(paw)
    within = np.flatnonzero((t - t[0]) <= search_sec) if t is not None else np.arange(n)
    last = int(within[-1]) if len(within) else n - 1
    p = paw[:last + 1]
    if not np.isfinite(p).any():
        return None
    k0 = int(np.nanargmax(p))
    d = np.diff(pd.Series(paw[:last + 2]).interpolate(limit_area="inside").to_numpy())[k0:last + 1]
    if len(d) == 0 or not np.isfinite(d).any():
        return None
    return k0 + int(np.nanargmin(d)) + 1   # 下がった後の点。直前の窓は [kd − w, kd)


def breath_metrics(cur, prev, opts, rate):
    """1 呼吸の (Pes_est の配列, 指標の dict)。"""
    k = int(opts["align_points"])
    paw = cur[PAW].to_numpy(float)
    pt = cur[PTRANS].to_numpy(float)
    pts = aligned_ptranspulm(cur, prev, k)
    pes = paw - pts
    m = dict.fromkeys(METRICS, np.nan)
    if np.isfinite(pes).any():
        m["Pes_max"], m["Pes_min"] = float(np.nanmax(pes)), float(np.nanmin(pes))
        m["dPes"] = m["Pes_max"] - m["Pes_min"]
    t = cur["t"].to_numpy(float) if "t" in cur else None
    kd = end_of_inspiration(paw, t, float(opts["end_insp_search_sec"]))
    w = max(1, int(round(float(opts["end_insp_window_sec"]) * rate)))
    if kd is not None and kd >= 1:
        win = pts[max(kd - w, 0):kd]
        if np.isfinite(win).any():
            m["Ptrans_I"] = float(np.nanmean(win))
    fin = np.flatnonzero(np.isfinite(pt))
    if len(fin):
        m["Ptrans_E"] = float(pt[fin[-1]])
    if np.isfinite([m["Ptrans_I"], m["Ptrans_E"]]).all():
        m["dPtrans"] = m["Ptrans_I"] - m["Ptrans_E"]
    return pes, m


def run(data, settings, progress):
    opts = _options(settings)
    channels = getattr(data, "channels", None) or {}
    if channels and PTRANS not in channels:
        raise NotApplicable("この解析には Ptranspulm の波形がありません（Hamilton エンジン 0.2.0 以降で、設定 post_ocr.ptranspulm をオンにして解析してください）")
    if channels and PAW not in channels:
        raise NotApplicable("この解析には Pressure（Paw）の波形がありません")

    breaths = data.breaths
    numbers = [int(n) for n in (breaths.sort_values("t_start")["breath_no"] if "t_start" in breaths else breaths["breath_no"])]
    by_no = breaths.set_index("breath_no")
    waves_out, rows = {}, []
    cache = {}   # 直前の呼吸を読み直さないように（前の呼吸の最後の点を使うため）

    def wave(no):
        if no not in cache:
            if len(cache) > 4:
                cache.clear()
            cache[no] = data.waves(no)
        return cache[no]

    for i, no in enumerate(numbers):
        progress(i, len(numbers), "")
        row = {"breath_no": no, **dict.fromkeys(METRICS, np.nan), "skip_reason": ""}
        cur = wave(no)
        reason = _skip_reason(by_no.loc[no])
        if reason is None:
            if cur is None or len(cur) == 0:
                reason = "Wave_Missing"
            elif PTRANS not in cur:
                reason = "No_Ptranspulm"
            elif len(cur) < int(opts["min_points"]):
                reason = "Too_Short"
            elif max(cur[PAW].isna().mean(), cur[PTRANS].isna().mean()) > float(opts["max_missing_frac"]):
                reason = "Wave_Missing"
        if reason is not None or cur is None or PTRANS not in cur:
            row["skip_reason"] = reason or "No_Ptranspulm"
            rows.append(row)
            continue
        before = data.neighbors(no, before=1, after=0) if hasattr(data, "neighbors") else []
        prev = wave(before[-1]) if before else None
        if "t" in cur and len(cur) >= 2:
            rate = 1.0 / float(np.nanmedian(np.diff(cur["t"].to_numpy(float))))
        else:
            rate = 50.0
        pes, m = breath_metrics(cur, prev, opts, rate)
        row.update({k: (round(v, 3) if np.isfinite(v) else np.nan) for k, v in m.items()})
        rows.append(row)
        out = pd.DataFrame({"X": cur["X"].to_numpy() if "X" in cur else np.arange(len(cur)), PES: np.round(pes, 2)})
        if "t" in cur:
            out.insert(1, "t", cur["t"].to_numpy(float))
        waves_out[no] = out
    progress(len(numbers), len(numbers), "")

    table = pd.DataFrame(rows, columns=["breath_no", *METRICS, "skip_reason"])
    done = table[table["skip_reason"] == ""]
    summary = {
        "module_version": MODULE_VERSION,
        "align_points": int(opts["align_points"]),
        "end_of_inspiration": END_INSP_METHOD,
        "end_insp_window_sec": float(opts["end_insp_window_sec"]),
        "end_insp_search_sec": float(opts["end_insp_search_sec"]),
        "breaths_total": int(len(table)),
        "breaths_computed": int(len(done)),
        "breaths_skipped": {r: int(c) for r, c in table.loc[table["skip_reason"] != "", "skip_reason"].value_counts().items()},
    }
    for col in METRICS:
        v = done[col].dropna()
        summary[col] = ({"median": round(float(v.median()), 3), "q1": round(float(v.quantile(0.25)), 3),
                         "q3": round(float(v.quantile(0.75)), 3), "n": int(len(v))} if len(v) else {"n": 0})
    return {"waves": waves_out, "breaths": table, "summary": summary}
