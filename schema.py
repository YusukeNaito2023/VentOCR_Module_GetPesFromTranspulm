"""設定項目（VentOCR の schema.py と同じ形）。最小版のアプリには、利用者が変える画面は無い（module_options.json の値をそのまま使う）。"""
MODULE_SETTINGS_SCHEMA = {
    "align_points": {
        "type": "int", "default": 1,
        "label": "Ptranspulm を何点前の行から取るか（4段目の線は Paw より約1点早く描かれている）",
    },
    "end_insp_window_sec": {
        "type": "float", "default": 0.1,
        "label": "Ptrans_I に使う、吸気の終わりの直前の時間（秒）",
    },
    "end_insp_search_sec": {
        "type": "float", "default": 3.0,
        "label": "吸気の終わりを探す範囲（呼吸の始まりからの秒）",
    },
    "min_points": {
        "type": "int", "default": 10,
        "label": "これより点の少ない呼吸は計算しない",
    },
    "max_missing_frac": {
        "type": "float", "default": 0.1,
        "label": "Paw か Ptranspulm の空欄がこの割合を超えた呼吸は計算しない",
    },
}
