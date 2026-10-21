# VentOCR Module: Pes の推定（get_pes_from_transpulm）

VentOCR の事後解析モジュール。Hamilton の人工呼吸器の画面から読んだ経肺圧（Ptranspulm）と気道内圧（Paw）から、
食道内圧（Pes）を推定し、呼吸ごとの Pes・経肺圧の指標を求める。**研究用（Research use only）**。

## 対象

- エンジン: `hamilton_ventocr` 0.2.0 以降で、設定 `post_ocr.ptranspulm` をオンにして解析したもの
  （4 段目の波形が Ptranspulm の動画。波形の列 `Pressure`・`Ptranspulm` が必要）
- Ptranspulm の列が無い解析（4 段目が Pes の解析など）は「対象外」（`NotApplicable`）
- VentOCR 0.7.0 以降（`ventocr_min`）。約束事は MODULE_API.md（module_api 1）

## 出力

**波形**: `Pes_est`（Pes（推定）、cmH2O）。エンジンの波形の各点に1つずつ（同じ行数）

- `Pes_est[i] = Paw[i] − Ptranspulm[i − align_points]`（既定 `align_points` = 1）
- Hamilton の画面では、4 段目（Ptranspulm）の線が Paw の線より約 1 点（0.02 秒）早く描かれている。そのまま引くと
  Paw の立ち上がり・立ち下がりで尖りが出る（Pes max の誤差 1.99 cmH2O）ので、1 点前の Ptranspulm と組む（0.43 cmH2O。逆向きは 4.38 と悪化）
- 呼吸の最初の点には、前の呼吸の最後の Ptranspulm を使う（前の呼吸と波形がつながっていなければ空欄）

**呼吸ごとの値**

| 列 | 定義 |
|---|---|
| `Pes_max`・`Pes_min` | その呼吸の Pes_est の最大・最小 |
| `dPes` | Pes_max − Pes_min |
| `Ptrans_I` | 吸気の終わりの直前 0.1 秒（`end_insp_window_sec`）の Ptranspulm（1 点ずらしたもの）の平均。吸気の終わり = Paw の最大のあとで Paw がいちばん急に下がる点（呼吸の始まりから 3 秒 `end_insp_search_sec` まで） |
| `Ptrans_E` | その呼吸の最後の点の Ptranspulm（ずらさない） |
| `dPtrans` | Ptrans_I − Ptrans_E（動的。吸気ポーズは使わない） |
| `skip_reason` | 計算しなかった理由: `Abnormal`（ポップアップ）・`Fragment`（録画の最初・最後）・`Clipped`（目盛りの外）・`Wave_Missing`（Paw か Ptranspulm の空欄が 1 割（`max_missing_frac`）を超える、Alert の Partial）・`Too_Short`（10 点未満）・`No_Ptranspulm` |

**要約**（summary）: 各指標の中央値・四分位・件数、計算した・飛ばした呼吸の数（理由ごと）、使ったずらし量と吸気の終わりの決め方

イベントは出さない（非同調は、利用者がタグで分類してから）。Pes の PTP は、Hamilton の定義が分かるまで出さない。

## 検証

Hamilton 自身の呼吸ごとの値（日本光電 Study Recorder で記録した MonitorParameters）と比べた。
動画 Ptranspulm 2026-10-09 10-25-03（1 時間、hamilton_ventocr 0.8.3 の解析 = 0.1.0 と同じ）、計算した 1,202 呼吸。
記録の値は「次の呼吸の始まりで出る記録 = その呼吸の値」で、表示の更新の時刻と VT で呼吸を対応づけた。

| 値 | 記録 | n | bias | MAE | ±1 cmH2O 以内 |
|---|---|---|---|---|---|
| Pes_max | Pes max | 1202 | +0.13 | 0.43 | 93% |
| Pes_min | Pes min | 1110 | −0.60 | 0.81 | 78% |
| dPes | Pes max − Pes min | 1110 | +0.71 | 1.01 | 72% |
| Ptrans_I | Ptrans I | 1201 | −0.41 | 0.45 | 90% |
| Ptrans_E | Ptrans E | 1202 | −0.58 | 0.67 | 83% |

- 縦の分解能は画面の 1 点（Ptranspulm の目盛り 0〜20 で約 0.14 cmH2O）なので、細かい振れ（dPes）は苦手
- Hamilton の Ptrans I は「吸気時間の終わり」の値とみられる（吸気時間が分かれば MAE 0.34）が、吸気時間は画面に出ていないので Paw の下がり方から決める

## 設定（module_options.json）

| 名前 | 既定 | 内容 |
|---|---|---|
| `align_points` | 1 | Ptranspulm を何点前の行から取るか |
| `end_insp_window_sec` | 0.1 | Ptrans_I に使う、吸気の終わりの直前の時間（秒） |
| `end_insp_search_sec` | 3.0 | 吸気の終わりを探す範囲（呼吸の始まりからの秒） |
| `min_points` | 10 | これより点の少ない呼吸は計算しない |
| `max_missing_frac` | 0.1 | Paw か Ptranspulm の空欄がこの割合を超えた呼吸は計算しない |

## Author
- VentOCR Developer Team
