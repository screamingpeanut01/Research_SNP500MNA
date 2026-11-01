"""수집 상태가 '부분'인 거래의 빈 항목을 다시 찾기 위한 에이전트 입력을 만든다 (2026-11-01).

빈 항목의 정의
    수집 열의 값이 비어 있거나, '확인 안 됨'으로 시작하거나, 값 안에 '미확인'이 들어 있으면 빈 항목으로 본다.
    값의 일부만 '미확인'인 경우(예: '2014: 100억원; 2015: 미확인')도 포함한다.
    10-19 규칙이 만든 열(event_group, pre_incorp, stake)과, impairment_class로 대체된 impairment 열은 보지 않는다.

묶음
    원래 수집 묶음(nbs/ma188_collect/batches)을 깨지 않고, 기업별로 12건 안팎이 되도록 묶음을 합친다.
    같은 대상회사 계보는 한 에이전트가 함께 본다.

실행(저장소 루트): python -X utf8 nbs/ma188_recollect/make_inputs.py <출력 폴더>
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1].parent
SHEET = ROOT / "meeting" / "20261102" / "MA188_수집시트.csv"
CIQ_MAP = ROOT / "data" / "ma188_deal_ciq.csv"
BATCHES = ROOT / "nbs" / "ma188_collect" / "batches"

GAP_FIELDS = [
    "status_chk", "value_chk_local", "value_chk_usdmm", "announce_date_chk", "acquirer_entity", "purpose_quote",
    "acquirer_core", "acq_total_assets", "apex_total_assets", "deal_to_assets_pct", "deal_to_equity_pct",
    "acq_mktcap", "size_basis", "event_ticker", "first_filing_date", "pre_events_summary", "post_events_summary",
    "impairment_class", "target_rev_pre", "target_rev_post", "target_op_pre", "target_op_post", "perf_basis",
    "earnings_call_note",
]
CONTEXT = ["firm", "date", "target", "status", "value", "buyers", "sellers", "comment", "subtype_chk",
           "pre_incorp_chk", "acquirer_entity", "perf_basis", "impairment", "impairment_class_basis",
           "notes", "review_note"]
PART_SIZE = 12


def is_gap(v):
    v = str(v).strip()
    return v == "" or v.startswith("확인 안 됨") or "미확인" in v


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    d = pd.read_csv(SHEET, dtype=str, keep_default_na=False)
    to_deal = pd.read_csv(CIQ_MAP, dtype=str).set_index("ciq_id").deal_id
    d["deal_id"] = d.ciq_id.map(to_deal)
    p = d[d.collect_status == "부분"].set_index("deal_id")

    batch_of = {}
    for f in sorted(BATCHES.glob("*.json")):
        b = json.loads(f.read_text(encoding="utf-8"))
        for x in b["deals"]:
            batch_of[x["deal_id"]] = b["batch"]

    items = {}
    for did, r in p.iterrows():
        gaps = {f: r[f] for f in GAP_FIELDS if is_gap(r[f])}
        if not gaps:
            continue
        items[did] = {"deal_id": did, "ciq_id": r.ciq_id, "batch": batch_of[did],
                      "context": {c: r[c] for c in CONTEXT}, "gaps": gaps}

    # 기업별로, 원래 묶음 순서대로 PART_SIZE건을 넘기 전까지 묶음을 쌓는다.
    parts, cur, firm = [], [], None
    for b in sorted({v["batch"] for v in items.values()}):
        deals = [v for v in items.values() if v["batch"] == b]
        f = deals[0]["context"]["firm"]
        if cur and (f != firm or len(cur) + len(deals) > PART_SIZE):
            parts.append(cur)
            cur = []
        cur, firm = cur + deals, f
    parts.append(cur)

    for i, part in enumerate(parts, 1):
        (out / f"part{i}.json").write_text(json.dumps(part, ensure_ascii=False, indent=1), encoding="utf-8")
        n_gap = sum(len(x["gaps"]) for x in part)
        print(f"part{i}: {part[0]['context']['firm']} {len(part)}건, 빈 항목 {n_gap}칸, "
              f"묶음 {sorted({x['batch'] for x in part})}")
    print(f"거래 {len(items)}건, 빈 항목 {sum(len(x['gaps']) for x in items.values())}칸")


if __name__ == "__main__":
    main()
