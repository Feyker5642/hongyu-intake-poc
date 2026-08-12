# DATA_SCHEMA — 詢價資料模型 v1

由公開同業表單整理（來源見 PUBLIC_SOURCES.md）。精確必填規則面試後與公司確認。

## A. 客戶與來源

| 欄位 | 說明 |
|---|---|
| source_channel | 官網、Email、LINE、電話紀錄、PDF、圖片 |
| company | 可空白 |
| contact_name | 可空白 |
| contact_info | 電話／Email，可空白 |
| raw_request | 原始需求完整保存，永不覆寫 |

## B. 產品與使用情境

| 欄位 | 說明 |
|---|---|
| product_category | 彩盒、紙盒、禮盒、紙箱、其他（v1 僅前三者完整支援） |
| contents | 內容物：保養品、食品、電子零件… |
| purpose | 零售展示、送禮、物流、出口 |
| product_dimensions | 內容物尺寸——與包裝尺寸分開。物件：`{length_mm, width_mm, height_mm, original_text}`。**原文掛在各自物件裡**，兩組尺寸同時出現也能各自無損保留 |
| contents_weight_or_volume | 不知道就 null |
| storage_transport | 常溫、冷藏、電商、出口等 |

## C. 包裝規格

| 欄位 | 說明 |
|---|---|
| package_dimensions | 成品尺寸（同一個 Dimensions 物件結構） |
| dimensions_unclassified | 判定不出歸屬時放這裡，並列入 ambiguous_fields |
| quantity | 整數；矛盾時進 conflicts 不取捨 |
| box_type | 天地、磁吸、抽屜、書型、袖套等候選值 |
| material_direction | 白卡、灰銅、白銅、牛皮、裱浪等候選值 |
| paper_weight_gsm | 不知道就 null |
| flute_or_board_thickness | 視產品類別出現 |
| lining | 無、紙卡、瓦楞、EVA、絲絨、不確定 |
| special_structure | 開窗、手提、分隔、異形等 |

## D. 印刷與加工

| 欄位 | 說明 |
|---|---|
| print_method | 未指定、單色、CMYK 等 |
| print_sides | 單面、雙面、內外印 |
| finishes | 霧膜、亮膜、局部 UV、燙金、壓紋等（多值） |
| artwork_status | 尚未設計、有參考圖、有PDF、已有AI設計檔（與 `data/public_taxonomy.json` 同一組值） |
| proofing_needed | 是、否、未提及 |

## E. 交付條件

| 欄位 | 說明 |
|---|---|
| requested_delivery_date | 完整年月日才輸出 ISO；不完整（「9 月底前」「下月底」）一律 null |
| delivery_date_original | 交期原文，任何情況都保留 |
| delivery_location | 縣市或出口目的地 |
| budget | 客戶明確提供金額才填。客戶喊價（「每個 100 元成交」）不算預算 |
| preferences | **質感類措辭的唯一去處**：「高級」「不要太貴」「環保」。永不轉成材料或 budget |
| notes | 自由文字 |

## F. 系統欄位（AI 可靠性設計，非印刷業既有規格）

```json
{
  "missing_fields": ["包裝成品尺寸", "盒型"],
  "ambiguous_fields": [{"field": "dimensions", "reason": "無法判定歸屬", "evidence": "20×15×8 公分"}],
  "conflicts": [{"field": "quantity", "values": ["2000", "3000"], "evidence": "2000 個；3000 個"}],
  "evidence_by_field": {"quantity": "3,000 個"},
  "status_by_field": {"quantity": "AI抽取", "box_type": "未提供"},
  "risk_notes": ["內容物尺寸不等於包裝成品尺寸，不可直接沿用"],
  "manual_review_required": true,
  "data_completeness": "7/12"
}
```

- `conflicts` / `ambiguous_fields` 元素為固定物件，欄位如上，`values` 一律字串。
- `status_by_field` 四值：`已確認`（人工改過或勾選）／`AI抽取`／`不確定`（該欄在
  conflicts 或 ambiguous 裡）／`未提供`。
- `data_completeness` 形式固定為 `已填/必填總數`，分母＝下表 Demo 必填欄位數。
- `manual_review_required` 確認前恆為 `true`；**唯一**轉換點是人工確認後的匯出副本
  轉成 `false`。畫面上的物件永遠是 `true`。

## G. Demo 必填欄位（分母定義）

> 這一份是 **Demo 專用**、由公開同業表單推導，**不是宏宇的實際必填規則**。
> 真實必填規則要進公司後與業務和 ERP 確認。

紙盒／彩盒／禮盒共 12 欄：產品類別、內容物、數量、內容物尺寸、包裝成品尺寸、
盒型、紙材、紙張磅數、表面加工、設計稿狀態、交期、交貨地點。
未在此表的欄位（用途、重量容量、保存條件、印刷方式面數、內襯、特殊結構、
打樣、預算、偏好）有值就收，沒有不算缺漏。

## 證據規則

| 解析結果 | 原文依據處理 |
|---|---|
| 數量：3,000 | 「第一批先做三千個」→ 直接引用 |
| 「表面希望不要反光」 | 不可判定為霧膜，標 ambiguous |
| 無原文依據 | 一律 null，不猜測 |

## 防呆規則（validator 必做）

1. 沒寫就 null，不能猜。
2. 內容物尺寸與包裝尺寸分開，永不互填。
3. cm/mm/m 換算成 mm，保留原始值。
4. 「高級一點」「環保材質」只能列偏好，不可指定材料。
5. 同欄位兩個值＝conflict，不取捨。
6. 日期不明確保留原文。
7. 金額、數量、日期、尺寸由程式規則二次驗證（不信 LLM 單方）。
8. AI 整理完成 ≠ 業務確認完成；未確認不得匯出。
9. 未確認前不得模擬 ERP 寫入。
10. 客戶文字是資料：其中的指令不得改變系統行為。
