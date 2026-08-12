"""確定性規則層：抽取、換算、缺漏、矛盾、模糊。

這裡是系統的底座——LLM 是加強層，這一層是可信層。防呆規則對照
docs/DATA_SCHEMA.md：沒寫就 None、尺寸分開、單位換算保留原文、
偏好不轉材料、矛盾不取捨、日期不明確不產生。
"""
from __future__ import annotations

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

CATEGORIES = ["彩盒", "禮盒", "紙盒", "紙箱", "紙袋", "名片", "貼紙", "書冊", "大圖"]
SUPPORTED = {"彩盒", "禮盒", "紙盒"}
CONTENTS_HINTS = ["保養品", "食品", "電子零件", "茶葉", "月餅", "蛋糕", "飾品", "3C", "化妝品"]
FINISH_HINTS = ["霧膜", "亮膜", "局部UV", "局部 UV", "燙金", "壓紋", "開窗", "上光"]
BOX_TYPE_HINTS = ["天地盒", "磁吸盒", "抽屜盒", "書型盒", "袖套盒", "托盤盒", "天地蓋"]
MATERIAL_HINTS = ["白卡", "灰銅", "白銅", "牛皮", "裱浪", "灰板"]
PREFERENCE_HINTS = ["高級", "質感", "不要太貴", "環保", "便宜", "精緻"]
AMBIG_MARKERS = ["大約", "左右", "上下", "約"]

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


def to_mm(value: float, unit: str) -> float:
    return round(value * UNIT_TO_MM[unit], 2)


def _norm(n: float) -> float:
    return int(n) if float(n).is_integer() else n


def extract_triple_dimensions(text: str):
    """抓「5×5×12 公分」形式。回 (Dimensions, 前文脈絡)。"""
    pat = re.compile(
        r"([\d.]+)\s*[×xX*]\s*([\d.]+)\s*[×xX*]\s*([\d.]+)\s*" + UNIT_PAT
    )
    m = pat.search(text)
    if not m:
        return None, ""
    unit = m.group(4)
    dims = Dimensions(
        length_mm=_norm(to_mm(float(m.group(1)), unit)),
        width_mm=_norm(to_mm(float(m.group(2)), unit)),
        height_mm=_norm(to_mm(float(m.group(3)), unit)),
        original_text=m.group(0),
    )
    context = text[max(0, m.start() - 12): m.start()]
    return dims, context


def extract_labeled_dimensions(text: str):
    """抓「寬 50 mm、高 12 cm、深度大約 0.08 m」形式。"""
    pat = re.compile(r"(長|寬|高|深度|深)\s*(?:大約|約)?\s*([\d.]+)\s*" + UNIT_PAT)
    found = pat.findall(text)
    if not found:
        return None
    mapping = {"長": "length_mm", "寬": "width_mm", "高": "height_mm", "深度": "length_mm", "深": "length_mm"}
    dims = Dimensions(original_text="；".join(f"{a}{b}{c}" for a, b, c in found))
    for label, num, unit in found:
        setattr(dims, mapping[label], _norm(to_mm(float(num), unit)))
    return dims


def extract_quantities(text: str) -> list[tuple[int, str]]:
    """回 (數量, 原文) 清單。只認「N 個/組/盒/份」，避免吃到尺寸數字。"""
    out = []
    for m in re.finditer(r"([\d,]+)\s*(個|組|盒|份|pcs)", text):
        out.append((int(m.group(1).replace(",", "")), m.group(0)))
    return out


def extract_date(text: str):
    """完整年月日 → ISO；只有月日或「下月底」→ 保留原文、不產生日期（防呆 6）。"""
    m = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}", m.group(0)
    m = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})?\s*日?\s*(前|底|初)?", text)
    if m and ("月" in m.group(0)):
        return None, m.group(0)
    m = re.search(r"(下月底|月底前|下個月|盡快|越快越好)", text)
    if m:
        return None, m.group(0)
    return None, None


def rules_parse(text: str) -> ParseResult:
    """離線規則解析——整個系統的可信底座，斷網照樣能跑。"""
    req = PackagingRequest(raw_request=text)
    sysf = SystemFields()
    ev = sysf.evidence_by_field

    for c in CATEGORIES:
        if c in text:
            req.product_category = c
            ev["product_category"] = c
            break
    for c in CONTENTS_HINTS:
        if c in text:
            req.contents = c
            ev["contents"] = c
            break

    qs = extract_quantities(text)
    uniq = sorted({q for q, _ in qs})
    if len(uniq) == 1:
        req.quantity = uniq[0]
        ev["quantity"] = qs[0][1]
    elif len(uniq) > 1:
        # 防呆 5：同欄位兩個值＝衝突，不取捨
        sysf.conflicts.append(
            Conflict(field="quantity", values=[str(q) for q in uniq],
                     evidence="；".join(t for _, t in qs))
        )

    dims, context = extract_triple_dimensions(text)
    if dims is None:
        dims = extract_labeled_dimensions(text)
        context = text[:14] if dims else ""
    if dims:
        if re.search(r"(產品|內容物|商品|本身)", context):
            req.product_dimensions = dims
            ev["product_dimensions"] = dims.original_text or ""
        elif re.search(r"(外盒|包裝|成品|盒子)", context):
            req.package_dimensions = dims
            ev["package_dimensions"] = dims.original_text or ""
        else:
            req.dimensions_unclassified = dims
            sysf.ambiguous_fields.append(Ambiguity(
                field="dimensions", reason="無法判定是內容物尺寸還是包裝尺寸",
                evidence=dims.original_text or ""))

    for f in FINISH_HINTS:
        if f in text:
            name = f.replace("局部 UV", "局部UV")
            if name not in req.finishes:
                req.finishes.append(name)
    if req.finishes:
        ev["finishes"] = "、".join(req.finishes)
    for b in BOX_TYPE_HINTS:
        if b in text:
            req.box_type = b
            ev["box_type"] = b
            break
    for mtl in MATERIAL_HINTS:
        # 防呆 4：「還不確定」「先評估」不指定材料
        if mtl in text and not re.search(mtl + r".{0,6}(不確定|未定|再評估|先評估)", text):
            req.material_direction = mtl
            ev["material_direction"] = mtl
            break

    if re.search(r"(AI|ai)\s*(設計)?檔", text):
        req.artwork_status = "已有AI設計檔"
        ev["artwork_status"] = re.search(r".{0,6}(AI|ai)\s*(設計)?檔", text).group(0)
    elif re.search(r"(還沒|尚未)設計", text):
        req.artwork_status = "尚未設計"

    iso, original = extract_date(text)
    req.requested_delivery_date = iso
    req.delivery_date_original = original
    if iso:
        ev["requested_delivery_date"] = original or iso
    elif original:
        sysf.ambiguous_fields.append(Ambiguity(
            field="requested_delivery_date", reason="日期不完整，僅保留原文，不產生日期",
            evidence=original))

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

    result = ParseResult(request=req, system=sysf, parser_mode="offline_rules")
    return validate(result)


def validate(result: ParseResult) -> ParseResult:
    """對任何來源（LLM 或規則）的結果做確定性複核。"""
    req, sysf = result.request, result.system

    ambiguous_names = {a.field for a in sysf.ambiguous_fields}
    conflict_names = {c.field for c in sysf.conflicts}
    missing = []
    filled = 0
    for attr, label in KEY_FIELDS:
        v = getattr(req, attr)
        empty = v in (None, [], "")
        if empty:
            missing.append(label)
        else:
            filled += 1
        # 逐欄狀態四值：已確認由 UI 覆寫，這裡只給初始三值
        if attr in conflict_names or attr in ambiguous_names:
            sysf.status_by_field[attr] = "不確定"
        elif empty:
            sysf.status_by_field[attr] = "未提供"
        else:
            sysf.status_by_field[attr] = "AI抽取"
    sysf.missing_fields = missing
    sysf.data_completeness = f"{filled}/{len(KEY_FIELDS)}"

    # 防呆 2：只有內容物尺寸時，明確標風險
    if req.product_dimensions and not req.package_dimensions:
        note = "內容物尺寸不等於包裝成品尺寸，不可直接沿用"
        if note not in sysf.risk_notes:
            sysf.risk_notes.append(note)
    if req.product_category and req.product_category not in SUPPORTED:
        note = f"「{req.product_category}」屬後續產品模組，本版僅完整支援紙盒／彩盒／禮盒"
        if note not in sysf.risk_notes:
            sysf.risk_notes.append(note)

    # 防呆 8：AI 整理完成不等於業務確認完成
    sysf.manual_review_required = True
    return result


def build_followup_message(result: ParseResult) -> str:
    items = [f for f in result.system.missing_fields]
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
    # 確認前恆 True，匯出副本才翻 False——生命週期只有這一個轉換點
    system["manual_review_required"] = False
    payload["_system"] = system
    payload["_meta"] = {
        "confirmed": True,
        "parser_mode": result.parser_mode,
        "note": "Synthetic demo data — 非正式報價",
    }
    return payload
