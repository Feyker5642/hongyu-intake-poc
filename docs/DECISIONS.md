# DECISIONS

## 2026-08-12 立案

- **獨立 repo**（`FeykerProjects/hongyu-intake-poc`），不進 feyker-agent：
  工作台規矩是產品不住 Agent Base；面試可能投影，個人工作台不能入鏡。
- **技術**：Python + Streamlit + OpenAI Structured Outputs（金鑰沿用既有）＋
  **離線 fallback 為一級路徑**——無金鑰／斷網照樣能展示四案例。
- **範圍**：P0 只做紙盒/彩盒/禮盒；其餘 11 類列為未來模組。不做報價。
- **派工模型**：Claude Code 主開發；Codex 獨立驗收（背景 `codex exec`，
  不走同步 MCP——2026-08-11 實測同步路會凍住對話）；Feyker 產品負責人，
  觸點壓縮為兩個：試用四案例、面試日取捨。最多兩輪修正，不無限互評。
- **Codex 審查節制**：AGENTS.md Reviewer conduct 節——分級含「非問題」桶、
  禁提範圍擴張與投機性加固。動機：Codex 傾向 correct-and-unnecessary。
- **來源策略**：PUBLIC_SOURCES 全部標「待複驗」，建置期間抽查；
  Demo 口徑只說「有公開依據」，不宣稱逐條查證。
- **不納入**：Kimi/Grok 子代理（訊號已記入工作台 ledger，面試後評估）。
