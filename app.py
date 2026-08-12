"""宏宇工藝 AI 詢價轉單助手 — Concept Demo（Streamlit 單頁）。

三區：原始需求 → AI 結構化結果（可編輯）→ 檢查與下一步。
沒有金鑰也能完整展示：解析自動落回離線規則引擎。

狀態規則：任何影響匯出內容的修改都會撤銷人工確認；改動原文還會作廢舊解析。
"""
from __future__ import annotations

import json
import pathlib

import streamlit as st

from rules.validator import build_export, build_followup_message, normalize_iso, validate
from schemas.packaging_request import Dimensions, ParseResult
from services.llm_parser import parse_request

ROOT = pathlib.Path(__file__).parent
DEMO = json.loads((ROOT / "data" / "demo_cases.json").read_text(encoding="utf-8"))
TAXONOMY = json.loads((ROOT / "data" / "public_taxonomy.json").read_text(encoding="utf-8"))
NONE = "（未提供）"

st.set_page_config(page_title="宏宇工藝 AI 詢價轉單助手", page_icon="📦", layout="wide")

# 設計語彙：印刷業的客戶看得出版面有沒有被在乎。字級層次、留白、
# 狀態色票（紅=缺、琥珀=疑、藍=AI、綠=人）全部集中在這裡。
st.markdown("""<style>
.block-container { padding-top: 2.2rem; max-width: 1150px; }
h1 { font-size: 1.72rem !important; letter-spacing: .01em; }
.hy-chips { display:flex; gap:8px; flex-wrap:wrap; margin:.2rem 0 .9rem; }
.hy-chip { font-size:.78rem; padding:3px 12px; border-radius:999px;
  background:#F1EFE8; color:#444441; border:1px solid #D3D1C7; }
.hy-chip.warn { background:#FAEEDA; color:#854F0B; border-color:#FAC775; }
.hy-note { font-size:.82rem; color:#5F5E5A; margin-bottom:1.1rem; }
.hy-sec { display:flex; align-items:center; gap:10px; margin:1.6rem 0 .6rem; }
.hy-sec .n { width:26px; height:26px; border-radius:50%; background:#0F6E56;
  color:#fff; font-size:.85rem; display:flex; align-items:center; justify-content:center; }
.hy-sec .t { font-size:1.12rem; font-weight:600; }
.hy-badge { display:inline-block; font-size:.74rem; padding:2px 10px;
  border-radius:999px; white-space:nowrap; }
.hy-none    { background:#FCEBEB; color:#A32D2D; border:1px solid #F7C1C1; }
.hy-ai      { background:#E6F1FB; color:#185FA5; border:1px solid #B5D4F4; }
.hy-unsure  { background:#FAEEDA; color:#854F0B; border:1px solid #FAC775; }
.hy-human   { background:#EAF3DE; color:#3B6D11; border:1px solid #C0DD97; }
.hy-ev { font-size:.74rem; color:#888780; }
.hy-missing-item { color:#A32D2D; font-weight:600; }
</style>""", unsafe_allow_html=True)

st.title("宏宇工藝 AI 詢價轉單助手")
st.markdown(
    '<div class="hy-chips">'
    '<span class="hy-chip warn">Concept Demo</span>'
    '<span class="hy-chip warn">全部使用合成資料</span>'
    '<span class="hy-chip warn">非正式報價系統</span>'
    '<span class="hy-chip">ERP 前的詢價整理層</span>'
    "</div>"
    '<div class="hy-note">欄位定義整理自公開同業表單，不代表宏宇實際材料、價格或產能。'
    "請勿輸入真實客戶個資或機密價格。</div>",
    unsafe_allow_html=True,
)


def section(n: int, title: str):
    st.markdown(f'<div class="hy-sec"><div class="n">{n}</div>'
                f'<div class="t">{title}</div></div>', unsafe_allow_html=True)

for key, default in [("result", None), ("confirmed", False),
                     ("text", ""), ("edited", set())]:
    st.session_state.setdefault(key, default)


def on_text_change():
    """改原文 → 舊解析立即作廢，不可能用新原文配舊結果匯出。"""
    st.session_state.result = None
    st.session_state.confirmed = False
    st.session_state.edited = set()


def on_field_change(field: str):
    """改任何欄位 → 撤銷確認，該欄標為已確認並清掉它的舊矛盾與依據。

    非法日期在這裡就清掉：回呼跑在重繪之前，是唯一能改 widget 狀態的時機，
    也才能保證畫面上確認的值跟匯出的值是同一份。
    """
    st.session_state.confirmed = False
    st.session_state.edited = set(st.session_state.edited) | {field}
    if field == "requested_delivery_date":
        raw = st.session_state.get("w_requested_delivery_date") or ""
        if raw and not normalize_iso(raw):
            st.session_state["w_requested_delivery_date"] = ""
            st.session_state["date_rejected"] = raw


def load_case(text: str):
    st.session_state.text = text
    on_text_change()


# ── 第一區：原始需求 ────────────────────────────────────────────────
section(1, "客戶原始需求")

# 正式導入時，需求從既有管道自動流入——宏宇官網本來就有客戶詢問表單。
# Demo 階段用選單標示來源、用貼上模擬內容；接管道是之後的工程，不是這一版。
src = st.radio("來源管道", ["官網詢問單", "Email", "LINE", "電話紀錄"],
               horizontal=True, key="w_source_channel")
st.caption("正式導入時由這些管道自動接入（官網表單目前收：姓名／公司、電話、"
           "需求項目、詳細描述——正好是結構化前的原始輸入）。Demo 以貼上文字模擬。")

cols = st.columns(len(DEMO["cases"]))
for col, case in zip(cols, DEMO["cases"]):
    col.button(case["title"], use_container_width=True,
               on_click=load_case, args=(case["text"],), key=f"case_{case['id']}")

st.text_area(f"模擬從「{src}」收到的內容（合成資料）", height=140,
             key="text", on_change=on_text_change)

left, right = st.columns([1, 3])
if left.button("解析需求", type="primary", use_container_width=True):
    if not st.session_state.text.strip():
        st.error("請先貼上或載入一段需求文字。")
    else:
        st.session_state.result = parse_request(st.session_state.text)
        st.session_state.result.request.source_channel = src
        st.session_state.confirmed = False
        st.session_state.edited = set()

result: ParseResult | None = st.session_state.result
if result is None:
    st.info("載入上方任一合成案例，或貼上文字後按「解析需求」。")
    st.stop()

if result.parser_mode == "deepseek":
    right.success("解析模式：DeepSeek（JSON 模式；數字、尺寸、日期仍以規則層為準）")
elif result.parser_mode == "openai":
    right.success("解析模式：OpenAI Structured Outputs（數字、尺寸、日期仍以規則層為準）")
else:
    right.info(f"已切換離線 Demo 模式：{result.parser_note or '離線規則解析'}", icon="🔌")

# ── 第二區：AI 結構化結果 ──────────────────────────────────────────
section(2, "AI 結構化結果（可修改）")
req, sysf = result.request, result.system
# 未提供＝紅：這一欄就是要刺眼，它是業務接下來要追的東西
BADGE = {"已確認": '<span class="hy-badge hy-human">已確認</span>',
         "AI抽取": '<span class="hy-badge hy-ai">AI 抽取</span>',
         "不確定": '<span class="hy-badge hy-unsure">不確定</span>',
         "未提供": '<span class="hy-badge hy-none">未提供</span>'}


def meta(col, field: str):
    status = sysf.status_by_field.get(field, "未提供")
    ev = sysf.evidence_by_field.get(field)
    html = BADGE[status]
    if ev:
        html += f'<div class="hy-ev">原文：「{ev}」</div>'
    col.markdown(html, unsafe_allow_html=True)


def select_field(label, field, options, current):
    a, b = st.columns([3, 1])
    idx = options.index(current) + 1 if current in options else 0
    with a:
        picked = st.selectbox(label, [NONE] + options, index=idx,
                              key=f"w_{field}", on_change=on_field_change, args=(field,))
    meta(b, field)
    return None if picked == NONE else picked


def text_field(label, field, current, **kw):
    a, b = st.columns([3, 1])
    with a:
        v = st.text_input(label, value=current or "", key=f"w_{field}",
                          on_change=on_field_change, args=(field,), **kw)
    meta(b, field)
    return v or None


def dims_editor(label, field, dims: Dimensions | None) -> Dimensions | None:
    st.markdown(f"**{label}**　{BADGE[sysf.status_by_field.get(field, '未提供')]}",
                unsafe_allow_html=True)
    c = st.columns(3)
    vals = []
    for i, (name, attr) in enumerate([("長", "length_mm"), ("寬", "width_mm"), ("高", "height_mm")]):
        cur = getattr(dims, attr, None) if dims else None
        vals.append(c[i].number_input(
            f"{name} (mm)", min_value=0.0, step=1.0,
            value=float(cur) if cur is not None else None, placeholder="未提供",
            key=f"w_{field}_{attr}", on_change=on_field_change, args=(field,)))
    if dims and dims.original_text:
        st.caption(f"原文（唯讀）：「{dims.original_text}」")
    if not any(v for v in vals if v):
        return None
    return Dimensions(length_mm=vals[0] or None, width_mm=vals[1] or None,
                      height_mm=vals[2] or None,
                      original_text=dims.original_text if dims else None)


c1, c2 = st.columns(2)
with c1:
    st.subheader("產品與情境")
    cats = TAXONOMY["product_categories_supported"] + TAXONOMY["product_categories_future"]
    req.product_category = select_field("產品類別", "product_category", cats, req.product_category)
    req.contents = text_field("內容物", "contents", req.contents)
    a, b = st.columns([3, 1])
    with a:
        # value=None 讓「未提供」在畫面上就是空白，不是 0——畫面必須跟匯出一致
        q = st.number_input("數量", min_value=0, step=100, value=req.quantity,
                            placeholder="未提供", key="w_quantity",
                            on_change=on_field_change, args=("quantity",))
    meta(b, "quantity")
    req.quantity = int(q) if q else None
    req.product_dimensions = dims_editor("內容物尺寸", "product_dimensions", req.product_dimensions)
    req.package_dimensions = dims_editor("包裝成品尺寸", "package_dimensions", req.package_dimensions)
    if req.dimensions_unclassified:
        st.caption(f"⚠️ 尺寸歸屬不明，未填入任何尺寸欄："
                   f"「{req.dimensions_unclassified.original_text}」")

with c2:
    st.subheader("規格與交付")
    req.box_type = select_field("盒型", "box_type", TAXONOMY["box_types"], req.box_type)
    req.material_direction = text_field("紙材", "material_direction", req.material_direction)
    a, b = st.columns([3, 1])
    with a:
        # default 含字典外的值會讓 multiselect 直接拋例外——過濾是保命符
        safe_defaults = [f for f in req.finishes if f in TAXONOMY["finishes"]]
        req.finishes = st.multiselect("表面加工", TAXONOMY["finishes"], default=safe_defaults,
                                      key="w_finishes", on_change=on_field_change,
                                      args=("finishes",))
    meta(b, "finishes")
    req.artwork_status = select_field("設計稿狀態", "artwork_status",
                                      TAXONOMY["artwork_status"], req.artwork_status)
    req.requested_delivery_date = text_field(
        "交期（ISO 例 2026-09-30；不完整請留空）", "requested_delivery_date",
        req.requested_delivery_date)
    if req.delivery_date_original:
        st.caption(f"交期原文保留：「{req.delivery_date_original}」")
    req.delivery_location = text_field("交貨地點", "delivery_location", req.delivery_location)

if req.preferences:
    st.info("**客戶偏好（不轉成材料或預算）**：" + "、".join(req.preferences))

if st.session_state.pop("date_rejected", None):
    st.error("交期不是合法的 ISO 日期（例如 2026-02-31 並不存在），已清空。"
             "原文仍保留在下方。", icon="🚫")

st.session_state.result = validate(result, confirmed_fields=set(st.session_state.edited))

# ── 第三區：檢查與下一步 ───────────────────────────────────────────
section(3, "檢查與下一步")
sysf = st.session_state.result.system
filled, total = (int(x) for x in sysf.data_completeness.split("/"))
m1, m2, m3 = st.columns([2, 1, 1])
with m1:
    st.caption(f"資料完整度 {sysf.data_completeness}")
    st.progress(filled / total)
m2.metric("待補欄位", len(sysf.missing_fields))
m3.metric("矛盾", len(sysf.conflicts))

for c in sysf.conflicts:
    st.error(f"**矛盾｜{c.field}**：出現 {' 與 '.join(c.values)}，系統不代為選擇。"
             f"原文：「{c.evidence}」", icon="🚨")
for a_ in sysf.ambiguous_fields:
    st.warning(f"**不確定｜{a_.field}**：{a_.reason}（原文：「{a_.evidence}」）", icon="❓")
for n in sysf.risk_notes:
    st.warning(f"**風險**：{n}", icon="⚠️")
if sysf.missing_fields:
    st.markdown("**待補資料**：" +
                "、".join(f'<span class="hy-missing-item">{f}</span>'
                          for f in sysf.missing_fields),
                unsafe_allow_html=True)

st.divider()
b1, b2, b3 = st.columns(3)
if b1.button("產生客戶追問訊息", use_container_width=True):
    st.text_area("可直接複製給客戶",
                 build_followup_message(st.session_state.result), height=110)
b2.button("人工確認", type="primary", use_container_width=True,
          on_click=lambda: st.session_state.update(confirmed=True))

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
    st.caption("未經人工確認不得匯出；任何修改都會撤銷確認，需要重新確認。")
