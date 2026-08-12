# 宏宇工藝 AI 詢價轉單助手（Concept Demo）

面試概念驗證：把非結構的包裝詢價文字轉成結構化、可編輯、可驗證的欄位，
標出缺漏與矛盾，人工確認後匯出 JSON。**非正式報價系統；全部使用合成資料。**

## 快速開始

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

無 `OPENAI_API_KEY` 時自動進入離線 Demo 模式（內建四個合成案例的解析結果）。

## 設定

複製 `.env.example` 為 `.env`，填入金鑰。金鑰永不進 commit。

## 測試

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## 文件

- `docs/PRODUCT_SPEC.md` — 定位與頁面
- `docs/DATA_SCHEMA.md` — 資料模型與防呆規則
- `docs/ACCEPTANCE.md` — 驗收標準與四個案例
- `docs/PUBLIC_SOURCES.md` — 欄位的公開依據（與免責聲明）
- `docs/DECISIONS.md` — 取捨紀錄
