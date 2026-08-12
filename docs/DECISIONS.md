# DECISIONS

## 2026-08-12 立案

- **獨立 repo**（`FeykerProjects/hongyu-intake-poc`），不進 feyker-agent：
  工作台規矩是產品不住 Agent Base；面試可能投影，個人工作台不能入鏡。
- **技術**：Python + Streamlit + OpenAI Structured Outputs（金鑰沿用既有）＋
  **離線 fallback 為一級路徑**——無金鑰／斷網照樣能展示四案例。
- **範圍**：P0 只做紙盒/彩盒/禮盒；其餘品類列為未來模組。不做報價。
- **派工模型**：Claude Code 主開發；Codex 獨立驗收（背景 `codex exec`，
  不走同步 MCP——2026-08-11 實測同步路會凍住對話）；Feyker 產品負責人，
  觸點壓縮為兩個：試用四案例、面試日取捨。最多兩輪修正，不無限互評。
- **Codex 審查節制**：AGENTS.md Reviewer conduct 節——分級含「非問題」桶、
  禁提範圍擴張與投機性加固。動機：Codex 傾向 correct-and-unnecessary。
- **來源策略**：PUBLIC_SOURCES 全部標「待複驗」，建置期間抽查；
  Demo 口徑只說「有公開依據」，不宣稱逐條查證。
- **不納入**：Kimi/Grok 子代理（訊號已記入工作台 ledger，面試後評估）。

## 2026-08-12 Codex 規格審查裁決（6×P0、11×P1、1×P2、2×非問題）

全數成立。三條屬「文件落後於實作」，改文件不改碼：
- 尺寸原文改掛在各自 `Dimensions.original_text`（優於原案的單一
  `dimension_unit_original`，兩組尺寸同時出現才能各自無損保存）。
- 質感措辭進獨立的 `preferences` 欄（Codex 建議放 `notes`——駁回：
  獨立欄位才讓「不得轉成材料」變成可測試的斷言）。
- 完整度維持 `已填/必填總數` 字串（Codex 建議 0–100 整數——駁回：
  畫面本來就顯示 n/m，字串與畫面同源少一次換算）。

三條改了程式：新增 `status_by_field`（逐欄四值狀態）、
`manual_review_required` 生命週期只在匯出副本翻 `false`、
把 Demo 必填 12 欄正式寫進 DATA_SCHEMA G 節當完整度分母
（明示非宏宇實際規則）。

案例 4 保留「產品寬…」原輸入（Codex 建議改成「包裝外徑」——駁回：
客戶講「產品」時就是指內容物，這比改題目更接近真實輸入），
改為在 ACCEPTANCE 寫明歸屬判定依據與 risk_note 期望。
