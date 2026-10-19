"""PP·M&A 거래 기록의 실제 의미 검토 (2026-10-19 랩미팅 검토용)

목적
    S&P Capital IQ 원자료의 PP(Private Placement)·M&A(Merger/Acquisition) 기록이
    연구에서 대응시킨 개념(PP=외부 기업 투자, M&A=외부 기업 인수)과 얼마나 맞는지
    거래 단위로 확인한다. 결과 해설은 meeting/20261019/주차연구정리_20261019.md 에 있다.

실행 (저장소 루트에서)
    python nbs/pp_ma_record_audit.py

입력
    researchprep/KRMedia_051324_Transaction type_Target_Buyer_Total Transaction value_v4.xlsx
    researchprep/KRMedia_051324.xls  (xlrd 가 설치된 경우에만 [A-1]·[A-2] 원자료 부분 출력)

출력
    meeting/20261019/PP_MA_거래기록_역할분류.csv  (497건 거래별 분류 결과)
    표준출력: 문서에 인용한 모든 수치

주의
    그룹 회사 판정은 회사명 키워드와 '현재 자회사 목록(대상회사 이름)'에 기반한 휴리스틱이다.
    거래 당시 소속이 아니라 2024-05 추출 시점 기준이므로, 편입 전 거래도 그룹 거래로 잡힐 수 있다.
"""
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
V4 = ROOT / "researchprep" / "KRMedia_051324_Transaction type_Target_Buyer_Total Transaction value_v4.xlsx"
RAW = ROOT / "researchprep" / "KRMedia_051324.xls"
OUT_CSV = ROOT / "meeting" / "20261019" / "PP_MA_거래기록_역할분류.csv"

COLS = ["date", "target", "cat", "subcat", "type", "status", "value", "buyers", "sellers",
        "ma_date", "cond", "comment", "parents"]
FIRMS = ["CJ ENM", "Kakao", "Naver"]
PP, MA = "Private Placement", "Merger/Acquisition"

# 그룹 회사 판정 키워드. 대상회사 이름(=추출 시점의 현재 자회사)도 그룹 회사로 본다.
GROUP_KW = {
    "CJ ENM": r"\bCJ\b|On Media|M-net|Studio Dragon|Artworks Korea|DADA MNC|Tving|O Trend|dBase",
    "Kakao": r"Kakao|Daum|LOEN|Ground X|Krust|Metabora|Kross|Radish|Kids Note|Piccoma|Starship",
    "Naver": r"NAVER|Naver|\bLINE\b|\bLine\b|LY Corporation|A Holdings|SNOW|Kream|WEBTOON|Webtoon|"
             r"ValueCommerce|Z Holdings|Yahoo Japan|Demae-Can|Munpia|Wattpad",
}
# 수작업 판정: 설명란에 투자자 지위가 없지만 외부 기업에 신규 진입한 것이 확인된 거래.
# 근거: pptx 슬라이드 14 발표자 노트(NAVER의 BeNX 신주 인수, BeNX는 당시 빅히트(HYBE) 자회사).
MANUAL_EXTERNAL_ENTRY = [("Naver", "beNX Co., Ltd.", 2021)]
# 수작업 판정: 설명란 뒤쪽의 "additional" 때문에 추가지분으로 잘못 잡히는 과반 인수.
# 근거: 설명란 첫 문장 "acquire 80% stake in scripted business of IMG Worldwide".
MANUAL_STAKE = {"Scripted Business of IMG": "과반 인수(≥50%)"}
# LINE과 Z Holdings(Yahoo Japan)의 경영통합 완료 연도. 이전 Yahoo Japan 거래는 NAVER 편입 전 거래로 본다.
YJ_INTEGRATION_YEAR = 2021
YJ_PAT = r"LY Corporation|Z Holdings|Yahoo|ValueCommerce|ZOZO|ASKUL|Ikyu"
# UJU Electronics 3% 추가 취득: value 1,579.0으로 기록됐으나 설명란은 KRW 21.6 billion.
# 2021년 6월 환율 약 1,120원/달러를 가정한 달러 환산값(백만 달러).
UJU_CORRECTED = 21.6e3 / 1120
# [A-9] 금액 점검용 대략 환율(원/달러). 10배 이상 차이만 잡으므로 연도별 환율 차이는 결과에 영향이 없다.
KRW_PER_USD = 1150


def load():
    frames = []
    for s in FIRMS:
        d = pd.read_excel(V4, sheet_name=s)
        d.columns = COLS
        d["firm"] = s
        frames.append(d)
    d = pd.concat(frames, ignore_index=True)
    d["date"] = pd.to_datetime(d["date"], errors="coerce", format="mixed")
    d["year"] = d["date"].dt.year
    d["value"] = pd.to_numeric(d["value"], errors="coerce")
    for c in ["target", "cat", "buyers", "sellers", "comment", "parents"]:
        d[c] = d[c].fillna("-").astype(str).str.strip()
    d["cat"] = d["cat"].str.replace("Producation", "Production")
    return d


def parties(s):
    return [] if s in ("-", "") else [p.strip() for p in s.split(";") if p.strip()]


def section(title):
    print("\n" + "=" * 8, title, "=" * 8)


def share_table(df, by, total=None):
    g = df.groupby(by).agg(n=("value", "size"), value=("value", "sum"))
    g["share_%"] = 100 * g["value"] / (total if total is not None else g["value"].sum())
    return g.round(1)


def vso(x):
    p = x.loc[x.type == PP, "value"].sum()
    m = x.loc[x.type == MA, "value"].sum()
    return (p - m) / (p + m), p, m


def main():
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    allrows = load()

    # [A-1] 추출 기준, [A-2] 원자료 거래유형 분포 — xls 판독에 xlrd 필요
    section("[A-1] Screen Criteria / [A-2] 원자료 Transaction Types")
    try:
        import xlrd
        b = xlrd.open_workbook(RAW)
        sc = b.sheet_by_name("Screen Criteria")
        for r in range(sc.nrows):
            v = " ".join(str(x) for x in sc.row_values(r)).strip()
            if v:
                print("  ", v)
        sh = b.sheet_by_name("Screening")
        hdr = next(r for r in range(30) if "Transaction Types" in [str(v).strip() for v in sh.row_values(r)])
        col = [str(v).strip() for v in sh.row_values(hdr)].index("Transaction Types")
        raw_types = pd.Series([str(sh.cell_value(r, col)).strip() for r in range(hdr + 1, sh.nrows)])
        raw_types = raw_types[raw_types != ""]
        print("원자료 행 수:", len(raw_types))
        print(raw_types.value_counts().to_string())
    except ImportError:
        print("xlrd 미설치: 원자료(.xls) 부분은 건너뜀 (pip install xlrd)")
    print("\nv4 파일 기업별 거래유형:")
    print(allrows.groupby(["firm", "type"]).size().unstack(0).fillna(0).astype(int).to_string())

    # 분석 대상: researchprep 보고서와 같은 필터 (PP·M&A, 2005년 이후, value 존재)
    d = allrows[allrows.type.isin([PP, MA]) & (allrows.year >= 2005) & allrows.value.notna()].copy()
    assert len(d) == 497, len(d)
    print("\n분석 대상 행:", len(d), "(researchprep 보고서의 497행과 일치)")
    print("Parent Companies 열의 관계 표기:", d.parents.str.extract(r"\((Current Parent|Pending Parent[^)]*)\)")[0]
          .value_counts(dropna=False).to_dict())

    targets = {f: set(d[d.firm == f].target) for f in FIRMS}

    def is_group(name, firm):
        return bool(re.search(GROUP_KW[firm], name)) or name in targets[firm]

    def role(r):
        if r.type == PP:
            inv = parties(r.buyers)
            if not inv:
                return "PP-4 투자자 미기재"
            g = [is_group(p, r.firm) for p in inv]
            if all(g):
                return "PP-1 그룹 내부 출자"
            if not any(g):
                return "PP-2 외부 투자 유치"
            return "PP-3 그룹+외부 공동"
        b, s = parties(r.buyers), parties(r.sellers)
        if not b:
            return "MA-5 매수자 미기재"
        bg = any(is_group(p, r.firm) for p in b)
        sg = any(is_group(p, r.firm) for p in s)
        if bg and sg:
            return "MA-2 그룹 내부 재편"
        if bg:
            return "MA-1 그룹이 매수자"
        if sg:
            return "MA-3 그룹의 지분 매각"
        return "MA-4 외부자 간 거래"

    d["role"] = d.apply(role, axis=1)

    # [공통] 그룹 회사 판정의 근거: 데이터(대상회사 목록)인가, 작성자가 넣은 키워드인가
    section("[공통] 그룹 회사 판정 근거")
    src, kw_only = {"대상회사 목록(데이터)": 0, "키워드만(작성자 지식)": 0, "그룹 아님": 0}, {}
    for r in d.itertuples():
        for p in parties(r.buyers) + parties(r.sellers):
            if p in targets[r.firm]:
                src["대상회사 목록(데이터)"] += 1
            elif re.search(GROUP_KW[r.firm], p):
                src["키워드만(작성자 지식)"] += 1
                kw_only[(r.firm, p)] = kw_only.get((r.firm, p), 0) + 1
            else:
                src["그룹 아님"] += 1
    print("거래 당사자 판정 수:", src, "합계", sum(src.values()))
    for (f, p), n in sorted(kw_only.items(), key=lambda kv: -kv[1]):
        print(f"   키워드만: {f:6} {n:3d}  {p}")

    # [A-3] PP 그룹 역할
    section("[A-3] PP 기록의 그룹 역할")
    pp = d[d.type == PP]
    pp_total = pp.value.sum()
    print(f"PP 전체: {len(pp)}건, {pp_total:.1f}")
    print(share_table(pp, "role").to_string())
    print("\n기업별 건수·금액:")
    print(pp.groupby(["role", "firm"]).value.agg(["size", "sum"]).unstack("firm").round(1).fillna(0).to_string())

    # [A-4] 그룹이 신주를 산 PP: 기존 계열사 추가 출자인가, 외부 기업 신규 진입인가
    section("[A-4] 그룹 투자 PP의 진입 여부")
    d["tkey"] = d.target.str.replace(r"\s*\(.*?\)", "", regex=True).str.lower().str.strip()

    def comment_status(r):
        ginv = [p for p in parties(r.buyers) if is_group(p, r.firm)]
        out = set()
        for m in re.finditer(r"\b(new|existing|returning|current)\s+investors?\b([^.;]*)", r.comment, flags=re.I):
            for g in ginv:
                if re.search(re.escape(g.split()[0].strip("(),")), m.group(2)):
                    out.add(m.group(1).lower())
        if re.search(r"retain(s|ing)?\s+(its\s+)?100\s?%", r.comment, flags=re.I):
            out.add("retain100")
        return ",".join(sorted(out)) or "unspecified"

    def prior_group_deals(r):
        x = d[(d.firm == r.firm) & (d.tkey == r.tkey) & (d.date < r.date)]
        return sum(any(is_group(p, y.firm) for p in parties(y.buyers)) for y in x.itertuples())

    gpp = d[d.role.isin(["PP-1 그룹 내부 출자", "PP-3 그룹+외부 공동"])].copy()
    gpp["comment_status"] = gpp.apply(comment_status, axis=1)
    gpp["prior_group_deals"] = gpp.apply(prior_group_deals, axis=1)

    def entry(r):
        if (r.firm, r.target, r.year) in MANUAL_EXTERNAL_ENTRY:
            return "E2 외부 기업 신규 진입(수작업 확인)"
        if r.prior_group_deals > 0 or any(k in r.comment_status for k in ("existing", "returning", "current", "retain100")):
            return "E1 기존 계열사·투자처 추가 출자"
        if "new" in r.comment_status:
            return "E2 외부 기업 신규 진입"
        return "E3 판단 근거 없음(이름상 그룹 설립 자회사 추정)"

    gpp["entry"] = gpp.apply(entry, axis=1)
    d["entry"] = gpp["entry"]
    print(f"그룹이 신주를 산 PP: {len(gpp)}건, {gpp.value.sum():.1f}")
    print(share_table(gpp, "entry", total=pp_total).rename(columns={"share_%": "PP전체대비_%"}).to_string())
    for _, r in gpp[gpp.entry.str.startswith("E2")].iterrows():
        print(f"  신규 진입: {r.firm} {r.year} {r.target} {r.value:.1f} | {r.comment[:120]}")

    # [A-5] M&A 그룹 역할과 지분 규모
    section("[A-5] M&A 기록의 그룹 역할과 지분 규모")
    ma = d[d.type == MA]
    print(f"M&A 전체: {len(ma)}건, {ma.value.sum():.1f}")
    print(share_table(ma, "role").to_string())

    def stake(c):
        lc = c.lower()
        pm = re.search(r"(\d+(?:\.\d+)?)\s?%", c)
        pct = float(pm.group(1)) if pm else None
        if "merger" in lc and pct is None:
            return "합병"
        if "remaining" in lc:
            return "기존 자회사 잔여지분"
        if "additional" in lc:
            return "추가지분"
        if pct is None:
            return "지분율 미기재(대개 100%·사업양수)"
        return "과반 인수(≥50%)" if pct >= 50 else "소수지분(<50%)"

    mb = ma[ma.role == "MA-1 그룹이 매수자"].copy()
    mb["stake"] = mb.comment.apply(stake)
    for key, val in MANUAL_STAKE.items():
        mb.loc[mb.target.str.contains(key, regex=False), "stake"] = val
    d["stake"] = mb["stake"]
    print("\n그룹이 매수자인 M&A의 지분 규모(설명란 기준):")
    print(share_table(mb, "stake").sort_values("value", ascending=False).to_string())

    # [A-6] Naver: Yahoo Japan의 NAVER 편입 전 거래
    section("[A-6] Naver M&A 중 Yahoo Japan 편입 전 거래")
    nv = d[d.firm == "Naver"]
    yj = nv[(nv.buyers.str.contains(YJ_PAT) | nv.sellers.str.contains(YJ_PAT)
             | nv.comment.str.contains("Yahoo Japan|Z Holdings")) & (nv.year < YJ_INTEGRATION_YEAR)]
    for t in [MA, PP]:
        x, tot = yj[yj.type == t], nv[nv.type == t].value.sum()
        print(f"{t}: {len(x)}건, {x.value.sum():.1f} / Naver {t} 전체 {tot:.1f} ({100 * x.value.sum() / tot:.1f}%)")
    print(yj[yj.type == MA].sort_values("value", ascending=False)[["year", "target", "value", "buyers"]].head(6).to_string())
    d["yj_pre2021"] = d.index.isin(yj.index)

    # [A-7] 미팅 자료가 인용한 핵심 대비 칸의 구성
    section("[A-7] 미팅 자료 핵심 칸 분해")
    cells = [("CJ ENM", "Music & Fan Entertainment", MA), ("Kakao", "Technology & Infrastructure", PP),
             ("Kakao", "Music & Fan Entertainment", MA), ("Naver", "Music & Fan Entertainment", PP),
             ("Naver", "Mobility & Transportation", PP), ("Naver", "Mobility & Transportation", MA)]
    for firm, cat, t in cells:
        x = d[(d.firm == firm) & (d.cat == cat) & (d.type == t)]
        print(f"\n-- {firm} | {cat} | {t}: {len(x)}건, {x.value.sum():.1f}")
        print(share_table(x, "role").to_string())
        for _, r in x.sort_values("value", ascending=False).head(4).iterrows():
            print(f"   {r.year} {r.target[:34]:34} {r.value:8.1f} [{r.role}] 매수:{r.buyers[:35]} 매도:{r.sellers[:30]}")
    k4 = d[(d.firm == "Kakao") & (d.cat == "Music & Fan Entertainment") & (d.type == MA)]
    loen_pre = k4[(k4.year < 2016) & k4.buyers.str.contains("Kakao M")]  # 카카오의 로엔 인수 계약: 2016-01
    print(f"\nKakao Cat 4 M&A 중 카카오 편입 전 로엔(현 Kakao M)의 거래: {len(loen_pre)}건, {loen_pre.value.sum():.1f}"
          f" / {k4.value.sum():.1f} ({100 * loen_pre.value.sum() / k4.value.sum():.1f}%)")
    x = nv[(nv.cat == "Mobility & Transportation") & (nv.type == MA)]
    xy = x[x.index.isin(yj.index)]
    print(f"\nNaver Cat 9 M&A 중 Yahoo Japan 편입 전 거래: {xy.value.sum():.1f} / {x.value.sum():.1f} "
          f"({100 * xy.value.sum() / x.value.sum():.1f}%)")
    cj = d[(d.firm == "CJ ENM") & (d.type == MA)]
    cj_tot = cj.value.sum()
    print(f"\nCJ ENM M&A 전체 {cj_tot:.1f}")
    print(share_table(cj, "role", total=cj_tot).to_string())
    cjcorp = cj[cj.buyers.str.contains("CJ Corporation")].value.sum()
    print(f"상위 지주사 CJ㈜가 매수자인 거래: {cjcorp:.1f} ({100 * cjcorp / cj_tot:.1f}%)")

    # [A-8] VSO 민감도
    section("[A-8] 거래 한 건에 따른 VSO 변화")
    for firm, cat, drop in [("Naver", "Commerce & Marketing", "ZOZO"),
                            ("Naver", "Technology & Infrastructure", "UJU Electronics"),
                            ("CJ ENM", "Content Production & Investment", "Fifth Season")]:
        x = d[(d.firm == firm) & (d.cat == cat)]
        v0, p0, m0 = vso(x)
        v1, _, m1 = vso(x[~((x.type == MA) & x.target.str.contains(drop))])
        print(f"{firm} | {cat}: VSO {v0:+.3f} (PP {p0:.1f}, M&A {m0:.1f}) → {drop} M&A 제외 시 {v1:+.3f} (M&A {m1:.1f})")
        if drop == "UJU Electronics":
            v2 = (p0 - (m1 + UJU_CORRECTED)) / (p0 + m1 + UJU_CORRECTED)
            print(f"   UJU 금액을 설명란 기준 {UJU_CORRECTED:.1f}로 바로잡을 때: {v2:+.3f}")

    # [A-9] 금액 기록 점검: 설명란의 원화 금액과 value(백만 달러)가 10배 이상 어긋나는 거래
    section("[A-9] 설명란 원화 금액과 value 대조")
    unit = {"trillion": 1e6, "billion": 1e3, "million": 1.0}

    def krw_in_comment(c):
        m = re.search(r"KRW\s?([\d,]+(?:\.\d+)?)\s*(trillion|billion|million)", c)
        return float(m.group(1).replace(",", "")) * unit[m.group(2)] if m else None

    d["krw_mn"] = d.comment.apply(krw_in_comment)
    chk = d[d.krw_mn.notna()].copy()
    chk["usd_from_comment"] = chk.krw_mn / KRW_PER_USD
    chk["ratio"] = chk.value / chk.usd_from_comment
    flag = chk[(chk.ratio > 10) | (chk.ratio < 0.1)].sort_values("value", ascending=False)
    print(f"원화 금액이 적힌 거래 {len(chk)}건 중 10배 이상 어긋나는 거래 {len(flag)}건 (환율 {KRW_PER_USD}원/달러 가정)")
    for _, r in flag.iterrows():
        print(f"  {r.firm} {r.year} {r.target[:32]:32} [{r.type[:2]}] value {r.value:9.2f} | 설명란 KRW {r.krw_mn:,.0f}백만"
              f" ≈ {r.usd_from_comment:8.2f} | 배율 {r.ratio:8.1f} | {r.comment[:90]}")
    d["value_flag"] = d.index.isin(flag.index)
    x = d[(d.firm == "Kakao") & (d.cat == "Music & Fan Entertainment")]
    v0, p0, m0 = vso(x)
    et = x[(x.type == MA) & x.target.str.contains("E&T Story")]
    m1 = m0 - et.value.sum() + et.krw_mn.sum() / KRW_PER_USD
    print(f"Kakao | Music & Fan Entertainment: VSO {v0:+.3f}, M&A 비중 {100 * m0 / (p0 + m0):.1f}% → "
          f"E&T Story 금액을 설명란 기준으로 바로잡을 때 VSO {(p0 - m1) / (p0 + m1):+.3f}, M&A 비중 {100 * m1 / (p0 + m1):.1f}%")
    loen_pre_v = x[(x.type == MA) & (x.year < 2016) & x.buyers.str.contains("Kakao M")].value.sum()
    print(f"   바로잡은 M&A {m1:.1f} 중 카카오 편입 전 로엔 거래 {loen_pre_v:.1f} ({100 * loen_pre_v / m1:.1f}%)")

    # 편입 전 표시: Yahoo Japan의 2021년 이전 거래 + 카카오 인수(2016-01) 전 로엔(현 Kakao M)의 매수 거래
    d["loen_pre"] = (d.firm == "Kakao") & d.buyers.str.contains("Kakao M") & (d.year < 2016)
    d["pre"] = d.yj_pre2021 | d.loen_pre

    def subtype(r):
        if r.type == PP:
            if r.role.startswith(("PP-1", "PP-3")):
                return {"E1": "PP① 기존 계열사 추가 출자", "E3": "PP② 그룹 설립 자회사 출자(추정)",
                        "E2": "PP③ 외부 기업 신주 투자"}[r.entry[:2]]
            return {"PP-2": "PP④ 외부 투자자의 자회사 투자", "PP-4": "PP⑤ 투자자 미기재"}[r.role[:4]]
        if r.role.startswith("MA-1"):
            return {"과반 인수(≥50%)": "MA① 경영권 인수", "지분율 미기재(대개 100%·사업양수)": "MA① 경영권 인수",
                    "추가지분": "MA② 기존 지분 확대", "기존 자회사 잔여지분": "MA② 기존 지분 확대", "합병": "MA② 기존 지분 확대",
                    "소수지분(<50%)": "MA③ 소수지분 매입"}[r.stake]
        return {"MA-2": "MA④ 그룹 내부 재편", "MA-3": "MA⑤ 그룹의 지분 매각", "MA-4": "MA⑥ 외부자 간 거래",
                "MA-5": "MA⑦ 매수자 미기재"}[r.role[:4]]

    d["subtype"] = d.apply(subtype, axis=1)

    # [A-10] 그룹이 사는 쪽이었던 거래의 기업별 유형
    section("[A-10] 그룹이 사는 쪽이었던 거래의 기업별 유형")
    buy = d[d.role.isin(["PP-1 그룹 내부 출자", "PP-3 그룹+외부 공동", "MA-1 그룹이 매수자", "MA-2 그룹 내부 재편"])]
    macro = {"PP①": "E 자회사 출자(내부 육성)", "PP②": "E 자회사 출자(내부 육성)", "PP③": "F 외부 기업 신주 투자",
             "MA①": "A 경영권 인수", "MA②": "B 기존 지분 확대", "MA③": "C 소수지분 매입", "MA④": "D 그룹 내부 재편"}
    for f in FIRMS:
        x = buy[buy.firm == f].copy()
        x["macro"] = x.subtype.str[:3].map(macro)
        tot = x.value.sum()
        t = x.groupby("macro").agg(n=("value", "size"), value=("value", "sum"),
                                   편입전=("value", lambda s: s[x.loc[s.index, "pre"]].sum()),
                                   금액의심=("value", lambda s: s[x.loc[s.index, "value_flag"]].sum()))
        t["share_%"] = 100 * t.value / tot
        acq = x[(x.macro.str[0] == "A") & ~x.pre & ~x.value_flag].value.sum()
        inv = x[x.macro.str[0].isin(["C", "F"]) & ~x.pre & ~x.value_flag].value.sum()
        print(f"\n-- {f}: {len(x)}건, {tot:.1f} | 연구 개념의 인수(A) {100 * acq / tot:.1f}%, 외부 투자(C+F) {100 * inv / tot:.1f}%"
              f" (편입 전·금액 의심 제외)")
        print(t.round(1).to_string())

    # [A-11] 기업별 PP·M&A 세부 유형 (분석 대상 497건 전체)
    section("[A-11] 기업별 PP·M&A 세부 유형")
    for f in FIRMS:
        for t_ in [PP, MA]:
            x = d[(d.firm == f) & (d.type == t_)]
            tot = x.value.sum()
            g = x.groupby("subtype").agg(n=("value", "size"), value=("value", "sum"),
                                         편입전=("value", lambda s: s[x.loc[s.index, "pre"]].sum()),
                                         금액의심=("value", lambda s: s[x.loc[s.index, "value_flag"]].sum()))
            g["share_%"] = 100 * g.value / tot
            print(f"\n-- {f} | {t_}: {len(x)}건, {tot:.1f}")
            print(g.round(1).to_string())
            for s, z in x.groupby("subtype"):
                ex = z.sort_values("value", ascending=False).head(2)
                print(f"     {s}: " + "; ".join(f"{r.target[:28]} {r.year} {r.value:.1f}" for r in ex.itertuples()))

    # [A-12] 그룹이 관여하기 전의 외부 라운드, 같은 날 PP·M&A로 함께 잡힌 인수
    section("[A-12] 그룹 관여 이전의 외부 PP 라운드와 이중 집계 의심")
    first = buy.groupby(["firm", "target"]).date.min().rename("first_grp")
    x = d.join(first, on=["firm", "target"])
    ext = x[(x.type == PP) & x.role.isin(["PP-2 외부 투자 유치", "PP-4 투자자 미기재"])]
    pre_round = ext[ext.first_grp.notna() & (ext.date < ext.first_grp)]
    for f in FIRMS:
        a = pre_round[pre_round.firm == f]
        tot = d[(d.firm == f) & (d.type == PP)].value.sum()
        print(f"{f}: 그룹 최초 관여 이전의 외부 PP 라운드 {len(a)}건, {a.value.sum():.1f} (PP의 {100 * a.value.sum() / tot:.1f}%)")
        for r in a.sort_values("value", ascending=False).head(4).itertuples():
            print(f"   {r.target[:30]:30} {r.year} {r.value:7.1f} (그룹 최초 관여 {r.first_grp.year}) 투자자: {r.buyers[:40]}")
    d["pre_round"] = d.index.isin(pre_round.index)
    pos = d[(d.firm == "Naver") & d.target.str.contains("Proton Parent|Poshmark") & (d.year == 2022)]
    print("\n같은 날 기록된 Proton Parent PP와 Poshmark M&A:")
    for r in pos.itertuples():
        print(f"   {r.date.date()} {r.type} {r.target[:30]} {r.value:.1f} | {r.comment[:110]}")

    # [A-13] 견고성: 판단이 안 되는 거래를 극단적으로 가정해도 결론이 유지되는가
    section("[A-13] 견고성 점검")
    print("PP 중 외부 기업 신주 투자 비중: 현재 / 상한(투자자 미기재·그룹 설립 추정을 전부 외부 투자로 가정)")
    for f in FIRMS:
        p_ = d[(d.firm == f) & (d.type == PP)]
        tot = p_.value.sum()
        base = p_[p_.subtype.str.startswith("PP③")].value.sum()
        unk = p_[p_.subtype.str.startswith(("PP②", "PP⑤"))]
        ub = base + unk.value.sum()
        ub2 = ub - unk[unk.target.str.contains("Proton Parent")].value.sum()
        print(f"   {f:6}: {100 * base / tot:5.1f}% / {100 * ub / tot:5.1f}% (Proton Parent 제외 상한 {100 * ub2 / tot:5.1f}%)")
    print("M&A 중 경영권 인수 비중: 엄격 / +단계적 경영권 인수(Tapas·Radish 2021) / +편입 전 거래 인정 (금액 의심 제외)")
    step = d.target.str.contains("Tapas Media|Radish Media") & (d.year == 2021) & (d.role == "MA-1 그룹이 매수자")
    for f in FIRMS:
        m_ = d[(d.firm == f) & (d.type == MA)]
        tot = m_.value.sum()
        A = m_.subtype.str.startswith("MA①")
        st = step.loc[m_.index]
        r1 = m_[A & ~m_.pre & ~m_.value_flag].value.sum()
        r2 = m_[(A | st) & ~m_.pre & ~m_.value_flag].value.sum()
        r3 = m_[(A | st) & ~m_.value_flag].value.sum()
        print(f"   {f:6}: {100 * r1 / tot:5.1f}% / {100 * r2 / tot:5.1f}% / {100 * r3 / tot:5.1f}%")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    keep = ["firm", "date", "year", "target", "cat", "subcat", "type", "status", "value", "buyers", "sellers",
            "role", "entry", "stake", "subtype", "yj_pre2021", "loen_pre", "pre_round", "value_flag", "comment"]
    d[keep].sort_values(["firm", "date"]).to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n저장: {OUT_CSV.relative_to(ROOT)} ({len(d)}행)")


if __name__ == "__main__":
    main()
