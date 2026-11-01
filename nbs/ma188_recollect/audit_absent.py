"""1차 재수집에서 '공개 자료 없음'으로 분류한 칸을 강화된 기준으로 다시 볼 대상을 고른다 (2026-11-01).

강화된 기준 (nbs/ma188_recollect/brief_recollect.md §2-1)
    항목별 출처 목록을 실제로 열어 보고 값이 없음을 확인한 칸만 '공개 자료 없음'이다.
    제도나 추론만으로 판단한 칸은 '미완'이다.

다시 볼 대상
    1. 강화된 기준을 받기 전에 끝난 묶음(part1·2·4·7·8·9·11)의 '공개 자료 없음' 칸 전부.
       이 묶음은 옛 기준으로 분류했으므로, 이유에 출처가 적혀 있어도 출처 목록을 다 봤는지 알 수 없다.
    2. 강화된 기준을 받은 묶음(part3·5·6·10)의 칸 중, 이유에 실제로 연 출처의 흔적이 없는 칸.
       흔적: DART 접수번호(14자리), URL, 'dart.py'·검색·조회·목록 같은 확인 행위.

실행(저장소 루트): python -X utf8 nbs/ma188_recollect/audit_absent.py <재수집 폴더> <출력 폴더>
    <재수집 폴더>에는 inputs/part*.json과 results/*.json이 있어야 한다.
    <출력 폴더>/verify_part*.json을 쓴다(2차 재수집 입력). 기업별·계보 순서로 12건 안팎씩 묶는다.
"""
import json
import re
import sys
from pathlib import Path

NEW_RULE_PARTS = {3, 5, 6, 10}
REF = re.compile(r"\d{14}|https?://|dart\.py|검색|조회|목록|EDINET|TDnet|EDGAR|官報")
PART_SIZE = 12


def main():
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    inputs = {}
    for f in sorted((src / "inputs").glob("part*.json"), key=lambda p: int(p.stem[4:])):
        for x in json.loads(f.read_text(encoding="utf-8")):
            inputs[x["deal_id"]] = (int(f.stem[4:]), x)

    deals, n_old, n_noref, n_ok = [], 0, 0, 0
    for did, (part, x) in inputs.items():
        r = json.loads((src / "results" / f"{did}.json").read_text(encoding="utf-8"))
        targets = []
        for g in r["gaps"]:
            if not g["class"].startswith("공개 자료 없음"):
                continue
            if part not in NEW_RULE_PARTS:
                why = "옛 기준으로 분류"
                n_old += 1
            elif not REF.search(g["reason"]):
                why = "이유에 실제로 연 출처가 없음"
                n_noref += 1
            else:
                n_ok += 1
                continue
            targets.append({"field": g["field"], "value_now": g["after"], "reason_now": g["reason"], "why_recheck": why})
        if targets:
            deals.append({"deal_id": did, "ciq_id": x["ciq_id"], "part": part, "context": x["context"],
                          "targets": targets})

    parts, cur = [], []
    for dl in sorted(deals, key=lambda v: (v["context"]["firm"], v["part"], v["deal_id"])):
        if cur and (dl["context"]["firm"] != cur[0]["context"]["firm"] or len(cur) >= PART_SIZE):
            parts.append(cur)
            cur = []
        cur.append(dl)
    if cur:
        parts.append(cur)
    for i, p in enumerate(parts, 1):
        (out / f"verify_part{i}.json").write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"verify_part{i}: {p[0]['context']['firm']} {len(p)}건, {sum(len(d['targets']) for d in p)}칸")
    print(f"다시 볼 칸: 옛 기준 {n_old}, 출처 흔적 없음 {n_noref} / 기준 충족으로 둔 칸 {n_ok}")


if __name__ == "__main__":
    main()
