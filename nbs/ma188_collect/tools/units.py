"""작업 유닛 대기열 (main 전용).

python -X utf8 units.py next <N> [review|collect]   다음 유닛 N개를 만들어 출력한다(기본: 검토 먼저, 그다음 수집).
python -X utf8 units.py close <U...>   끝난(또는 실패한) 유닛을 닫는다. 결과 파일이 없는 거래는 다시 대기열로 간다.
python -X utf8 units.py status         진척 요약

유닛 크기: 같은 묶음 안에서 2건씩, 100만 달러 미만 거래는 3건씩.
검토 깊이: 1천만 달러 이상이거나 금액 의심(value_flag)이면 full, 아니면 light.
"""
import json
import sys
from pathlib import Path

SP = Path(__file__).resolve().parent.parent
REC, UNITS, BATCH = SP / "records", SP / "units", SP / "batches"
STATE = UNITS / "_state.json"


def load_deals():
    deals = {}
    order = []
    for bf in sorted(BATCH.glob("*.json")):
        b = json.loads(bf.read_text(encoding="utf-8"))
        for d in b["deals"]:
            d["batch"] = b["batch"]
            deals[d["deal_id"]] = d
    # 묶음 우선순위: 금액 상위 50건이 든 묶음 먼저, 그다음 묶음 최대 금액 순
    bmax = {}
    for d in deals.values():
        k = (d["top50"] == "True", float(d["value"]))
        bmax[d["batch"]] = max(bmax.get(d["batch"], (False, 0.0)), k)
    order = sorted(deals, key=lambda i: (tuple(-x for x in (bmax[deals[i]["batch"]][0], bmax[deals[i]["batch"]][1])),
                                         deals[i]["batch"], i))
    return deals, order


def full_review(d):
    return float(d["value"]) >= 10 or d["value_flag"] == "True"


def state():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"next_id": 1, "units": {}}


def save(st):
    UNITS.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def done_sets():
    rec = {p.stem for p in REC.glob("*.json") if not p.stem.startswith("review_")}
    rev = {p.stem[7:] for p in REC.glob("review_*.json")}
    return rec, rev


def inflight(st, typ):
    return {d for u in st["units"].values() if u["status"] == "open" and u["type"] == typ for d in u["deals"]}


def chunks(ids, deals):
    out, cur = [], []
    for i in ids:
        size = 3 if float(deals[i]["value"]) < 1 else 2
        if cur and (deals[cur[0]]["batch"] != deals[i]["batch"] or len(cur) >= size
                    or (float(deals[cur[0]]["value"]) < 1) != (float(deals[i]["value"]) < 1)):
            out.append(cur)
            cur = []
        cur.append(i)
    if cur:
        out.append(cur)
    return out


def make_unit(st, typ, ids, deals):
    uid = f"U{st['next_id']:03d}"
    st["next_id"] += 1
    b = deals[ids[0]]["batch"]
    depth = ("full" if any(full_review(deals[i]) for i in ids) else "light") if typ == "review" else ""
    brief = SP / ("brief_review.md" if typ == "review" else "brief_collect.md")
    u = {"unit": uid, "type": typ, "depth": depth, "deals": ids, "batch": b,
         "batch_file": str(BATCH / f"{b}.json").replace("\\", "/"), "brief": str(brief).replace("\\", "/"),
         "work_dir": str(SP / "work" / uid).replace("\\", "/"),
         "instructions": (
             f"이 유닛의 거래 {', '.join(ids)}만 처리한다. 묶음 파일의 다른 거래는 관련 맥락을 볼 때만 참고한다. "
             f"먼저 brief 파일을 끝까지 읽는다(0절 토큰 절약 규칙을 반드시 지킨다). 임시 파일은 work_dir에만 쓴다. "
             + ("검토 깊이는 depth 값을 따른다. 거래마다 records/review_<deal_id>.json을 쓴다. 수집 기록 파일은 고치지 않는다."
                if typ == "review" else "거래마다 records/<deal_id>.json을 쓴다. 이미 파일이 있는 거래는 건너뛴다.")
             + " 끝나면 거래마다 한 줄로만 보고한다."),
         "status": "open"}
    (UNITS / f"{uid}.json").write_text(json.dumps(u, ensure_ascii=False, indent=1), encoding="utf-8")
    st["units"][uid] = {k: u[k] for k in ("type", "depth", "deals", "batch", "status")}
    return u


def cmd_next(n, only=None):
    UNITS.mkdir(exist_ok=True)
    deals, order = load_deals()
    st = state()
    rec, rev = done_sets()
    made = []
    rv = [] if only == "collect" else [i for i in order if i in rec and i not in rev and i not in inflight(st, "review")]
    # 같은 깊이끼리 묶는다
    for grp in (chunks([i for i in rv if full_review(deals[i])], deals), chunks([i for i in rv if not full_review(deals[i])], deals)):
        for c in grp:
            if len(made) < n:
                made.append(make_unit(st, "review", c, deals))
    cl = [] if only == "review" else [i for i in order if i not in rec and i not in inflight(st, "collect")]
    for c in chunks(cl, deals):
        if len(made) < n:
            made.append(make_unit(st, "collect", c, deals))
    save(st)
    for u in made:
        print(f"{u['unit']} {u['type']}{('-' + u['depth']) if u['depth'] else ''} {u['batch']} {','.join(u['deals'])}")
    if not made:
        print("대기열 비어 있음")


def cmd_close(uids):
    st = state()
    rec, rev = done_sets()
    for uid in uids:
        u = st["units"].get(uid)
        if not u:
            continue
        u["status"] = "closed"
        have = rev if u["type"] == "review" else rec
        miss = [d for d in u["deals"] if d not in have]
        print(f"{uid} closed" + (f", 결과 없음 → 대기열 복귀: {','.join(miss)}" if miss else ""))
    save(st)


def cmd_status():
    deals, _ = load_deals()
    st = state()
    rec, rev = done_sets()
    op = [k for k, u in st["units"].items() if u["status"] == "open"]
    print(f"수집 {len(rec)}/188, 검토 {len(rev)}/188, 진행 중 유닛 {len(op)}: {' '.join(op)}")


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "next":
        cmd_next(int(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else None)
    elif c == "close":
        cmd_close(sys.argv[2:])
    else:
        cmd_status()
