# 宏宇工藝 AI 詢價轉單助手（Concept Demo）

**線上試用：<https://hongyu-intake-poc.streamlit.app/>**

把非結構的包裝詢價文字轉成結構化、可編輯、可驗證的欄位，標出缺漏與矛盾，
人工確認後匯出 JSON。定位是 **ERP 前面的詢價整理層**，不是報價系統。

> **Concept Demo · 全部使用合成資料 · 非正式報價系統**
> 欄位定義整理自公開同業表單（見 `docs/PUBLIC_SOURCES.md`），
> 不代表宏宇工藝實際材料、價格、供應商或生產能力。

## 它在做什麼

| | |
|---|---|
| 輸入 | 客戶從 Email／LINE／電話紀錄丟來的一段不完整需求 |
| 輸出 | 標準欄位 + 缺漏清單 + 矛盾標記 + 每欄原文依據 + 追問訊息 |
| 底線 | 沒寫的一律 `null`，矛盾不代為選擇，未經人工確認不得匯出 |

**不需要 API 金鑰即可完整展示**——解析的底座是確定性規則引擎，
LLM 只是可選的加強層，而且數量、尺寸、日期、金額一律以規則層為準。

## 快速開始（乾淨 checkout）

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

**不需要 API 金鑰也能完整展示**——沒有 `OPENAI_API_KEY` 時自動走離線規則解析，
四個合成案例照樣可以載入、解析、確認、匯出。

## 設定（可選）

複製 `.env.example` 為 `.env` 填入金鑰後，解析改走 OpenAI Structured Outputs；
缺漏、矛盾與完整度仍由規則層複核。金鑰永不進 commit。

## 測試

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## 文件

- `docs/PRODUCT_SPEC.md` — 定位與頁面
- `docs/DATA_SCHEMA.md` — 資料模型與防呆規則
- `docs/ACCEPTANCE.md` — 驗收標準與四個案例
- `docs/PUBLIC_SOURCES.md` — 欄位的公開依據（與免責聲明）
- `docs/DECISIONS.md` — 取捨紀錄
