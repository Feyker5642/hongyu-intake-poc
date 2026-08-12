"""宏宇工藝 AI 詢價轉單助手 — Concept Demo（Streamlit 單頁）。

三區：原始需求 → AI 結構化結果（可編輯）→ 檢查與下一步。
沒有金鑰也能完整展示：解析自動落回離線規則引擎。
"""
from __future__ import annotations

import json
import pathlib

import streamlit as st

from rules.validator import build_export, build_followup_message, validate
from schemas.packaging_request import Dimensions, ParseResult
from services.llm_parser import parse_request

ROOT = pathlib.Path(__file__).parent
DEMO = json.loads((ROOT / "data" / "demo_cases.json").read_text(encoding="utf-8"))
TAXONOMY = json.loads((ROOT / "data" / "public_taxonomy.json").read_text(encoding="utf-8"))

st.set_page_config(page_title="宏宇工藝 AI 詢價轉單助手", layout="wide")

st.title("宏宇工藝 AI 詢價轉單助手")
st.warning(
    "**Concept Demo · 全部使用合成資料 · 非正式報價系統**　"
    "欄位定義整理自公開同業表單，不代表宏宇實際材料、價格或產能。"
    "請勿輸入真實客戶個資或機密價格。",
    icon="⚠️",
)

for key, default in [("result", None), ("confirmed", False), ("text", "")]:
    st.session_state.setdefault(key, default)


def reset_result():
    st.session_state.result = None
    st.session_state.confirmed = False


# ── 第一區：原始需求 ────────────────────────────────────────────────
st.header("1. 客戶原始需求")

cols = st.columns(len(DEMO["cases"]))
for col, case in zip(cols, DEMO["cases"]):
    if col.button(case["title"], use_container_width=True):
        st.session_state.text = case["text"]
        reset_result()

text = st.text_area(
    "貼上 Email、LINE 或電話紀錄（合成資料）",
    value=st.session_state.text,
    height=140,
    key="input_area",
)

left, right = st.columns([1, 3])
if left.button("解析需求", type="primary", use_container_width=True):
    if not text.strip():
        st.error("請先貼上或載入一段需求文字。")
    else:
        st.session_state.text = text
        st.session_state.result = parse_request(text)
        st.session_state.confirmed = False

result: ParseResult | None = st.session_state.result
if result is None:
    st.info("載入上方任一合成案例，或貼上文字後按「解析需求」。")
    st.stop()

if result.parser_mode != "openai":
    right.info(f"已切換離線 Demo 模式：{result.parser_note or '離線規則解析'}", icon="🔌")
else:
    right.success("解析模式：OpenAI Structured Outputs（缺漏與矛盾仍由規則層複核）")

# ── 第二區：AI 結構化結果 ──────────────────────────────────────────
st.header("2. AI 結構化結果（可修改）")
req, sysf = result.request, result.system


def status_badge(field: str) -> str:
    return {"已確認": "✅ 已確認", "AI抽取": "🤖 AI 抽取",
            "不確定": "⚠️ 不確定", "未提供": "➖ 未提供"}.get(
        sysf.status_by_field.get(field, "未提供"), "➖ 未提供")


def dims_text(d: Dimensions | None) -> str:
    if not d:
        return ""
    parts = [str(v) for v in (d.length_mm, d.width_mm, d.height_mm) if v is not None]
    return " × ".join(parts) + " mm" if parts else ""


def field_row(label: str, field: str, widget):
    a, b = st.columns([3, 1])
    with a:
        value = widget()
    b.caption(f"{status_badge(field)}")
    ev = sysf.evidence_by_field.get(field)
    if ev:
        b.caption(f"原文：「{ev}」")
    return value


c1, c2 = st.columns(2)
with c1:
    st.subheader("產品與情境")
    cats = TAXONOMY["product_categories_supported"] + TAXONOMY["product_categories_future"]
    req.product_category = field_row("產品類別", "product_category", lambda: st.selectbox(
        "產品類別", ["（未提供）"] + cats,
        index=(cats.index(req.product_category) + 1) if req.product_category in cats else 0))
    if req.product_category == "（未提供）":
        req.product_category = None
    req.contents = field_row("內容物", "contents", lambda: st.text_input(
        "內容物", value=req.contents or "")) or None
    req.quantity = field_row("數量", "quantity", lambda: st.number_input(
        "數量", min_value=0, value=req.quantity or 0, step=100)) or None
    st.text_input("內容物尺寸", value=dims_text(req.product_dimensions),
                  disabled=True, help="唯讀：尺寸由解析層負責，避免手改造成單位不一致")
    st.text_input("包裝成品尺寸", value=dims_text(req.package_dimensions), disabled=True)
    if req.dimensions_unclassified:
        st.text_input("尺寸（歸屬不明）", value=dims_text(req.dimensions_unclassified),
                      disabled=True, help="前後文未指明是內容物還是包裝尺寸")

with c2:
    st.subheader("規格與交付")
    boxes = TAXONOMY["box_types"]
    req.box_type = field_row("盒型", "box_type", lambda: st.selectbox(
        "盒型", ["（未提供）"] + boxes,
        index=(boxes.index(req.box_type) + 1) if req.box_type in boxes else 0))
    if req.box_type == "（未提供）":
        req.box_type = None
    req.material_direction = field_row("紙材", "material_direction", lambda: st.text_input(
        "紙材", value=req.material_direction or "")) or None
    req.finishes = field_row("表面加工", "finishes", lambda: st.multiselect(
        "表面加工", TAXONOMY["finishes"], default=req.finishes))
    arts = TAXONOMY["artwork_status"]
    req.artwork_status = field_row("設計稿", "artwork_status", lambda: st.selectbox(
        "設計稿狀態", ["（未提供）"] + arts,
        index=(arts.index(req.artwork_status) + 1) if req.artwork_status in arts else 0))
    if req.artwork_status == "（未提供）":
        req.artwork_status = None
    req.requested_delivery_date = field_row("交期", "requested_delivery_date",
        lambda: st.text_input("交期（ISO；不完整日期留空）",
                              value=req.requested_delivery_date or "")) or None
    if req.delivery_date_original:
        st.caption(f"交期原文保留：「{req.delivery_date_original}」")
    req.delivery_location = st.text_input("交貨地點", value=req.delivery_location or "") or None

if req.preferences:
    st.info("**客戶偏好（不轉成材料或預算）**：" + "、".join(req.preferences))

st.session_state.result = validate(result)  # 改動後即時重算完整度與狀態

# ── 第三區：檢查與下一步 ───────────────────────────────────────────
st.header("3. 檢查與下一步")
sysf = st.session_state.result.system

m1, m2, m3 = st.columns(3)
m1.metric("資料完整度", sysf.data_completeness)
m2.metric("待補欄位", len(sysf.missing_fields))
m3.metric("矛盾", len(sysf.conflicts))

if sysf.conflicts:
    for c in sysf.conflicts:
        st.error(f"**矛盾｜{c.field}**：出現 {' 與 '.join(c.values)}，"
                 f"系統不代為選擇。原文：「{c.evidence}」", icon="🚨")
if sysf.ambiguous_fields:
    for a in sysf.ambiguous_fields:
        st.warning(f"**不確定｜{a.field}**：{a.reason}（原文：「{a.evidence}」）", icon="❓")
if sysf.risk_notes:
    for n in sysf.risk_notes:
        st.warning(f"**風險**：{n}", icon="⚠️")
if sysf.missing_fields:
    st.markdown("**待補資料**：" + "、".join(sysf.missing_fields))

st.divider()
b1, b2, b3 = st.columns(3)

if b1.button("產生客戶追問訊息", use_container_width=True):
    st.text_area("可直接複製給客戶", build_followup_message(st.session_state.result), height=110)

if b2.button("人工確認", type="primary", use_container_width=True):
    st.session_state.confirmed = True

if st.session_state.confirmed:
    st.success("已人工確認。ERP 草稿資料已準備（Demo 不連線 ERP）。", icon="✅")
    payload = build_export(st.session_state.result, confirmed=True)
    b3.download_button("匯出 JSON", json.dumps(payload, ensure_ascii=False, indent=2),
                       file_name="intake_request.json", mime="application/json",
                       use_container_width=True)
    with st.expander("匯出內容預覽"):
        st.json(payload)
else:
    b3.button("匯出 JSON", disabled=True, use_container_width=True,
              help="必須先人工確認才能匯出")
    st.caption("未經人工確認不得匯出——AI 整理完成不等於業務確認完成。")
