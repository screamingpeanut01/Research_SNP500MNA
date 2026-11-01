"""2차 재수집 입력: 1차 재수집 뒤에도 채우지 못한 칸만 골라 에이전트 입력을 만든다 (2026-11-01).

대상
    data/ma188_missing_fields.csv에서 분류가 '미완'이고 재시도 결과가 '채움'이 아닌 칸(못 찾음, 일부 채움).
    여기에 빈 항목 정의에 걸리지 않았지만 수집 메모가 '부분' 사유로 든 칸(EXTRA)을 더한다.
칸마다 지금 값과, 1차 재수집에서 이미 연 출처(reason)를 함께 넘겨 같은 출처를 다시 열지 않게 한다.

묶음
    어닝콜·IR 언급(earnings_call_note)은 기업별로 한 에이전트(ir_<기업>.json)가 맡는다.
    같은 실적발표 자료를 여러 거래가 함께 쓰므로, 자료를 한 번 열어 그 기업의 거래를 모두 확인하게 한다.
    나머지 칸은 1차 재수집의 묶음(work/inputs/part*.json) 순서를 따라, 기업별로 PART_SIZE건 안팎씩 묶는다.
    기업의 마지막 묶음이 MIN_PART건보다 작으면 앞 묶음에 붙인다.

실행(저장소 루트): python -X utf8 nbs/ma188_recollect/make_inputs_r2.py <출력 폴더>
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MISS = ROOT / "data" / "ma188_missing_fields.csv"
SHEET = ROOT / "meeting" / "20261102" / "MA188_수집시트.csv"
CIQ_MAP = ROOT / "data" / "ma188_deal_ciq.csv"
R1_INPUTS = Path(__file__).resolve().parent / "work" / "inputs"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_inputs import CONTEXT  # noqa: E402

# 빈 항목 정의('미확인' 문자열)에 걸리지 않았지만 메모가 '부분' 사유로 든 칸
EXTRA = {
    ("IQTR404659267", "acq_mktcap"): "수집 메모: LINE의 2016-10-12 일별 종가를 구하지 못해 월간 고저가로 범위만 추정함"
                                     "(Yahoo Finance에 상장폐지 종목 없음, Wayback 스냅샷 없음)",
}
PART_SIZE = 11
MIN_PART = 4
IR_FIELD = "earnings_call_note"


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    m = pd.read_csv(MISS, dtype=str, keep_default_na=False)
    d = pd.read_csv(SHEET, dtype=str, keep_default_na=False).set_index("ciq_id")
    to_deal = pd.read_csv(CIQ_MAP, dtype=str).set_index("ciq_id").deal_id

    left = m[(m["class"] == "미완") & (m.retry != "채움")]
    targets = {}
    for r in left.itertuples():
        targets.setdefault(r.ciq_id, []).append(
            {"field": r.field, "value_now": d.loc[r.ciq_id, r.field], "tried_r1": r.reason})
    for (cid, f), why in EXTRA.items():
        targets.setdefault(cid, []).append({"field": f, "value_now": d.loc[cid, f], "tried_r1": why})

    order = {}
    for f in sorted(R1_INPUTS.glob("part*.json"), key=lambda p: int(p.stem[4:])):
        for i, x in enumerate(json.loads(f.read_text(encoding="utf-8"))):
            order[x["ciq_id"]] = (int(f.stem[4:]), i)

    def deal(cid, t):
        return {"deal_id": to_deal[cid], "ciq_id": cid, "context": {c: d.loc[cid, c] for c in CONTEXT}, "targets": t}

    key = lambda v: (v["context"]["firm"], order.get(v["ciq_id"], (99, 0)))  # noqa: E731
    ir = sorted([deal(c, [x for x in t if x["field"] == IR_FIELD]) for c, t in targets.items()
                 if any(x["field"] == IR_FIELD for x in t)], key=key)
    rest = sorted([deal(c, [x for x in t if x["field"] != IR_FIELD]) for c, t in targets.items()
                   if any(x["field"] != IR_FIELD for x in t)], key=key)

    parts, cur = [], []
    for dl in rest:
        if cur and (dl["context"]["firm"] != cur[0]["context"]["firm"] or len(cur) >= PART_SIZE):
            parts.append(cur)
            cur = []
        cur.append(dl)
    parts.append(cur)
    merged = []
    for p in parts:
        if merged and len(p) < MIN_PART and p[0]["context"]["firm"] == merged[-1][0]["context"]["firm"]:
            merged[-1] += p
        else:
            merged.append(p)

    def write(name, p):
        (out / f"{name}.json").write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{name}: {p[0]['context']['firm']} {len(p)}건, {sum(len(x['targets']) for x in p)}칸")

    for i, p in enumerate(merged, 1):
        write(f"part{i}", p)
    for firm in sorted({x["context"]["firm"] for x in ir}):
        write(f"ir_{firm.replace(' ', '')}", [x for x in ir if x["context"]["firm"] == firm])
    print(f"거래 {len(targets)}건, 칸 {sum(len(t) for t in targets.values())}칸")


if __name__ == "__main__":
    main()
