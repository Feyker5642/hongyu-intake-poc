# DEPLOY — 上線手冊

## 為什麼不是 Cloudflare Pages

feyker.dev 是靜態網站（Vite 打包成 HTML/JS），Cloudflare Pages 直接放檔案就好。
這個專案是**跑著的 Python 伺服器**，Streamlit 還需要 WebSocket 長連線，
Pages 放不了。兩者路線不同，不是設定問題。

## 選定平台：Streamlit Community Cloud

| 項目 | 現況（2026-08-12 查證） |
|---|---|
| 費用 | 免費 |
| Python | 支援 3.10–3.14，**預設 3.12**（本專案不指定，用預設） |
| 公開 App | 無數量上限；私人 App 免費版只有 1 個 |
| 私有 repo | 可以（Streamlit 建唯讀 deploy key） |
| 休眠 | 12 小時無流量進入休眠，有人連線就喚醒 |
| 自訂網域 | **免費版沒有**，網址是 `<app>.streamlit.app` |
| 記憶體 | 約 1 GB（本專案無模型、無資料庫，綽綽有餘） |

比較過 Hugging Face Spaces：資源更好（16GB RAM、48 小時才休眠），
但同樣沒有免費自訂網域，且 Streamlit 官方平台對 Streamlit 專案設定最少。
本專案負載極小，選官方平台。

## 部署為什麼是安全的

**這個 App 在雲端不需要任何金鑰。** 離線規則引擎是解析底座，
沒有 `OPENAI_API_KEY` 時四個案例照樣完整跑完。所以：

- 雲端**不設定** secrets → 沒有金鑰可被盜用、沒有帳單風險
- 頁面常駐標示 Concept Demo／合成資料／非正式報價
- 全部資料是合成的，沒有真實客戶內容
- `.env` 在 `.gitignore` 裡，已確認未被追蹤

若之後要展示 LLM 路徑，在 Streamlit 的 App settings → Secrets 貼上
`OPENAI_API_KEY`，不要進 Git。

## 現況

- Repo：<https://github.com/Feyker5642/hongyu-intake-poc>（public、`main`）
- App：<https://hongyu-intake-poc.streamlit.app/>（2026-08-12 上線）
- Secrets：**未設定**，刻意的——離線規則引擎不需要金鑰

## 上線步驟

1. `gh repo create Feyker5642/hongyu-intake-poc --source=. --push`（可視性見下）
2. 到 <https://share.streamlit.io> 用 GitHub 登入授權（**只有 Feyker 能做**）
3. New app → 選 repo → main → `app.py` → Deploy
4. 拿到 `https://<app-name>.streamlit.app`

## 休眠的實務對策

12 小時沒人連線就會睡著，第一個訪客要等約 30 秒喚醒。
**面試前 10 分鐘自己開一次網址**，它就是醒的。

## 與 feyker.dev 的關係

免費版不能把 `demo.feyker.dev` 指過去。正確的整合方式是
**在 feyker.dev 加一張案例卡，連到這個 App**——作品集是門面，
Demo 是可操作的證據。這也是 feyker.dev 現有案例的做法。

## Sources

- <https://docs.streamlit.io/deploy/streamlit-community-cloud/status>
- <https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/upgrade-python>
- <https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy>
- <https://huggingface.co/docs/hub/en/spaces-sdks-streamlit>
