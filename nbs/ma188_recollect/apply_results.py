"""빈 항목 재수집 결과를 거래별 검토 기록에 반영한다 (2026-11-01).

입력
    <결과 폴더>/<deal_id>.json   재수집 에이전트가 쓴 결과 (형식: nbs/ma188_recollect/brief_recollect.md §3)

하는 일
    1. 결과를 검사한다: 거래가 입력에 있었는지, 분류·재시도 값이 정해진 것인지, 고친 열이 빈 항목이었는지.
    2. data/ma188_missing_fields.csv에 빈 항목마다 한 행을 쓴다(분류, 이유, 재시도 결과, 전후 값).
    3. data/ma188_records/review_<deal_id>.json에 반영한다.
       - corrections: 재수집으로 바뀐 열의 값을 넣는다(앞선 검토 정정 위에 덮어쓴다).
       - notes: 지금 메모 뒤에 재수집 요약을 덧붙인다.
       - collect_status: 남은 빈 항목이 모두 '공개 자료 없음'이면 '완료'로 바꾼다.
         즉 재수집 뒤의 '완료'는 "남은 빈칸이 모두 공개 자료에 없는 값"이라는 뜻이다.
       - evidence_add: 새 근거를 덧붙인다. review_note: 재수집 요약을 덧붙인다.
    4. 손상 분류를 새로 판정한 거래는 data/ma188_impairment_class.csv를 고친다.
    같은 결과를 두 번 반영하지 않도록, review_note에 표시(MARK)가 있으면 건너뛴다.

실행(저장소 루트): python -X utf8 nbs/ma188_recollect/apply_results.py <결과 폴더> [<2차 확인 결과 폴더>]
    2차 확인 결과(nbs/ma188_recollect/brief_verify.md)가 있으면 같은 거래의 1차 결과 위에 덮어쓴 뒤 반영한다.
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
OUT = ROOT / "data" / "ma188_missing_fields.csv"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_inputs import GAP_FIELDS, is_gap  # noqa: E402

MARK = "재수집(2026-11-01)"
CLASSES = {"공개 자료 없음", "미완"}
RETRY = {"채움", "일부 채움", "못 찾음", "재시도 안 함"}
IMP_VALUES = {"있음", "없음 (확인)", "식별 불가", "미확인", "해당 없음"}
EVID_KEYS = ["field", "phase", "event_date", "event_type", "content", "url", "doc_type", "doc_date", "doc_id"]


def normalize(r):
    """'못 찾음 (어디를 봤는지)'처럼 재시도 값 뒤에 설명을 붙인 경우, 앞부분만 값으로 두고 설명은 reason 뒤로 옮긴다."""
    for g in r["gaps"]:
        for key, allowed in (("class", CLASSES), ("retry", RETRY)):
            v = g[key].strip()
            head = next((a for a in sorted(allowed, key=len, reverse=True) if v.startswith(a)), None)
            if head and v != head:
                g[key] = head
                g["reason"] = f"{g['reason']} {v[len(head):].strip()}".strip()
    # 손상 분류는 별도 파일에서 관리하므로, corrections에 들어왔으면 impairment_class_after로 옮긴다.
    c = r.get("corrections", {})
    if "impairment_class" in c:
        v = c.pop("impairment_class")
        r["impairment_class_after"] = r.get("impairment_class_after") or v
    return r


def merge_verify(r, v):
    """2차 확인 결과(brief_verify.md §3)를 1차 결과 위에 덮어쓴다.
    다시 본 칸은 분류·재시도·이유·값을 2차 결과로 바꾸고, 이유 앞에 '2차 확인:'을 붙인다."""
    gaps = {g["field"]: g for g in r["gaps"]}
    for c in normalize({"gaps": v["checks"]})["gaps"]:
        if c["field"] not in gaps:
            raise ValueError(f"{r['deal_id']}: 2차 확인한 칸 {c['field']}이 1차 빈 항목에 없음")
        if c["class"] not in CLASSES or c["retry"] not in RETRY - {"재시도 안 함"}:
            raise ValueError(f"{r['deal_id']} {c['field']}: 2차 분류 '{c['class']}'·재시도 '{c['retry']}'가 정해진 값이 아님")
        g = gaps[c["field"]]
        g.update({"class": c["class"], "retry": c["retry"], "after": c["after"], "reason": f"2차 확인: {c['reason']}"})
    r.setdefault("corrections", {}).update(v.get("corrections", {}))
    r["evidence_add"] = r.get("evidence_add", []) + v.get("evidence_add", [])
    r["summary"] = f"{r['summary']} 2차 확인: {v['summary']}"
    if v.get("other_issues"):
        r["other_issues"] = f"{r.get('other_issues', '')} {v['other_issues']}".strip()
    return r


def imp_after(r):
    """손상 분류 결과를 {class, basis}로 맞춘다. 에이전트가 '없음 (확인): 근거'처럼 문자열로 쓴 경우도 받는다."""
    v = r.get("impairment_class_after")
    if not v:
        return None
    if isinstance(v, dict):
        return {"class": v.get("class", v.get("value")), "basis": v.get("basis", "")}
    cls = next((c for c in sorted(IMP_VALUES, key=len, reverse=True) if v.startswith(c)), None)
    return {"class": cls, "basis": v[len(cls):].lstrip(" :—-(").rstrip(")") if cls else v}


def check(r, row):
    did = r["deal_id"]
    expected = {f for f in GAP_FIELDS if is_gap(row[f])}
    got = {g["field"] for g in r["gaps"]}
    if got != expected:
        raise ValueError(f"{did}: 빈 항목이 입력과 다름 (빠짐 {expected - got}, 더함 {got - expected})")
    for g in r["gaps"]:
        if g["class"] not in CLASSES or g["retry"] not in RETRY:
            raise ValueError(f"{did} {g['field']}: 분류 '{g['class']}' 또는 재시도 '{g['retry']}'가 정해진 값이 아님")
    bad = set(r.get("corrections", {})) - expected
    if bad:
        raise ValueError(f"{did}: 빈 항목이 아닌 열을 고침 {bad}")
    for e in r.get("evidence_add", []):
        if set(e) != set(EVID_KEYS):
            raise ValueError(f"{did}: 근거 행의 키가 다름 {sorted(e)}")
    imp = imp_after(r)
    if imp and imp.get("class") not in IMP_VALUES:
        raise ValueError(f"{did}: 손상 분류 '{imp.get('class')}'가 정해진 값이 아님")


def notes_line(r):
    """notes 뒤에 덧붙일 재수집 요약: 채운 항목, 공개 자료에 없는 항목, 못 찾은 항목."""
    by = {k: [g["field"] for g in r["gaps"] if g["retry"] in v]
          for k, v in {"채움": {"채움"}, "일부 채움": {"일부 채움"}, "못 찾음": {"못 찾음"}}.items()}
    absent = [g["field"] for g in r["gaps"] if g["class"] == "공개 자료 없음"]
    parts = [f"{k} {', '.join(v)}" for k, v in by.items() if v]
    if absent:
        parts.append(f"공개 자료 없음 {', '.join(absent)}")
    return f"{MARK}: " + "; ".join(parts) + "."


def main():
    src = Path(sys.argv[1])
    ver = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    d = pd.read_csv(SHEET, dtype=str, keep_default_na=False).set_index("ciq_id")
    to_deal = pd.read_csv(CIQ_MAP, dtype=str).set_index("ciq_id").deal_id
    d["deal_id"] = d.index.map(to_deal)
    d = d.reset_index().set_index("deal_id")
    imp = pd.read_csv(IMP_CLASS, dtype=str, keep_default_na=False).set_index("ciq_id")

    rows, n_done, n_skip = [], 0, 0
    for f in sorted(src.glob("*.json")):
        r = normalize(json.loads(f.read_text(encoding="utf-8")))
        did = r["deal_id"]
        if ver and (ver / f.name).exists():
            r = merge_verify(r, json.loads((ver / f.name).read_text(encoding="utf-8")))
        row = d.loc[did]
        if row.collect_status != "부분" and MARK not in row.review_note:
            raise ValueError(f"{did}: 수집 상태가 '부분'이 아닌 거래")
        if r["ciq_id"] != row.ciq_id:
            raise ValueError(f"{did}: ciq_id가 시트와 다름")
        for g in r["gaps"]:
            rows.append({"ciq_id": row.ciq_id, "field": g["field"], "class": g["class"], "reason": g["reason"],
                         "retry": g["retry"], "before": g["before"], "after": g["after"]})

        rv_path = REC / f"review_{did}.json"
        rv = json.loads(rv_path.read_text(encoding="utf-8"))
        if MARK in rv["review_note"]:
            n_skip += 1
            continue
        check(r, row)
        corr = rv["corrections"]
        corr.update(r.get("corrections", {}))
        corr["notes"] = (row.notes + " / " if row.notes else "") + notes_line(r)
        left = [g for g in r["gaps"] if g["class"] == "미완" and g["retry"] != "채움"]
        if not left:
            corr["collect_status"] = "완료"
        rv["evidence_add"] = rv["evidence_add"] + r.get("evidence_add", [])
        rv["review_note"] = rv["review_note"] + f" / {MARK}: {r['summary']}"
        if r.get("other_issues"):
            rv["review_note"] += f" 재수집 중 발견한 다른 문제: {r['other_issues']}"
        rv_path.write_text(json.dumps(rv, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

        ic = imp_after(r)
        if ic:
            imp.loc[row.ciq_id, "impairment_class"] = ic["class"]
            imp.loc[row.ciq_id, "impairment_class_basis"] = f"{ic['basis']} ({MARK})"
        n_done += 1

    imp.reset_index().to_csv(IMP_CLASS, index=False, encoding="utf-8-sig")
    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"반영 {n_done}건, 이미 반영돼 건너뜀 {n_skip}건, 빈 항목 {len(out)}칸 -> {OUT.name}")
    print(pd.crosstab(out["class"], out["retry"], margins=True).to_string())


if __name__ == "__main__":
    main()
