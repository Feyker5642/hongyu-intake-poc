"""語料跑分器（LLM 路徑版）：同一份 100 筆，走 parse_request 完整管線。

會打 100 次真 API——手動跑，估 10-20 分鐘。與 eval_runner.py 同一把尺，
產出可直接對照的欄位一致率；結果另存 JSON 供覆核單筆差異。
"""
import io
import json
import pathlib
import sys
import time
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from services.llm_parser import parse_request  # noqa: E402
from tests.eval_runner import DIM_FIELDS, FIELDS, dims_tuple, norm  # noqa: E402

OUT = pathlib.Path(__file__).parent.parent / "exports" / "llm_eval_results.json"


def main():
    corpus = json.load(io.open(
        pathlib.Path(__file__).parent.parent / "data" / "eval_corpus.json",
        encoding="utf-8"))["cases"]

    agree = fn = fp = diff = 0
    per_cat = defaultdict(lambda: [0, 0])
    rows = []
    llm_used = 0
    t0 = time.time()

    for i, case in enumerate(corpus, 1):
        exp_req = case["expected"]["request"]
        exp_conf = {c["field"] for c in case["expected"].get("system", {}).get("conflicts", [])}
        r = parse_request(case["text"])
        llm_used += r.parser_mode != "offline_rules"
        got = r.request

        pairs = []
        for f in FIELDS:
            pairs.append((f, norm(exp_req.get(f)), norm(getattr(got, f))))
        for f in DIM_FIELDS:
            pairs.append((f, dims_tuple(exp_req.get(f)), dims_tuple(getattr(got, f))))
        pairs.append(("finishes", set(exp_req.get("finishes") or []), set(got.finishes)))
        pairs.append(("preferences", set(exp_req.get("preferences") or []), set(got.preferences)))
        pairs.append(("conflicts", exp_conf, {c.field for c in r.system.conflicts}))

        for f, e, g in pairs:
            e0, g0 = e in (None, set(), ()), g in (None, set(), ())
            per_cat[case["category"]][1] += 1
            if e == g or (e0 and g0):
                agree += 1
                per_cat[case["category"]][0] += 1
            else:
                kind = "FN" if g0 else ("FP" if e0 else "DIFF")
                if kind == "FN":
                    fn += 1
                elif kind == "FP":
                    fp += 1
                else:
                    diff += 1
                rows.append({"id": case["id"], "cat": case["category"], "field": f,
                             "kind": kind, "expected": sorted(e) if isinstance(e, set) else e,
                             "got": sorted(g) if isinstance(g, set) else g,
                             "mode": r.parser_mode})
        if i % 10 == 0:
            print(f"[{i}/100] {int(time.time() - t0)}s", flush=True)

    total = agree + fn + fp + diff
    print(f"\nLLM 路徑欄位一致率：{agree}/{total} = {agree * 100 // total}%")
    print(f"  （{llm_used}/100 筆實際走 LLM；其餘為 API 失敗退離線）")
    print(f"  FN {fn} / FP {fp} / 值不同 {diff}")
    print("\n各類別：")
    for cat, (a, t) in sorted(per_cat.items(), key=lambda x: x[1][0] / x[1][1]):
        print(f"  {cat:8} {a * 100 // t}%")

    OUT.parent.mkdir(exist_ok=True)
    io.open(OUT, "w", encoding="utf-8").write(
        json.dumps({"agree": agree, "total": total, "llm_used": llm_used,
                    "disagreements": rows}, ensure_ascii=False, indent=1))
    print(f"\n細目已存 {OUT.name}")


if __name__ == "__main__":
    main()
