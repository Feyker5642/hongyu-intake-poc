"""壓力測試：規則引擎面對沒見過的說法會怎樣。

不是 pytest——這是一份誠實的體檢報告，跑出來看數字，不是拿來通過的。
案例刻意用四個 demo 案例沒出現過的講法：口語、單位變體、繞路的表達。
"""
import io
import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from rules.validator import rules_parse  # noqa: E402

# (輸入, 期望抓到什麼, 檢查函式)
CASES = [
    ("客戶要三千個彩盒，尺寸大概 20 乘 15 乘 8 公分",
     "數量 3000（中文數字）", lambda r: r.request.quantity == 3000),
    ("我們要做 5000 pcs 的禮盒，材質用 350P 白卡",
     "磅數 350", lambda r: r.request.paper_weight_gsm == 350),
    ("這批貨兩千五百盒，希望下個月十五號前到",
     "數量 2500（中文數字）", lambda r: r.request.quantity == 2500),
    ("盒子外圍是 20cm x 15cm x 8cm",
     "包裝尺寸（無空格 x 分隔）", lambda r: r.request.package_dimensions is not None),
    ("產品規格 200*150*80mm，數量一千",
     "尺寸（星號分隔）", lambda r: r.request.product_dimensions is not None),
    ("表面要做消光處理，再加個燙金",
     "消光＝霧膜", lambda r: "霧膜" in r.request.finishes),
    ("我要那種上下蓋分開的盒子",
     "天地盒（描述而非名稱）", lambda r: r.request.box_type == "天地盒"),
    ("送到台中港，出口用",
     "交貨地點 台中港", lambda r: r.request.delivery_location is not None),
    ("裡面裝的是精華液，一瓶 30ml",
     "內容物與容量", lambda r: r.request.contents is not None),
    ("Need 2000 gift boxes, 20x15x8 cm, matte lamination",
     "全英文詢價", lambda r: r.request.quantity == 2000),
    ("先做打樣一個看看，確認 OK 再下 3000",
     "打樣需求＋數量", lambda r: r.request.proofing_needed is not None),
    ("紙盒 30*20*10 公分 1000 個 白卡 300 磅 霧膜",
     "電報式全塞一行", lambda r: r.request.quantity == 1000 and r.request.paper_weight_gsm == 300),
    # 「或」型未決選項——2026-08-12 語料跑分抓到的三個缺口，引擎不得代選
    ("彩盒 2,000 或 4,000 盒，抽屜盒",
     "數量或型→矛盾不代選", lambda r: r.request.quantity is None and
     any(c.field == "quantity" for c in r.system.conflicts)),
    ("三千盒彩盒，亮膜或霧膜哪個合適再決定",
     "加工或型→不填標未決", lambda r: r.request.finishes == [] and
     any(a.field == "finishes" for a in r.system.ambiguous_fields)),
    ("800 個紙盒，交期 2026-09-30 或 2026-10-03 都可以",
     "日期或型→不挑第一個", lambda r: r.request.requested_delivery_date is None and
     r.request.delivery_date_original is not None),
]


def main():
    passed = 0
    print("=" * 74)
    for text, label, check in CASES:
        r = rules_parse(text)
        ok = False
        try:
            ok = bool(check(r))
        except Exception:
            ok = False
        passed += ok
        print(f"{'PASS' if ok else 'FAIL'}  {label}")
        if not ok:
            print(f"      輸入：{text}")
    print("=" * 74)
    print(f"規則引擎：{passed}/{len(CASES)} = {passed * 100 // len(CASES)}%")


if __name__ == "__main__":
    main()
