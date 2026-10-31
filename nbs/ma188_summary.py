"""M&A 188건 수집 결과 요약 (주차연구정리_20261102 [분석 B-1]~[B-6] 표와 수치의 출처).

저장소 루트에서 실행: python -X utf8 nbs/ma188_summary.py
입력: meeting/20261102/MA188_수집시트.csv, MA188_근거.csv (nbs/ma188_build_sheet.py 산출물)
"""
import re
import pandas as pd

SHEET = "meeting/20261102/MA188_수집시트.csv"
EVID = "meeting/20261102/MA188_근거.csv"


def code(s):
    m = re.search(r"MA[①-⑦]", s)
    return m.group(0) if m else ""


def imp_class(s):
    s = s.strip()
    if s.startswith("있음"):
        return "있음"
    if s.startswith("확인 안 됨"):
        return "확인 안 됨"
    if s.startswith("해당 없음"):
        return "해당 없음"
    if s.startswith("없음"):
        return "없음"
    return "기타(서술)"


def main():
    d = pd.read_csv(SHEET, dtype=str).fillna("")
    e = pd.read_csv(EVID, dtype=str).fillna("")
    d["base"] = d.subtype.map(code)
    d["chk"] = d.subtype_chk.map(code)
    d["imp"] = d.impairment.map(imp_class)
    d["val"] = d.value_chk_usdmm.map(lambda s: "일치" if s.startswith("원자료와 일치") else
                                     ("불일치" if s.startswith(("원자료와 불일치", "원자료 오류")) else "기타"))
    d["pre"] = d.pre_incorp_chk.map(lambda s: s.split(" (")[0].split(":")[0].strip())
    d["stat"] = d.status_chk.map(lambda s: s.split(" (")[0].strip())

    print("[1] 기업별 건수와 수집 상태")
    print(pd.crosstab(d.firm, d.collect_status, margins=True))
    print("\n[2] 검토 결과")
    print(d.review_status.value_counts())
    print("\n[3] 거래 형태: 설명란 판정(행) → 공시 확인(열)")
    print(pd.crosstab(d.base, d.chk, margins=True))
    print("분류가 바뀐 거래:", int((d.base != d.chk).sum()))
    print("\n[4] 거래 상태: 원자료 status → 확인")
    print(pd.crosstab(d.status, d.stat))
    print("\n[5] 금액 대조")
    print(d.val.value_counts())
    print("\n[6] 편입 시점 판정")
    print(d.pre.value_counts())
    print("\n[7] 손상 여부 (기업별)")
    print(pd.crosstab(d.firm, d.imp, margins=True))
    buy = d[d.chk.isin(["MA①", "MA②", "MA③"])]
    print("\n[8] 그룹이 산 거래(MA①②③)의 손상 여부")
    print(pd.crosstab(buy.chk, buy.imp, margins=True))
    if "impairment_class" in d.columns:
        print("\n[8b] 손상 다시 분류(impairment_class, 2026-11-01): 그룹이 산 거래(MA①②③)")
        t = pd.crosstab(buy.firm, buy.impairment_class, margins=True)
        print(t)
        j = buy[buy.impairment_class.isin(["있음", "없음 (확인)"])]
        print("판정 가능한 거래(있음+없음) 중 손상 비율:",
              (j.groupby("firm").impairment_class.apply(lambda s: (s == "있음").mean()).round(3)).to_dict(),
              "전체", round((j.impairment_class == "있음").mean(), 3))
    print("\n[10] 이중 집계·표본 제외 언급이 notes/chk_note에 있는 거래")
    m = (d.notes + " " + d.chk_note).str.contains("이중 집계|중복 행|제외 후보")
    print(int(m.sum()), " ".join(d[m].ciq_id))
    print("\n[11] 근거")
    print("근거 행", len(e), "/ 고유 URL", e.url[e.url != ""].nunique())
    print(e.doc_type.value_counts().head(12))


if __name__ == "__main__":
    main()
