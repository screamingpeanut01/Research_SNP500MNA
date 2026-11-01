"""2차 재수집 결과를 거래별 검토 기록과 빈 항목 표에 반영한다 (2026-11-01).

입력
    <입력 폴더>/part*.json, ir_*.json        make_inputs_r2.py가 만든 에이전트 입력(거래마다 targets)
    <결과 폴더>/<묶음>/<deal_id>.json         에이전트 결과 (형식: brief_recollect_r2.md §3)
    <Chrome 폴더>/*.json                      연구자 지시로 Claude in Chrome·공개 시세 API로 직접 확인한 값

하는 일
    1. 결과를 검사한다: targets의 칸이 빠짐없이 있는지, 분류·재시도 값이 정해진 것인지, 근거 행의 키가 맞는지.
    2. 아래 정정을 적용한다.
       - CALL_NOT_HEARD: 어닝콜 칸을 '공개 자료 없음'으로 분류했지만, 거래 연도·다음 연도 어닝콜의 녹취나 음성을
         실제로 열지 않고 기사로만 확인한 칸. 기준(출처를 모두 열어야 '공개 자료 없음')에 맞지 않으므로 '미완'으로 바꾼다.
       - Chrome 폴더의 값: 에이전트가 열지 못한 출처를 직접 열어 얻은 값으로 칸을 채우거나 이유를 보탠다.
    3. data/ma188_missing_fields.csv의 해당 칸을 2차 결과로 바꾼다(이유 앞에 '2차 재수집:'을 붙인다).
       빈 항목 정의에 걸리지 않아 표에 없던 칸(make_inputs_r2.EXTRA)은 행을 더한다.
    4. review_<deal_id>.json에 반영한다: corrections, notes(MARK 줄 덧붙임), evidence_add, review_note.
       collect_status는 빈 항목 표에서 그 거래의 남은 칸이 모두 '공개 자료 없음'이거나 '채움'이면 '완료', 아니면 '부분'.
    5. 손상 분류를 새로 판정한 거래는 data/ma188_impairment_class.csv를 고친다.
    같은 결과를 두 번 반영하지 않도록, review_note에 MARK가 있으면 그 거래의 기록은 건너뛴다.

실행(저장소 루트): python -X utf8 nbs/ma188_recollect/apply_round2.py <입력 폴더> <결과 폴더> <Chrome 폴더> [--dry]
그다음 시트 재생성: python -X utf8 nbs/ma188_build_sheet.py --out meeting/20261102 --merge data/ma188_records
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
REC = ROOT / "data" / "ma188_records"
SHEET = ROOT / "meeting" / "20261102" / "MA188_수집시트.csv"
CIQ_MAP = ROOT / "data" / "ma188_deal_ciq.csv"
IMP_CLASS = ROOT / "data" / "ma188_impairment_class.csv"
MISS = ROOT / "data" / "ma188_missing_fields.csv"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_results import CLASSES, EVID_KEYS, IMP_VALUES, imp_after  # noqa: E402

MARK = "재수집2(2026-11-01)"
RETRY = {"채움", "일부 채움", "못 찾음"}
CALL = "earnings_call_note"

# 어닝콜 녹취·음성을 열지 않고 기사로만 확인한 칸(거래 연도·다음 연도 기준).
#   카카오 2016~2020 거래: 2Q20 이전 어닝콜은 녹취가 없고 음성(teletogether RTMP)만 있는데 열지 못함.
#   카카오게임즈 2020 거래: 2020~2021 어닝콜 녹취를 찾지 못함(StockAnalysis는 1Q23부터).
#   LINE 2017 거래: 2017 3Q 녹취 한 건 외에는 어닝콜을 열지 못함.
#   NAVER 2018~2021 거래: 어닝콜 음성은 이메일 인증을 거쳐야 열리고, 녹취는 2022년부터만 찾음.
CALL_NOT_HEARD = {
    "K010": "카카오 2016~2017 어닝콜 음성", "K011": "카카오 2016~2017 어닝콜 음성",
    "K019": "카카오 2018~2019 어닝콜 음성", "K023": "카카오 2018~2019 어닝콜 음성",
    "K024": "카카오 2018~2019 어닝콜 음성", "K026": "카카오 2018~2019 어닝콜 음성",
    "K031": "카카오 2018~2019 어닝콜 음성", "K040": "카카오 1Q20·2Q20 어닝콜 음성",
    "K043": "카카오게임즈 2020~2021 어닝콜",
    "N034": "LINE 2017~2018 어닝콜(2017 3Q 외)", "N036": "LINE 2017~2018 어닝콜(2017 3Q 외)",
    "N039": "LINE 2017~2018 어닝콜(2017 3Q 외)",
    "N042": "NAVER 2018~2019 어닝콜 음성(이메일 인증)", "N045": "NAVER 2018~2019 어닝콜 음성(이메일 인증)",
    "N048": "NAVER 2019~2020 어닝콜 음성(이메일 인증)", "N053": "NAVER 2020~2021 어닝콜 음성(이메일 인증)",
    "N056": "NAVER 2020~2021 어닝콜 음성(이메일 인증)", "N069": "NAVER 2021 어닝콜 음성(이메일 인증)",
}


def load(inp, res):
    targets = {}
    for f in sorted(inp.glob("*.json")):
        for x in json.loads(f.read_text(encoding="utf-8")):
            t = targets.setdefault(x["deal_id"], {"ciq_id": x["ciq_id"], "fields": {}})
            for g in x["targets"]:
                t["fields"][g["field"]] = g
    merged = {}
    for f in sorted(res.glob("*/*.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        m = merged.setdefault(r["deal_id"], {"deal_id": r["deal_id"], "ciq_id": r["ciq_id"], "checks": [],
                                             "corrections": {}, "evidence_add": [], "other_issues": [],
                                             "summary": [], "impairment_class_after": None})
        m["checks"] += r["checks"]
        m["corrections"].update(r.get("corrections") or {})
        m["evidence_add"] += r.get("evidence_add") or []
        if r.get("other_issues"):
            m["other_issues"].append(r["other_issues"])
        m["summary"].append(r.get("summary", ""))
        m["impairment_class_after"] = m["impairment_class_after"] or r.get("impairment_class_after")
    return targets, merged


def check(t, r):
    did = r["deal_id"]
    got = [c["field"] for c in r["checks"]]
    if sorted(got) != sorted(t["fields"]):
        raise ValueError(f"{did}: 칸이 입력과 다름 (빠짐 {set(t['fields']) - set(got)}, 더함 {set(got) - set(t['fields'])})")
    for c in r["checks"]:
        if c["class"] not in CLASSES or c["retry"] not in RETRY:
            raise ValueError(f"{did} {c['field']}: 분류 '{c['class']}'·재시도 '{c['retry']}'가 정해진 값이 아님")
    bad = set(r["corrections"]) - (set(t["fields"]) - {"impairment_class"})
    if bad:
        raise ValueError(f"{did}: 대상이 아닌 열을 고침 {bad}")
    for e in r["evidence_add"]:
        if set(e) != set(EVID_KEYS):
            raise ValueError(f"{did}: 근거 행의 키가 다름 {sorted(e)}")
    imp = imp_after(r)
    if imp and imp.get("class") not in IMP_VALUES:
        raise ValueError(f"{did}: 손상 분류 '{imp.get('class')}'가 정해진 값이 아님")


def apply_chrome(merged, chrome, to_deal):
    """연구자 지시로 Chrome·공개 API로 직접 연 출처의 결과를 반영한다."""
    def cell(cid, field):
        r = merged[to_deal[cid]]
        return r, next(c for c in r["checks"] if c["field"] == field)

    p = chrome / "naver_price.json"
    if p.exists():
        for x in json.loads(p.read_text(encoding="utf-8")):
            r = merged[x["deal_id"]]
            c = next(c for c in r["checks"] if c["field"] == x["field"])
            v = (f"계산: {x['mktcap_krw']:,}원 (발표 직전 거래일 {x['date']} 종가 {x['close_krw']:,}원 × 발행주식총수 "
                 f"{x['shares']:,}주; 종가는 네이버 증권 차트 API의 상장폐지 종목 일별 시세). "
                 f"참고: 2015년 10월 일평균 주가 기준 추정은 약 3조 3,105억원")
            c.update({"class": "미완", "retry": "채움", "after": v,
                      "reason": c["reason"] + f" / 이후 연구자 지시로 네이버 증권 차트 API({x['url']})에서 종가를 확인함."})
            r["corrections"][x["field"]] = v
            r["evidence_add"].append({"field": x["field"], "phase": "발표", "event_date": x["date"], "event_type": "기타",
                                      "content": f"{x['date']} 종가 {x['close_krw']:,}원 (네이버 증권 일별 시세 {x['raw']})",
                                      "url": x["url"], "doc_type": "기타", "doc_date": x["date"], "doc_id": ""})

    p = chrome / "cj_calls.json"
    if p.exists():
        for x in json.loads(p.read_text(encoding="utf-8")):
            r, c = cell(x["ciq_id"], x["field"])
            # IR 자료는 에이전트가, 어닝콜 녹취는 Chrome으로 모두 열었다. 개별 회사 언급은 없고 일반론만 있다.
            v = (c["after"] + " / 어닝콜: " + x["after"]) if c["retry"] in ("채움", "일부 채움") else x["after"]
            c.update({"class": "공개 자료 없음", "retry": "못 찾음", "after": v,
                      "reason": c["reason"] + " / " + x["reason"]})
            r["corrections"][x["field"]] = v
            r["evidence_add"].append(x["evidence"])

    p = chrome / "ir_calls.json"
    if p.exists():
        for x in json.loads(p.read_text(encoding="utf-8")):
            if x["ciq_id"] not in to_deal or to_deal[x["ciq_id"]] not in merged:
                continue
            r, c = cell(x["ciq_id"], x["field"])
            if x["kind"] == "filled":
                c["reason"] += f" / Claude in Chrome으로 StockAnalysis 녹취({x['url']})에서도 같은 발언을 확인함."
            else:
                c["reason"] += f" / {x['note']} 확인한 녹취: {x['checked']}."

    p = chrome / "overrides.json"  # 칸 하나를 통째로 다시 판정한 경우(예: 연구자가 사람 확인을 통과시킨 기사)
    if p.exists():
        for x in json.loads(p.read_text(encoding="utf-8")):
            r = merged[x["deal_id"]]
            c = next(c for c in r["checks"] if c["field"] == x["field"])
            c.update({"class": x["class"], "retry": x["retry"], "after": x["after"],
                      "reason": c["reason"] + " / " + x["reason_add"]})
            r["corrections"][x["field"]] = x["after"]
            r["evidence_add"].append(x["evidence"])

    p = chrome / "line_irbank.json"
    if p.exists():
        for x in json.loads(p.read_text(encoding="utf-8")):
            r, c = cell(x["ciq_id"], x["field"])
            c["reason"] += (f" / 교차 확인: Claude in Chrome으로 연 IRBANK({x['url']})의 {x['date']} 종가 "
                            f"{x['close_jpy']}円, 시가총액 {x['mktcap']}.")


def main():
    inp, res, chrome = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    dry = "--dry" in sys.argv
    to_deal = pd.read_csv(CIQ_MAP, dtype=str).set_index("ciq_id").deal_id
    targets, merged = load(inp, res)
    missing = set(targets) - set(merged)
    if missing:
        raise ValueError(f"결과가 없는 거래: {sorted(missing)}")
    for did, r in merged.items():
        check(targets[did], r)
    apply_chrome(merged, chrome, to_deal)
    for did, why in CALL_NOT_HEARD.items():
        c = next(c for c in merged[did]["checks"] if c["field"] == CALL)
        if c["class"] == "공개 자료 없음":
            c["class"] = "미완"
            c["reason"] += (f" / 정정(2026-11-01): {why}을 열지 않고 기사로만 확인했으므로, "
                            f"출처를 모두 열어야 한다는 기준에 따라 '미완'으로 둔다.")

    miss = pd.read_csv(MISS, dtype=str, keep_default_na=False)
    for did, r in merged.items():
        for c in r["checks"]:
            row = {"class": c["class"], "retry": c["retry"], "after": c["after"], "reason": f"2차 재수집: {c['reason']}"}
            k = (miss.ciq_id == r["ciq_id"]) & (miss.field == c["field"])
            if k.any():
                for col, v in row.items():
                    miss.loc[k, col] = v
            else:
                g = targets[did]["fields"][c["field"]]
                miss.loc[len(miss)] = {"ciq_id": r["ciq_id"], "field": c["field"], "before": g["value_now"], **row}

    imp = pd.read_csv(IMP_CLASS, dtype=str, keep_default_na=False).set_index("ciq_id")
    sheet = pd.read_csv(SHEET, dtype=str, keep_default_na=False).set_index("ciq_id")
    n_done = n_skip = 0
    status = {}
    for did, r in merged.items():
        left = miss[(miss.ciq_id == r["ciq_id"]) & (miss["class"] == "미완") & (miss.retry != "채움")]
        status[did] = "완료" if left.empty else "부분"
        rv_path = REC / f"review_{did}.json"
        rv = json.loads(rv_path.read_text(encoding="utf-8"))
        if MARK in rv["review_note"]:
            n_skip += 1
            continue
        corr = rv["corrections"]
        corr.update(r["corrections"])
        by = {k: [c["field"] for c in r["checks"] if c["retry"] == k and c["class"] == "미완"] for k in ("채움", "일부 채움")}
        by["못 찾음"] = [c["field"] for c in r["checks"] if c["class"] == "미완" and c["retry"] == "못 찾음"]
        by["공개 자료 없음"] = [c["field"] for c in r["checks"] if c["class"] == "공개 자료 없음"]
        line = f"{MARK}: " + "; ".join(f"{k} {', '.join(v)}" for k, v in by.items() if v) + "."
        notes = corr.get("notes", sheet.loc[r["ciq_id"], "notes"])
        corr["notes"] = (notes + " / " if notes else "") + line
        corr["collect_status"] = status[did]
        rv["evidence_add"] = rv["evidence_add"] + r["evidence_add"]
        rv["review_note"] += f" / {MARK}: {' '.join(s for s in r['summary'] if s)}"
        if r["other_issues"]:
            rv["review_note"] += f" 2차 재수집 중 발견한 다른 문제: {' '.join(r['other_issues'])}"
        ic = imp_after(r)
        if ic:
            imp.loc[r["ciq_id"], "impairment_class"] = ic["class"]
            imp.loc[r["ciq_id"], "impairment_class_basis"] = f"{ic['basis']} ({MARK})"
        if not dry:
            rv_path.write_text(json.dumps(rv, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        n_done += 1

    cells = [c for r in merged.values() for c in r["checks"]]
    out = pd.DataFrame([{"class": c["class"], "retry": c["retry"]} for c in cells])
    print(f"거래 {len(merged)}건, 칸 {len(cells)}칸 (반영 {n_done}건, 이미 반영돼 건너뜀 {n_skip}건)")
    print(pd.crosstab(out["class"], out.retry, margins=True).to_string())
    print("수집 상태:", pd.Series(status).value_counts().to_dict())
    if not dry:
        miss.to_csv(MISS, index=False, encoding="utf-8-sig")
        imp.reset_index().to_csv(IMP_CLASS, index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
