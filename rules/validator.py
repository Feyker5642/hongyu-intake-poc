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
SEP = r"\s*(?:[×xX*✕╳]|乘)\s*"
# 單位可以只出現在最後（20×15×8 公分），也可以每個數字都帶（20cm x 15cm x 8cm）
TRIPLE_PAT = re.compile(
    r"([\d.]+)\s*" + UNIT_PAT + r"?" + SEP +
    r"([\d.]+)\s*" + UNIT_PAT + r"?" + SEP +
    r"([\d.]+)\s*" + UNIT_PAT + r"?")
LABELED_PAT = re.compile(r"(長|寬|高|深度|深)\s*(?:大約|約)?\s*([\d.]+)\s*" + UNIT_PAT)

CN_DIGITS = {"零": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4,
             "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNITS = {"十": 10, "百": 100, "千": 1000, "萬": 10000}


def cn_to_int(s: str):
    """把「三千」「兩千五百」「一千」轉成數字。看不懂就回 None，不猜。"""
    total, section, digit = 0, 0, 0
    for ch in s:
        if ch in CN_DIGITS:
            digit = CN_DIGITS[ch]
        elif ch in CN_UNITS:
            unit = CN_UNITS[ch]
            if unit == 10000:
                section = (section + digit) * unit
                total += section
                section = digit = 0
            else:
                section += (digit or 1) * unit
                digit = 0
        else:
            return None
    value = total + section + digit
    return value or None

CATEGORIES = ["彩盒", "禮盒", "紙盒", "紙箱", "紙袋", "名片", "貼紙", "書冊", "大圖"]
SUPPORTED = {"彩盒", "禮盒", "紙盒"}
CONTENTS_HINTS = ["保養品", "食品", "電子零件", "茶葉", "月餅", "蛋糕", "飾品", "3C",
                  "化妝品", "精華液", "面膜", "咖啡", "酒", "保健品", "手工皂"]
# 同義詞：業界口語與英文都對到同一個正式值。左邊是會出現在客戶嘴裡的說法。
FINISH_ALIASES = {
    "霧膜": ["霧膜", "消光", "霧面處理", "matte"],
    "亮膜": ["亮膜", "亮面處理", "gloss"],
    "局部UV": ["局部UV", "局部 UV", "局部上光", "spot uv"],
    "燙金": ["燙金", "燙銀", "hot stamp", "foil"],
    "壓紋": ["壓紋", "壓凸", "emboss"],
    "開窗": ["開窗", "透明窗", "window"],
}
BOX_TYPE_ALIASES = {
    "天地盒": ["天地盒", "天地蓋", "上下蓋分開", "上下蓋"],
    "磁吸盒": ["磁吸盒", "磁鐵盒", "磁吸"],
    "抽屜盒": ["抽屜盒", "抽屜式", "推拉盒"],
    "書型盒": ["書型盒", "書本盒", "翻蓋"],
    "袖套盒": ["袖套盒", "外套盒", "sleeve"],
    "托盤盒": ["托盤盒", "托盤"],
}
CATEGORY_ALIASES = {
    "彩盒": ["彩盒", "color box"],
    "禮盒": ["禮盒", "gift box"],
    "紙盒": ["紙盒", "paper box"],
    "紙箱": ["紙箱", "carton"],
    "紙袋": ["紙袋", "paper bag"],
}
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
        # 單位可能標在任一數字後面或只標最後；一個都沒有就不算尺寸
        units = [m.group(2), m.group(4), m.group(6)]
        unit = next((u for u in reversed(units) if u), None)
        if unit is None:
            continue
        nums = [m.group(1), m.group(3), m.group(5)]
        vals = [to_mm(float(n), units[i] or unit) for i, n in enumerate(nums)]
        dims = Dimensions(length_mm=vals[0], width_mm=vals[1], height_mm=vals[2],
                          original_text=m.group(0))
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
    # \b 只能掛英文量詞：中文字在 re 裡也算 \w，「個保」之間沒有邊界會使比對失敗
    out = [(int(m.group(1).replace(",", "")), m.group(0))
           for m in re.finditer(r"([\d,]+)\s*(個|組|盒|份|pcs\b|pieces\b|units?\b)", text, re.I)]
    # 「2,000 或 4,000 盒」：前一個數字沒帶量詞，上面的樣式只會抓到後者，
    # 引擎就把未決的選項當成了答案——2026-08-12 語料跑分抓到的真缺口。
    # 兩個都收，讓既有的多值→conflict 路徑接手（防呆 5：不代選）。
    for m in re.finditer(r"([\d,]+)\s*[或/]\s*([\d,]+)\s*(個|組|盒|份|pcs\b)", text, re.I):
        for g in (1, 2):
            v = int(m.group(g).replace(",", ""))
            if not any(v == q for q, _ in out):
                out.append((v, m.group(0)))
    # 中文數字：「三千個」「兩千五百盒」。量詞跟阿拉伯數字同一組。
    for m in re.finditer(r"([零一二兩三四五六七八九十百千萬]{1,6})\s*(個|組|盒|份)", text):
        v = cn_to_int(m.group(1))
        if v:
            out.append((v, m.group(0)))
    # 英文語境：「Need 2000 gift boxes」——數字直接接品名
    for m in re.finditer(r"\b([\d,]{3,})\s+(?:gift|paper|color)?\s*box(?:es)?", text, re.I):
        out.append((int(m.group(1).replace(",", "")), m.group(0)))
    # 去重：同一個位置的值只留一筆
    seen, dedup = set(), []
    for v, t in out:
        if (v, t) not in seen:
            seen.add((v, t))
            dedup.append((v, t))
    return dedup


def extract_paper_weight(text: str):
    """「350P 白卡」「300 磅」「350gsm」→ 磅數。範圍限 150–600，避免吃到數量。"""
    m = re.search(r"(\d{3})\s*(?:P\b|磅|gsm|g\b)", text, re.I)
    if m and 150 <= int(m.group(1)) <= 600:
        return int(m.group(1)), m.group(0)
    return None, None


def extract_location(text: str):
    """交貨地點：「送到／出貨到／交貨到 X」或台灣縣市名。"""
    m = re.search(r"(?:送到|出貨到|交貨到|運到|寄到)\s*([一-鿿]{2,6}?[市縣港區]?)(?:[，。,\s]|$)", text)
    if m:
        return m.group(1), m.group(0)
    m = re.search(r"(台北|新北|桃園|台中|台南|高雄|基隆|新竹|嘉義|苗栗|彰化|南投|雲林|屏東|宜蘭|花蓮|台東)(市|縣|港)?", text)
    if m:
        return m.group(0), m.group(0)
    return None, None


def extract_date(text: str):
    """完整且合法的年月日 → ISO；否則 None，原文一律保留（防呆 6）。

    兩個完整日期以「或／還是／or」相連＝未決選項，不挑第一個當答案
    （語料 050 抓到的缺口：whichever is feasible）。
    """
    full = list(re.finditer(r"\d{4}\s*[年/-]\s*\d{1,2}\s*[月/-]\s*\d{1,2}\s*日?", text))
    if len(full) >= 2:
        between = text[full[0].end():full[1].start()]
        if re.search(r"或|還是|\bor\b", between):
            return None, text[full[0].start():full[1].end()]
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


def _find_aliases(text: str, aliases: dict[str, list[str]]) -> list[tuple[str, str]]:
    """回 [(正式值, 命中的原文說法)]。英文別名不分大小寫。"""
    low = text.lower()
    hits = []
    for canon, words in aliases.items():
        for w in words:
            if (w.lower() in low) if w.isascii() else (w in text):
                hits.append((canon, w))
                break
    return hits


def _pick_or_conflict(text, hints, field, req, sysf, attr, guard=None):
    """找出所有命中值：恰一個就填，多於一個就清空並記 conflict（防呆 5）。

    hints 可以是 list（直接比對）或 dict（同義詞表：口語／英文 → 正式值）。
    """
    if isinstance(hints, dict):
        found = _find_aliases(text, hints)
        values = [c for c, _ in found]
        evidences = {c: w for c, w in found}
    else:
        values = []
        for h in hints:
            if h not in text:
                continue
            if guard and re.search(h + guard, text):
                continue  # 「白卡還不確定」不算選定
            norm = h.replace("局部 UV", "局部UV")
            if norm not in values:
                values.append(norm)
        evidences = {v: v for v in values}
    if len(values) == 1:
        setattr(req, attr, values[0])
        sysf.evidence_by_field[field] = evidences[values[0]]
    elif len(values) > 1:
        sysf.conflicts.append(Conflict(field=field, values=values,
                                       evidence="；".join(evidences[v] for v in values)))


def rules_parse(text: str) -> ParseResult:
    """離線規則解析——整個系統的可信底座，斷網照樣能跑。"""
    req = PackagingRequest(raw_request=text)
    sysf = SystemFields()
    ev = sysf.evidence_by_field

    _pick_or_conflict(text, CATEGORY_ALIASES, "product_category", req, sysf, "product_category")
    _pick_or_conflict(text, CONTENTS_HINTS, "contents", req, sysf, "contents")
    _pick_or_conflict(text, BOX_TYPE_ALIASES, "box_type", req, sysf, "box_type")
    _pick_or_conflict(text, MATERIAL_HINTS, "material_direction", req, sysf,
                      "material_direction", guard=r".{0,6}(不確定|未定|再評估|先評估)")

    gsm, gsm_ev = extract_paper_weight(text)
    if gsm:
        req.paper_weight_gsm = gsm
        ev["paper_weight_gsm"] = gsm_ev
    loc, loc_ev = extract_location(text)
    if loc:
        req.delivery_location = loc
        ev["delivery_location"] = loc_ev
    if re.search(r"打樣|打個樣|樣品先", text):
        req.proofing_needed = "是"
        ev["proofing_needed"] = re.search(r".{0,4}(打樣|打個樣|樣品先)", text).group(0)

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
        existing = getattr(req, target)
        if existing is None and not any(c.field == target for c in sysf.conflicts):
            setattr(req, target, dims)
            if target != "dimensions_unclassified":
                ev[target] = dims.original_text or ""
        else:  # 同一類出現第二組——清空該欄並記衝突，絕不代為選第一組
            prior = [c for c in sysf.conflicts if c.field == target]
            values = prior[0].values if prior else [existing.original_text or ""]
            values = values + [dims.original_text or ""]
            sysf.conflicts = [c for c in sysf.conflicts if c.field != target]
            sysf.conflicts.append(Conflict(field=target, values=values,
                                           evidence="；".join(values)))
            setattr(req, target, None)
            ev.pop(target, None)

    finish_hits = _find_aliases(text, FINISH_ALIASES)
    # 「亮膜或霧膜哪個合適再決定」：被提及 ≠ 被選定。兩個加工詞之間有
    # 「或／還是」且句中帶未決語，一律不填、標不確定（語料跑分抓到的缺口）。
    undecided = re.search(
        r"(霧膜|亮膜|消光|燙金|壓紋|開窗|局部\s*UV)\s*(?:或|還是)\s*(霧膜|亮膜|消光|燙金|壓紋|開窗|局部\s*UV)",
        text)
    if undecided and re.search(r"再決定|再說|未定|不確定|哪個|都可以|皆可", text):
        dropped = {c for c, _ in _find_aliases(undecided.group(0), FINISH_ALIASES)}
        finish_hits = [(c, w) for c, w in finish_hits if c not in dropped]
        sysf.ambiguous_fields.append(Ambiguity(
            field="finishes", reason="加工選項未決（或），不代選",
            evidence=undecided.group(0)))
    for canon, _w in finish_hits:
        if canon not in req.finishes:
            req.finishes.append(canon)
    if req.finishes:
        ev["finishes"] = "、".join(w for _, w in finish_hits)

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
