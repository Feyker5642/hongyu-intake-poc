"""語料跑分器：100 筆合成詢價 × 離線規則引擎，對照 Codex 標註的期望值。

手動跑，不進 pytest。量的是**離線底座**的涵蓋率——LLM 路徑會更高，
但打 100 次 API 另議。不一致分兩種罪：
  FN（漏抓）：期望有值、引擎回 null——涵蓋率缺口，可接受。
  FP（誤抓）：期望 null、引擎給了值——**違反「不猜」底線，每一筆都要人工裁決**。
標註本身是 Codex 的主張；差異清單是「歧見報告」，不是判決書。
"""
import io
import json
import pathlib
import sys
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from rules.validator import rules_parse  # noqa: E402

FIELDS = [
    "product_category", "contents", "quantity", "box_type", "material_direction",
    "paper_weight_gsm", "artwork_status", "requested_delivery_date",
    "delivery_location", "budget", "proofing_needed",
]
DIM_FIELDS = ["product_dimensions", "package_dimensions", "dimensions_unclassified"]


def dims_tuple(d):
    if not d:
        return None
    if hasattr(d, "length_mm"):
        t = (d.length_mm, d.width_mm, d.height_mm)
    else:
        t = (d.get("length_mm"), d.get("width_mm"), d.get("height_mm"))
    return tuple(None if v is None else float(v) for v in t)


def norm(v):
    if isinstance(v, str):
        v = v.strip()
    return v if v not in ("", [], {}) else None


def main():
    corpus = json.load(io.open(
        pathlib.Path(__file__).parent.parent / "data" / "eval_corpus.json",
        encoding="utf-8"))["cases"]

    agree = fn = fp = diff = 0
    per_cat = defaultdict(lambda: [0, 0])  # cat -> [agree, total]
    fp_list, mism = [], []

    for case in corpus:
        exp_req = case["expected"]["request"]
        exp_conf = {c["field"] for c in case["expected"].get("system", {}).get("conflicts", [])}
        r = rules_parse(case["text"])
        got_req = r.request

        pairs = []
        for f in FIELDS:
            pairs.append((f, norm(exp_req.get(f)), norm(getattr(got_req, f))))
        for f in DIM_FIELDS:
            pairs.append((f, dims_tuple(exp_req.get(f)), dims_tuple(getattr(got_req, f))))
        pairs.append(("finishes", set(exp_req.get("finishes") or []), set(got_req.finishes)))
        pairs.append(("preferences", set(exp_req.get("preferences") or []), set(got_req.preferences)))
        pairs.append(("conflicts", exp_conf, {c.field for c in r.system.conflicts}))

        for f, e, g in pairs:
            e_empty = e in (None, set(), ())
            g_empty = g in (None, set(), ())
            per_cat[case["category"]][1] += 1
            if e == g or (e_empty and g_empty):
                agree += 1
                per_cat[case["category"]][0] += 1
            elif g_empty:
                fn += 1
                mism.append((case["id"], case["category"], f, e, "∅"))
            elif e_empty:
                fp += 1
                fp_list.append((case["id"], case["category"], f, g))
            else:
                diff += 1
                mism.append((case["id"], case["category"], f, e, g))

    total = agree + fn + fp + diff
    print(f"欄位層級一致率：{agree}/{total} = {agree * 100 // total}%")
    print(f"  漏抓 FN（期望有值、引擎 null）: {fn}")
    print(f"  誤抓 FP（期望 null、引擎有值）: {fp}   ← 違反不猜底線，逐筆裁決")
    print(f"  值不同: {diff}")
    print("\n各類別一致率：")
    for cat, (a, t) in sorted(per_cat.items(), key=lambda x: x[1][0] / x[1][1]):
        print(f"  {cat:8} {a * 100 // t}%")
    if fp_list:
        print("\nFP 全列：")
        for row in fp_list:
            print("  ", row)
    print("\n值不同（前 12 筆）：")
    for row in [m for m in mism if m[4] != "∅"][:12]:
        print("  ", row)


if __name__ == "__main__":
    main()
