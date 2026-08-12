"""確定性規則層：抽取、換算、缺漏、矛盾、模糊。

這裡是系統的底座——LLM 是加強層，這一層是可信層。防呆規則對照
docs/DATA_SCHEMA.md：沒寫就 None、尺寸分開、單位換算保留原文、
偏好不轉材料、矛盾不取捨、日期不明確不產生。
"""
from __future__ import annotations

import datetime
import re

from schemas.packaging_request import (
    Ambiguity,
    Conflict,
    Dimensions,
    PackagingRequest,
    ParseResult,
    SystemFields,
)

UNIT_TO_MM = {"mm": 1, "公厘": 1, "毫米": 1, "cm": 10, "公分": 10, "m": 1000, "公尺": 1000, "米": 1000}
UNIT_PAT = r"(mm|cm|公分|公厘|毫米|公尺|米|m)"
TRIPLE_PAT = re.compile(r"([\d.]+)\s*[×xX*]\s*([\d.]+)\s*[×xX*]\s*([\d.]+)\s*" + UNIT_PAT)
LABELED_PAT = re.compile(r"(長|寬|高|深度|深)\s*(?:大約|約)?\s*([\d.]+)\s*" + UNIT_PAT)

CATEGORIES = ["彩盒", "禮盒", "紙盒", "紙箱", "紙袋", "名片", "貼紙", "書冊", "大圖"]
SUPPORTED = {"彩盒", "禮盒", "紙盒"}
CONTENTS_HINTS = ["保養品", "食品", "電子零件", "茶葉", "月餅", "蛋糕", "飾品", "3C", "化妝品"]
FINISH_HINTS = ["霧膜", "亮膜", "局部UV", "局部 UV", "燙金", "壓紋", "開窗", "上光"]
BOX_TYPE_HINTS = ["天地盒", "磁吸盒", "抽屜盒", "書型盒", "袖套盒", "托盤盒", "天地蓋"]
MATERIAL_HINTS = ["白卡", "灰銅", "白銅", "牛皮", "裱浪", "灰板"]
PREFERENCE_HINTS = ["高級", "質感", "不要太貴", "環保", "便宜", "精緻"]
AMBIG_MARKERS = ["大約", "左右", "上下", "約"]

PRODUCT_CTX = re.compile(r"(產品|內容物|商品|本身)")
PACKAGE_CTX = re.compile(r"(外盒|包裝|成品|盒子|外徑|內徑)")

KEY_FIELDS = [
    ("product_category", "產品類別"),
    ("contents", "內容物"),
    ("quantity", "數量"),
    ("product_dimensions", "內容物尺寸"),
    ("package_dimensions", "包裝成品尺寸"),
    ("box_type", "盒型"),
    ("material_direction", "紙材"),
    ("paper_weight_gsm", "紙張磅數"),
    ("finishes", "表面加工"),
    ("artwork_status", "設計稿狀態"),
    ("requested_delivery_date", "交期"),
    ("delivery_location", "交貨地點"),
]
# 這幾個欄位由規則層拍板，LLM 不得覆蓋（防呆 7）
RULE_AUTHORITATIVE = [
    "quantity", "product_dimensions", "package_dimensions",
    "dimensions_unclassified", "requested_delivery_date",
    "delivery_date_original", "budget", "preferences",
]


def to_mm(value: float, unit: str) -> float:
    n = value * UNIT_TO_MM[unit]
    return int(n) if float(n).is_integer() else round(n, 2)


def is_valid_date(y: int, m: int, d: int) -> bool:
    try:
        datetime.date(y, m, d)
        return True
    except ValueError:
        return False


def normalize_iso(value: str | None) -> str | None:
    """人工或 LLM 填進來的交期也要驗——不是 ISO 或不存在的日期一律清掉。"""
    if not value:
        return None
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", value.strip())
    if not m:
        return None
    y, mo, d = (int(g) for g in m.groups())
    return value.strip() if is_valid_date(y, mo, d) else None


def extract_dimension_sets(text: str) -> list[tuple[Dimensions, str]]:
    """回 [(Dimensions, 該筆前文), ...]。多組尺寸必須全部取出，不得靜默丟棄。"""
    sets: list[tuple[Dimensions, str]] = []
    prev_end = 0
    for m in TRIPLE_PAT.finditer(text):
        unit = m.group(4)
        dims = Dimensions(
            length_mm=to_mm(float(m.group(1)), unit),
            width_mm=to_mm(float(m.group(2)), unit),
            height_mm=to_mm(float(m.group(3)), unit),
            original_text=m.group(0),
        )
        sets.append((dims, text[prev_end:m.start()]))
        prev_end = m.end()
    if sets:
        return sets

    labeled = list(LABELED_PAT.finditer(text))
    if not labeled:
        return []
    mapping = {"長": "length_mm", "寬": "width_mm", "高": "height_mm",
               "深度": "length_mm", "深": "length_mm"}
    # 原文用首末 match 的位置切回原始字串，不重新拼接（保留空白、標點、「大約」）
    dims = Dimensions(original_text=text[labeled[0].start():labeled[-1].end()])
    for m in labeled:
        setattr(dims, mapping[m.group(1)], to_mm(float(m.group(2)), m.group(3)))
    return [(dims, text[:labeled[0].start()])]


def extract_quantities(text: str) -> list[tuple[int, str]]:
    return [(int(m.group(1).replace(",", "")), m.group(0))
            for m in re.finditer(r"([\d,]+)\s*(個|組|盒|份|pcs)", text)]


def extract_date(text: str):
    """完整且合法的年月日 → ISO；否則 None，原文一律保留（防呆 6）。"""
    m = re.search(r"(\d{4})\s*[年/-]\s*(\d{1,2})\s*[月/-]\s*(\d{1,2})\s*日?", text)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if is_valid_date(y, mo, d):
            return f"{y}-{mo:02d}-{d:02d}", m.group(0)
        return None, m.group(0)  # 2026-02-31 這種不存在的日期不得產生
    m = re.search(r"\d{1,2}\s*月\s*\d{0,2}\s*日?\s*[前底初]?", text)
    if m:
        return None, m.group(0)
    m = re.search(r"(下月底|月底前|下個月|盡快|越快越好)", text)
    return (None, m.group(0)) if m else (None, None)


def _pick_or_conflict(text, hints, field, req, sysf, attr, guard=None):
    """找出所有命中值：恰一個就填，多於一個就清空並記 conflict（防呆 5）。"""
    hits = []
    for h in hints:
        if h not in text:
            continue
        if guard and re.search(h + guard, text):
            continue  # 「白卡還不確定」不算選定
        norm = h.replace("局部 UV", "局部UV")
        if norm not in hits:
            hits.append(norm)
    if len(hits) == 1:
        setattr(req, attr, hits[0])
        sysf.evidence_by_field[field] = hits[0]
    elif len(hits) > 1:
        sysf.conflicts.append(Conflict(field=field, values=hits, evidence="；".join(hits)))


def rules_parse(text: str) -> ParseResult:
    """離線規則解析——整個系統的可信底座，斷網照樣能跑。"""
    req = PackagingRequest(raw_request=text)
    sysf = SystemFields()
    ev = sysf.evidence_by_field

    _pick_or_conflict(text, CATEGORIES, "product_category", req, sysf, "product_category")
    _pick_or_conflict(text, CONTENTS_HINTS, "contents", req, sysf, "contents")
    _pick_or_conflict(text, BOX_TYPE_HINTS, "box_type", req, sysf, "box_type")
    _pick_or_conflict(text, MATERIAL_HINTS, "material_direction", req, sysf,
                      "material_direction", guard=r".{0,6}(不確定|未定|再評估|先評估)")

    qs = extract_quantities(text)
    uniq = sorted({q for q, _ in qs})
    if len(uniq) == 1:
        req.quantity = uniq[0]
        ev["quantity"] = qs[0][1]
    elif len(uniq) > 1:
        sysf.conflicts.append(Conflict(field="quantity", values=[str(q) for q in uniq],
                                       evidence="；".join(t for _, t in qs)))

    for dims, context in extract_dimension_sets(text):
        if PRODUCT_CTX.search(context) and not PACKAGE_CTX.search(context):
            target = "product_dimensions"
        elif PACKAGE_CTX.search(context):
            target = "package_dimensions"
        else:
            target = "dimensions_unclassified"
            sysf.ambiguous_fields.append(Ambiguity(
                field="dimensions", reason="無法判定是內容物尺寸還是包裝尺寸",
                evidence=dims.original_text or ""))
        if getattr(req, target) is None:
            setattr(req, target, dims)
            if target != "dimensions_unclassified":
                ev[target] = dims.original_text or ""
        else:  # 同一類出現第二組——不覆蓋，標為衝突
            sysf.conflicts.append(Conflict(
                field=target, values=[getattr(req, target).original_text or "",
                                      dims.original_text or ""],
                evidence=dims.original_text or ""))

    for f in FINISH_HINTS:
        norm = f.replace("局部 UV", "局部UV")
        if f in text and norm not in req.finishes:
            req.finishes.append(norm)
    if req.finishes:
        ev["finishes"] = "、".join(req.finishes)

    if re.search(r"(AI|ai)\s*(設計)?檔", text):
        req.artwork_status = "已有AI設計檔"
        ev["artwork_status"] = re.search(r".{0,6}(AI|ai)\s*(設計)?檔", text).group(0)
    elif re.search(r"(還沒|尚未)設計", text):
        req.artwork_status = "尚未設計"
        ev["artwork_status"] = "尚未設計"

    iso, original = extract_date(text)
    req.requested_delivery_date = iso
    req.delivery_date_original = original
    if iso:
        ev["requested_delivery_date"] = original or iso
    elif original:
        sysf.ambiguous_fields.append(Ambiguity(
            field="requested_delivery_date",
            reason="日期不完整或不存在，僅保留原文，不產生日期", evidence=original))

    for p in PREFERENCE_HINTS:
        if p in text and p not in req.preferences:
            req.preferences.append(p)
    for marker in AMBIG_MARKERS:
        if marker in text:
            sysf.ambiguous_fields.append(Ambiguity(
                field="general", reason=f"含約略語「{marker}」", evidence=marker))
            break

    m = re.search(r"預算.{0,4}?([\d,]+)\s*(元|萬)", text)
    if m:
        req.budget = m.group(0)
        ev["budget"] = m.group(0)

    return validate(ParseResult(request=req, system=sysf, parser_mode="offline_rules"))


def validate(result: ParseResult, confirmed_fields: set[str] | None = None) -> ParseResult:
    """對任何來源（LLM 或規則）的結果做確定性複核。

    confirmed_fields：使用者人工改過的欄位——清掉該欄的舊 conflict/ambiguity，
    狀態改「已確認」，並移除已失效的 AI 原文依據。
    """
    req, sysf = result.request, result.system
    confirmed_fields = confirmed_fields or set()

    for f in confirmed_fields:
        sysf.conflicts = [c for c in sysf.conflicts if c.field != f]
        sysf.ambiguous_fields = [a for a in sysf.ambiguous_fields if a.field != f]
        sysf.evidence_by_field.pop(f, None)

    # 交期不論來自 LLM 還是人工輸入都要驗
    if req.requested_delivery_date and not normalize_iso(req.requested_delivery_date):
        bad = req.requested_delivery_date
        req.requested_delivery_date = None
        sysf.ambiguous_fields.append(Ambiguity(
            field="requested_delivery_date", reason="不是合法的 ISO 日期，已清空", evidence=bad))

    ambiguous_names = {a.field for a in sysf.ambiguous_fields}
    conflict_names = {c.field for c in sysf.conflicts}
    missing, filled = [], 0
    for attr, label in KEY_FIELDS:
        v = getattr(req, attr)
        empty = v in (None, [], "")
        if empty:
            missing.append(label)
        else:
            filled += 1
        if attr in confirmed_fields:
            sysf.status_by_field[attr] = "已確認"
        elif attr in conflict_names or attr in ambiguous_names:
            sysf.status_by_field[attr] = "不確定"
        else:
            sysf.status_by_field[attr] = "未提供" if empty else "AI抽取"
    sysf.missing_fields = missing
    sysf.data_completeness = f"{filled}/{len(KEY_FIELDS)}"

    sysf.risk_notes = []
    if req.product_dimensions and not req.package_dimensions:
        sysf.risk_notes.append("內容物尺寸不等於包裝成品尺寸，不可直接沿用")
    if req.dimensions_unclassified:
        sysf.risk_notes.append("有一組尺寸無法判定歸屬，未填入任何尺寸欄位")
    if req.product_category and req.product_category not in SUPPORTED:
        sysf.risk_notes.append(
            f"「{req.product_category}」屬後續產品模組，本版僅完整支援紙盒／彩盒／禮盒")

    sysf.manual_review_required = True
    return result


def build_followup_message(result: ParseResult) -> str:
    items = result.system.missing_fields
    listed = "、".join(items[:6]) if items else "無"
    msg = f"您好，為利進一步評估，再請協助確認：{listed}。"
    if "紙材" in listed or "盒型" in listed:
        msg += "若材質尚未確定，也可提供預算與期望質感，由專員協助建議。"
    return msg


def build_export(result: ParseResult, confirmed: bool) -> dict:
    """防呆 8/9：未人工確認不得匯出，也不得模擬 ERP 寫入。"""
    if not confirmed:
        raise PermissionError("尚未人工確認，不能匯出")
    payload = result.request.model_dump()
    system = result.system.model_dump()
    system["manual_review_required"] = False  # 生命週期唯一轉換點
    payload["_system"] = system
    payload["_meta"] = {
        "confirmed": True,
        "parser_mode": result.parser_mode,
        "note": "Synthetic demo data — 非正式報價",
    }
    return payload
