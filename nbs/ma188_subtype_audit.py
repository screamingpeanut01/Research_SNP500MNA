"""M&A 188건 거래 형태 전수 검수 결과 요약 (2026-11-01, 주차연구정리_20261102 [분석 B-2]의 출처).

배경
    10-19 규칙(nbs/pp_ma_record_audit.py)은 원자료의 매수자·매도자 칸, 설명란, 작성자가 넣은 그룹 회사 키워드로
    거래 형태(subtype, MA①~⑦)를 붙였다. 수집 단계에서는 공시를 읽고 거래 형태를 다시 판정했다(subtype_chk).
    두 값은 모두 연구팀의 판정이고, Capital IQ 원자료에는 거래 형태가 없다('Merger/Acquisition'뿐).
    두 값이 다른 45건을 근거 공시 원문(data/ma188_sources)과 대조해, 수집 판정이 맞는지와
    10-19 규칙이 왜 달랐는지를 거래마다 판정했다. 판정은 data/ma188_subtype_audit.csv에 있다.

열
    subtype_10_19       10-19 규칙의 거래 형태
    subtype_chk_before  검수 전 수집 판정
    verdict             변경 맞음(수집 판정이 맞음) / 다른 코드(둘 다 틀림, correct_code가 맞음)
    cause               정보 보충(원자료에 없던 매수자·매도자·지분을 공시로 채움) / 10-19 규칙 오판(원자료로 충분했으나
                        규칙이 잘못 읽음) / 원자료 오류(원자료의 지분율 등이 틀림) / 정의 차이 / 수집 판정 오류

실행(저장소 루트): python -X utf8 nbs/ma188_subtype_audit.py
"""
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "data" / "ma188_subtype_audit.csv"
SHEET = ROOT / "meeting" / "20261102" / "MA188_수집시트.csv"


def code(s):
    m = re.search(r"MA[①-⑦]", s)
    return m.group(0) if m else ""


def main():
    a = pd.read_csv(AUDIT, dtype=str, keep_default_na=False)
    d = pd.read_csv(SHEET, dtype=str, keep_default_na=False).set_index("ciq_id")
    # 검수 대상이 10-19 규칙과 수집 판정이 달랐던 거래 전부인지, 정정이 시트에 반영됐는지 확인한다
    changed = set(d.index[d.subtype.map(code) != d.subtype_chk.map(code)])
    assert set(a.ciq_id) == changed, "검수 대상과 형태가 달랐던 거래가 맞지 않음"
    now = d.loc[a.ciq_id, "subtype_chk"].map(code).values
    assert (now == a.correct_code.map(code).values).all(), "시트의 subtype_chk가 검수 판정과 다름"

    print(f"[1] 검수한 거래 {len(a)}건 (10-19 규칙과 수집 판정이 달랐던 거래 전부)")
    print(a.verdict.value_counts().to_string())
    print("\n[2] 차이의 원인")
    print(a.cause.value_counts().to_string())
    print("\n[3] 원인 × 판정")
    print(pd.crosstab(a.cause, a.verdict, margins=True).to_string())
    print("\n[4] 10-19 규칙 → 최종 거래 형태")
    print(pd.crosstab(a.subtype_10_19.map(code), a.correct_code.map(code), margins=True).to_string())
    print("\n[5] 수집 판정을 고친 거래")
    for r in a[a.verdict != "변경 맞음"].itertuples():
        print(f"  {r.ciq_id} {r.target}: {code(r.subtype_chk_before)} → {code(r.correct_code)}")


if __name__ == "__main__":
    main()
