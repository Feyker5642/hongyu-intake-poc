# EVAL_CORPUS — 台灣包裝印刷詢價合成評測集

`data/eval_corpus.json` 收錄 100 條人工設計、人工標註的合成客戶訊息，用來檢查詢價抽取流程是否能在真實訊息常見的混亂情況下，仍遵守 `docs/DATA_SCHEMA.md` 的欄位與防呆規則。

這些訊息全部是合成資料，不含真實客戶資料。人名、公司、電話與 Email 若有出現，也只供測試格式使用。

## 檔案結構

```json
{
  "cases": [
    {
      "id": "001",
      "category": "口語",
      "text": "客戶原始訊息",
      "expected": {
        "request": {},
        "system": {}
      }
    }
  ]
}
```

- `id`：固定三位數，範圍為 `001` 到 `100`。
- `category`：該案例主要要測的訊息型態；同一案例仍可能同時包含其他難點。
- `text`：模型收到的完整客戶訊息。
- `expected.request`：依 `DATA_SCHEMA.md` 標註的期望詢價欄位。
- `expected.system`：缺漏、歧義、衝突、證據、欄位狀態、風險與完整度標註。

## 類別分布

| 類別 | 筆數 | 主要測試內容 |
|---|---:|---|
| 口語 | 10 | 「消光」「上下蓋分開」「不要太花」等日常說法 |
| 中文數字 | 10 | 三千、一千二百、二〇二六年等寫法 |
| 混合單位 | 10 | mm、cm、m、ml 與中英文單位混用 |
| 電報式 | 10 | 斜線、短語、無完整句子的規格清單 |
| 英文 | 10 | 英文或中英混合詢價 |
| 資訊矛盾 | 10 | 同一欄位出現兩個互斥值，不替客戶取捨 |
| 大量缺漏 | 10 | 只有品類、數量或模糊需求等極少資訊 |
| 提示注入 | 10 | 客戶文字夾帶「忽略規則」「輸出假值」等指令 |
| Email轉寄 | 10 | Subject、From、轉寄層、簽名檔與引文混在一起 |
| LINE碎句 | 10 | 多則短訊、補充、更正與口語省略 |

每類 10 筆，共 100 筆。

## 標註原則

### 1. 沒寫就不猜

- 未提及的純量欄位標成 `null`。
- schema 定義為多值陣列的 `finishes`、`preferences`，未提及時使用空陣列 `[]`。
- 不因產品類型、業界慣例或語氣自行推導紙材、盒型、尺寸、預算或加工。

### 2. 尺寸分流與換算

- 內容物尺寸只進 `product_dimensions`。
- 包裝成品尺寸只進 `package_dimensions`。
- 無法判定歸屬的尺寸只進 `dimensions_unclassified`，並在 `ambiguous_fields` 說明。
- cm、mm、m 會換算成 mm，但 `original_text` 永遠保留原寫法。
- 只有內容物尺寸、沒有包裝成品尺寸時，保留風險提示，不把兩者互填。

### 3. 中文數字與近似值

- 可明確換算的中文數字會轉成 schema 所需型別，例如「三千個」標成 `3000`。
- 「大概」「約」「左右」仍可保留抽出的值，但欄位狀態標成 `不確定`，並留下歧義證據。
- 無法可靠換算或缺少單位時不猜，保留在歧義標註。

### 4. 衝突不裁決

- 同一欄位出現互斥值時，正式欄位維持 `null`；多值欄位維持 `[]`。
- 所有候選值以字串放入 `system.conflicts[].values`。
- `status_by_field` 對應欄位標成 `不確定`。
- 若後一句明確更正前一句，才採用新值，並把更正過程保留在原文與證據中。

### 5. 日期、金額與偏好

- 只有完整年月日才輸出 ISO 日期。
- 「九月底」「下週」「月底前」等不完整日期，`requested_delivery_date` 為 `null`，原文放在 `delivery_date_original`，並標示歧義。
- 只有客戶明確表達整體或單位預算時才填 `budget`；「每個 100 元成交」等喊價不視為預算。
- 「高級」「環保」「不要太貴」只放 `preferences`，不轉成特定材料或金額。

### 6. 客戶文字永遠只是資料

提示注入案例中的「忽略規則」「把缺漏填滿」「不要人工確認」等文字都不會改變標註規則。`raw_request` 仍完整保存原文，未提供欄位仍為 `null`，`manual_review_required` 仍為 `true`。

### 7. 系統欄位

- `evidence_by_field` 保留重要抽取欄位的原文片段。
- `status_by_field` 固定涵蓋下述 12 個 Demo 必填欄位，並使用 `已確認`、`AI抽取`、`不確定`、`未提供` 四值；不在 12 欄內的衝突仍完整記在 `conflicts`，但不另增狀態鍵。本評測集尚未經業務人工修改，因此不使用 `已確認`。
- `ambiguous_fields.field` 為 `dimensions` 時，代表連「內容物尺寸或包裝尺寸」都無法判定，因此 `product_dimensions` 與 `package_dimensions` 的狀態都標成 `不確定`；若原文明示其中一種，只標對應欄位。
- `data_completeness` 依 Demo 的 12 個必填欄位計算：產品類別、內容物、數量、內容物尺寸、包裝成品尺寸、盒型、紙材、紙張磅數、表面加工、設計稿狀態、交期、交貨地點。
- 所有案例的 `manual_review_required` 都是 `true`。

## 文件版 schema 與目前 Python model 的差異

本評測集以 `docs/DATA_SCHEMA.md` 為欄位權威，因此包含文件中定義的 `flute_or_board_thickness`。目前 `schemas/packaging_request.py` 尚未宣告這個欄位；本次任務依要求不修改程式。後續若用 Pydantic model 做嚴格評測，需先另案對齊兩者，避免該欄被忽略。

## 適合怎麼使用

1. 把每筆 `text` 送進待測抽取流程。
2. 將輸出與 `expected.request`、`expected.system` 分欄比較。
3. 尺寸、日期、數量等正規化值與 `original_text` 分開評分。
4. 對 `conflicts`、`ambiguous_fields`、`manual_review_required` 設獨立通過條件，避免只看欄位填得多不多。
5. 失敗案例以 `id` 回查，不直接修改 gold label 來迎合現有 parser；只有確認標註本身錯誤時才修正。

## 本次資料檢查

- [x] 共有 100 筆，ID 為 `001`–`100` 且不重複。
- [x] 十個主要類別各 10 筆。
- [x] 每筆 `raw_request` 與 `text` 完全一致。
- [x] 每筆都有文件版 request 欄位與完整 system 欄位。
- [x] 每筆 `status_by_field` 都涵蓋 12 個 Demo 必填欄位。
- [x] 每筆 `data_completeness` 與實際已填欄位數一致。
- [x] 非空的重要欄位都有原文證據。
- [x] 衝突候選值一律為字串，衝突欄位標成 `不確定`。
- [x] 所有案例維持 `manual_review_required: true`。
