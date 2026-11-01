"""빈 항목 재수집 결과 요약 (주차연구정리_20261102 [분석 B-8]의 표와 수치의 출처).

입력: data/ma188_missing_fields.csv (apply_results.py 산출물), meeting/20261102/MA188_수집시트.csv
실행(저장소 루트): python -X utf8 nbs/ma188_recollect/summarize.py
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MISS = ROOT / "data" / "ma188_missing_fields.csv"
SHEET = ROOT / "meeting" / "20261102" / "MA188_수집시트.csv"
MARK = "재수집(2026-11-01)"

GROUP = {
    "실적": ["target_rev_pre", "target_rev_post", "target_op_pre", "target_op_post", "perf_basis"],
    "어닝콜·IR 언급": ["earnings_call_note"],
    "인수 목적 문장": ["purpose_quote"],
    "규모": ["acq_total_assets", "apex_total_assets", "deal_to_assets_pct", "deal_to_equity_pct", "acq_mktcap",
           "size_basis"],
}


def group(f):
    return next((g for g, fs in GROUP.items() if f in fs), "기타(사건·날짜·상태·손상 등)")


def outcome(r):
    if r["class"] == "공개 자료 없음":
        return "공개 자료 없음"
    return {"채움": "채움", "일부 채움": "일부 채움"}.get(r["retry"], "못 찾음")


def main():
    m = pd.read_csv(MISS, dtype=str, keep_default_na=False)
    d = pd.read_csv(SHEET, dtype=str, keep_default_na=False)
    m["group"] = m.field.map(group)
    m["outcome"] = m.apply(outcome, axis=1)
    m["second"] = m.reason.str.startswith("2차 확인")

    print(f"[1] 빈 항목 {len(m)}칸, 거래 {m.ciq_id.nunique()}건")
    print(pd.crosstab(m["class"], m.retry, margins=True).to_string())
    print("\n[2] 항목 묶음별 결과")
    cols = ["공개 자료 없음", "채움", "일부 채움", "못 찾음"]
    print(pd.crosstab(m.group, m.outcome, margins=True)[cols + ["All"]].to_string())
    print(f"\n[3] 2차 확인한 칸 {int(m.second.sum())}칸의 결과")
    print(m[m.second].outcome.value_counts().to_string())
    miss = m[(m["class"] == "미완") & (m.retry == "못 찾음")]
    print(f"\n[3b] 못 찾은 칸 {len(miss)}칸 중 이유에 다음 말이 있는 칸 (겹침 있음)")
    for k, p in {"官報": "官報", "유료·계정": "유료|계정|paywall|MCA", "접속 차단": "403|차단|캡차|봇",
                 "Wayback": "Wayback"}.items():
        print(f"  {k}: {int(miss.reason.str.contains(p).sum())}")
    print("\n[4] 재수집 뒤 수집 상태")
    re_ = d.notes.str.contains(MARK, regex=False)
    print(pd.crosstab(d.firm, d.collect_status, margins=True).to_string())
    print(f"재수집으로 '완료'가 된 거래 {int((re_ & (d.collect_status == '완료')).sum())}건, "
          f"재수집했으나 '부분'으로 남은 거래 {int((re_ & (d.collect_status == '부분')).sum())}건, "
          f"빈 항목이 없는데 '부분'인 거래 {int((~re_ & (d.collect_status == '부분')).sum())}건")


if __name__ == "__main__":
    main()
