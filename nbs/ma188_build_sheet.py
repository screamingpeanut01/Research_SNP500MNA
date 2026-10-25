"""M&A 188건 전후 이벤트·성과 레퍼런스 수집 시트 (2026-10-19 랩미팅 피드백 후속)

목적
    meeting/20261019/PP_MA_거래기록_역할분류.csv 의 M&A 188건을 거래 1행으로 펼친 수집 시트와
    출처 1행의 근거 시트를 만든다. 수집 항목은 현재_연구진행.md 의 To-do를 따른다.
    수집 자체는 출처를 찾아 읽고 기록하는 작업이다. 이 스크립트는 시트의 뼈대를 만들고,
    거래별 수집 기록과 검토 기록(JSON)을 시트에 합치는 일만 한다.

실행 (저장소 루트에서)
    python nbs/ma188_build_sheet.py --out <폴더>                    # 시트 생성·갱신
    python nbs/ma188_build_sheet.py --out <폴더> --merge <기록 폴더>  # 수집·검토 기록 반영

입력
    meeting/20261019/PP_MA_거래기록_역할분류.csv
    (--merge) <기록 폴더>/{deal_id}.json         수집 기록
              <기록 폴더>/review_{deal_id}.json  검토 기록

출력
    <폴더>/MA188_수집시트.csv  (188행, 거래 1행)
    <폴더>/MA188_근거.csv      (출처 1행. 인수 전·발표·인수 후 이벤트와 각 항목의 근거)

주의
    다시 실행해도 이미 수집한 열(COLLECT)은 deal_id로 맞춰 그대로 둔다. 기준 열(BASE)만 원자료에서 다시 만든다.
    deal_id는 기업 안에서 날짜·대상회사·금액 순으로 매긴다. 기준 CSV가 바뀌지 않는 한 같은 값이 나온다.
"""
import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "meeting" / "20261019" / "PP_MA_거래기록_역할분류.csv"
SHEET, EVID = "MA188_수집시트.csv", "MA188_근거.csv"

FIRMS = {"CJ ENM": "C", "Kakao": "K", "Naver": "N"}
MA = "Merger/Acquisition"
TOP_N = 50

BASE = ["deal_id", "value_rank", "top50", "event_group", "firm", "date", "target", "cat", "subcat",
        "status", "value", "buyers", "sellers", "comment", "role", "stake", "subtype", "pre_incorp",
        "value_flag"]
# 수집 열. 값은 모두 문자열로 적고, 금액·실적에는 연도와 단위를 함께 적는다(예: "2015: 매출 3,233억원").
COLLECT = [
    # 분류 확인: 기준 분류와 다르면 고친 값을 적고 chk_note에 근거를 남긴다.
    "subtype_chk", "pre_incorp_chk", "status_chk", "value_chk_local", "value_chk_usdmm", "chk_note", "notes",
    # 발표·목적
    "announce_date_chk", "acquirer_entity", "purpose_quote",
    # 인수 주체의 원래 핵심 영역
    "acquirer_core", "is_core", "core_basis",
    # 인수 시점 규모 (통화 단위를 값에 적는다). apex는 인수 주체가 속한 상장 지배회사(카카오, NAVER 등)
    "acq_total_assets", "apex_total_assets", "deal_to_assets_pct", "deal_to_equity_pct", "acq_mktcap",
    "size_basis",
    # 주가 이벤트 분석용
    "event_ticker", "event_ticker_basis", "first_filing_date",
    # 인수 전후 비교: 이벤트와 대상회사 실적 (실적은 인수 전 2년, 인수 후 2년 이상)
    "pre_events_summary", "post_events_summary", "impairment",
    "target_rev_pre", "target_rev_post", "target_op_pre", "target_op_post", "perf_basis", "earnings_call_note",
    # 진행 관리
    "collect_status", "collected_on", "review_status", "review_note",
]
EVID_COLS = ["deal_id", "field", "phase", "event_date", "event_type", "content", "url", "doc_type",
             "doc_date", "doc_id"]


def base_sheet():
    d = pd.read_csv(SRC, encoding="utf-8-sig")
    d = d[d["type"] == MA].copy()
    d["firm_order"] = d["firm"].map(list(FIRMS).index)
    d = d.sort_values(["firm_order", "date", "target", "value"]).reset_index(drop=True)
    d["deal_id"] = [f"{FIRMS[f]}{i:03d}" for f, i in zip(d["firm"], d.groupby("firm").cumcount() + 1)]
    d["value_rank"] = d["value"].rank(ascending=False, method="first").astype(int)
    d["top50"] = d["value_rank"] <= TOP_N
    d["pre_incorp"] = ""
    d.loc[d["yj_pre2021"], "pre_incorp"] = "Yahoo Japan 편입 전"
    d.loc[d["loen_pre"], "pre_incorp"] = "로엔 카카오 편입 전"
    # 같은 기업·같은 날짜·같은 매수자인 거래는 같은 사건일 수 있어 묶음 키를 붙인다(첫 행의 deal_id).
    key = d["firm"] + "|" + d["date"] + "|" + d["buyers"].fillna("-")
    first = d.groupby(key)["deal_id"].transform("first")
    size = d.groupby(key)["deal_id"].transform("size")
    d["event_group"] = first.where(size > 1, "")
    return d[BASE]


def load_existing(path, cols):
    if path.exists():
        return pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    return pd.DataFrame(columns=cols)


def merge_records(sheet, evid, paths):
    """주어진 순서대로 기록을 반영한다. 검토 기록의 정정(corrections)은 수집 값 위에 덮어쓴다."""
    sheet = sheet.set_index("deal_id")
    n_rec = n_rev = 0
    for p in paths:
        r = json.loads(p.read_text(encoding="utf-8"))
        did = r["deal_id"]
        if did not in sheet.index:
            raise KeyError(f"{p.name}: 시트에 없는 deal_id {did}")
        if p.name.startswith("review_"):
            for c, v in r.get("corrections", {}).items():
                if c not in COLLECT:
                    raise KeyError(f"{p.name}: 수집 열이 아닌 {c}")
                sheet.loc[did, c] = str(v)
            sheet.loc[did, "review_status"] = r["review_status"]
            sheet.loc[did, "review_note"] = r.get("review_note", "")
            drop = set(r.get("evidence_drop", []))
            evid = evid[~((evid["deal_id"] == did) & evid["url"].isin(drop))]
            add = pd.DataFrame(r.get("evidence_add", []), columns=EVID_COLS[1:]).assign(deal_id=did)
            evid = pd.concat([evid, add[EVID_COLS]], ignore_index=True)
            n_rev += 1
        else:
            for c, v in r.get("sheet", {}).items():
                if c not in COLLECT:
                    raise KeyError(f"{p.name}: 수집 열이 아닌 {c}")
                sheet.loc[did, c] = str(v)
            # 수집일은 수집 기록 파일을 마지막으로 쓴 날짜다.
            sheet.loc[did, "collected_on"] = date.fromtimestamp(p.stat().st_mtime).isoformat()
            # 같은 거래의 이전 근거는 지우고 새 기록으로 바꾼다.
            evid = evid[evid["deal_id"] != did]
            new = pd.DataFrame(r.get("evidence", []), columns=EVID_COLS[1:]).assign(deal_id=did)
            evid = pd.concat([evid, new[EVID_COLS]], ignore_index=True)
            n_rec += 1
    print(f"수집 기록 {n_rec}건, 검토 기록 {n_rev}건 반영")
    return sheet.reset_index(), evid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--merge", type=Path)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    base = base_sheet()
    old = load_existing(a.out / SHEET, BASE + COLLECT)
    keep = old[["deal_id"] + [c for c in COLLECT if c in old.columns]]
    sheet = base.merge(keep, on="deal_id", how="left")
    for c in COLLECT:
        sheet[c] = sheet[c].fillna("") if c in sheet.columns else ""
    evid = load_existing(a.out / EVID, EVID_COLS)

    if a.merge:
        # 수집 기록(K012.json)을 모두 반영한 뒤 검토 기록(review_K012.json)을 반영한다.
        recs = sorted(p for p in a.merge.glob("*.json") if not p.name.startswith("review_"))
        sheet, evid = merge_records(sheet, evid, recs + sorted(a.merge.glob("review_*.json")))

    sheet[BASE + COLLECT].to_csv(a.out / SHEET, index=False, encoding="utf-8-sig")
    evid[EVID_COLS].to_csv(a.out / EVID, index=False, encoding="utf-8-sig")

    s = sheet
    print(f"시트 {len(s)}행 (CJ ENM {sum(s.firm == 'CJ ENM')}, Kakao {sum(s.firm == 'Kakao')}, "
          f"Naver {sum(s.firm == 'Naver')}), 상위 {TOP_N}건 금액 비중 "
          f"{s.loc[s.top50.astype(str) == 'True', 'value'].astype(float).sum() / s.value.astype(float).sum():.1%}")
    print(f"사건 묶음 {s.event_group.replace('', pd.NA).nunique()}개, "
          f"수집 완료 {sum(s.collect_status == '완료')}건, 검토 통과 {sum(s.review_status == '통과')}건, "
          f"근거 {len(evid)}행")


if __name__ == "__main__":
    main()
