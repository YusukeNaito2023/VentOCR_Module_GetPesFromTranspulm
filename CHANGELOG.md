# CHANGELOG

## 0.1.1 (2026-10-21)
- manifest.json に、言語ごとの表示名・説明（display_name_ja / _en、description_ja / _en）と、この解析に使えないときの案内（requires_hint、_ja / _en）を足した
  （VentOCR 0.7.1 から読む。0.7.0 は display_name・description だけを読むので残した）
- 精度の評価を validation.json に（モジュールの一覧の make_entry が読む。値は 0.1.0 と同じ）
- 計算は 0.1.0 と同じ

## 0.1.0 (2026-10-21)
- 最初の版。波形 Pes_est（= Paw − 1 点前の Ptranspulm）、呼吸ごとの Pes_max・Pes_min・dPes・Ptrans_I・Ptrans_E・dPtrans・skip_reason、要約
- 定義は hamilton と app で決めた（VentOCR の設計案 第4版 10 章）。Study Recorder の MonitorParameters と 1,202 呼吸で比べて、
  Pes_max の MAE 0.43、Ptrans_I 0.45、Ptrans_E 0.67 cmH2O（README）
- 空欄の上限（max_missing_frac）は 0.1。0.3 にすると、欠けた所に Pes の山がある呼吸（23 呼吸）が入り、Pes_max の誤差が大きく外れる
