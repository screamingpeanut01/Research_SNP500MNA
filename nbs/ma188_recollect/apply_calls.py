"""어닝콜 음성을 받아써서 확인한 결과를 earnings_call_note 칸에 반영한다 (2026-11-02).

대상: 2차 재수집 뒤에도 어닝콜 칸이 '미완'으로 남은 거래 가운데, 거래 연도와 다음 연도의 어닝콜 음성을
      구해 받아쓴 거래(CJ ENM 2018~2019, 카카오 2016 4Q~2020 2Q, NAVER 2018~2021).
방법: nbs/ma188_recollect/transcribe_calls.py로 받아쓰고, 대상회사 이름(한글·영문·옛 사명)을 검색했다.
      검색에 걸린 구간은 음성 조각으로 잘라 사람이 직접 들어 확인했다.
결과: CALLS에 거래마다 판정과 확인한 어닝콜 목록을 적는다. 언급이 있으면 '채움', 없으면 '공개 자료 없음'이다.

입력: data/ma188_missing_fields.csv, data/ma188_records/review_<deal_id>.json
실행(저장소 루트): python -X utf8 nbs/ma188_recollect/apply_calls.py [--dry]
그다음 시트 재생성: python -X utf8 nbs/ma188_build_sheet.py --out meeting/20261102 --merge data/ma188_records
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
REC = ROOT / "data" / "ma188_records"
MISS = ROOT / "data" / "ma188_missing_fields.csv"
CIQ_MAP = ROOT / "data" / "ma188_deal_ciq.csv"
MARK = "어닝콜 음성 확인(2026-11-02)"
FIELD = "earnings_call_note"

KAKAO_AOD = "https://www.kakaocorp.com/ir/referenceRoom/earningsAnnouncement (방송 듣기, teletogether 다시듣기)"
NAVER_AOD = "https://www.navercorp.com/investment/earnings (webcast, irsvc.teletogether.com 이메일 인증 뒤 다시듣기)"
CJ_AOD = "https://cjenmir.irplus.co.kr/kor/EarningsRelease (컨퍼런스콜 음성)"


def q(prefix, quarters):
    return ", ".join(f"{prefix} {x}" for x in quarters)


K16_17 = ["4Q16", "1Q17", "2Q17", "3Q17", "4Q17"]
K18_19 = ["1Q18", "2Q18", "3Q18", "4Q18", "1Q19", "2Q19", "3Q19", "4Q19"]
N18_19 = ["1Q18", "2Q18", "3Q18", "4Q18", "1Q19", "2Q19", "3Q19", "4Q19"]
N19_20 = ["1Q19", "2Q19", "3Q19", "4Q19", "1Q20", "2Q20", "3Q20", "4Q20"]
N20_21 = ["1Q20", "2Q20", "3Q20", "4Q20", "1Q21", "2Q21", "3Q21", "4Q21"]
N21 = ["1Q21", "2Q21", "3Q21", "4Q21"]
CJ18_19 = ["1Q18", "2Q18", "3Q18", "4Q18", "1Q19", "2Q19", "3Q19", "4Q19"]

# 거래마다: (확인한 어닝콜, 음성 출처, 검색어, 판정 값). 판정 값이 None이면 언급 없음.
CALLS = {
    "C015": (q("CJ E&M·CJ ENM", CJ18_19) + ", CJ오쇼핑 1Q18", CJ_AOD, "하이업, 하이 업, High up", None),
    "K010": (q("카카오", K16_17) + " (1Q16~3Q16은 IR 페이지에 음성이 없음)", KAKAO_AOD, "지니랩스, Zinny", None),
    "K011": (q("카카오", K16_17) + " (1Q16~3Q16은 IR 페이지에 음성이 없음)", KAKAO_AOD, "밸류포션, Value Potion", None),
    "K019": (q("카카오", K18_19), KAKAO_AOD, "페이브, Fave", None),
    "K023": (q("카카오", K18_19), KAKAO_AOD, "엔글, NGLE", None),
    "K024": (q("카카오", K18_19), KAKAO_AOD, "손노리, 로이게임즈", None),
    "K026": (q("카카오", K18_19), KAKAO_AOD, "플레이엠, 플랜에이, Play M Entertainment", None),
    "K031": (q("카카오", K18_19), KAKAO_AOD, "삼양씨앤씨, 삼양 CNC", None),
    "K040": (q("카카오", ["1Q20", "2Q20"]) + " (3Q20 이후는 녹취로 이미 확인)", KAKAO_AOD,
             "에이윈즈, 어윈즈, Awins, 키즈노트", None),
    "N042": (q("NAVER", N18_19), NAVER_AOD, "컴퍼니AI, 컴퍼니 에이아이, Company AI", None),
    "N045": (q("NAVER", N18_19), NAVER_AOD, "베트남 물류센터, 아시아그로쓰, 미래에셋 펀드", None),
    "N048": (q("NAVER", N19_20), NAVER_AOD, "컴퍼니AI, 컴퍼니 에이아이, Company AI", None),
    "N053": (q("NAVER", N20_21), NAVER_AOD, "와이랩, YLAB", None),
    "N056": (q("NAVER", N20_21), NAVER_AOD, "컴퍼니AI, 컴퍼니 에이아이, Company AI", None),
    "N069": (q("NAVER", N21) + " (2022는 녹취로 이미 확인)", NAVER_AOD, "비닷두, 브이닷, V.DO", None),
}


def main():
    dry = "--dry" in sys.argv
    to_ciq = pd.read_csv(CIQ_MAP, dtype=str).set_index("deal_id").ciq_id
    miss = pd.read_csv(MISS, dtype=str, keep_default_na=False)
    done = skip = 0
    for did, (calls, src, terms, hit) in CALLS.items():
        cid = to_ciq[did]
        k = (miss.ciq_id == cid) & (miss.field == FIELD)
        if not k.any():
            raise ValueError(f"{did}: 빈 항목 표에 어닝콜 칸이 없음")
        how = (f"어닝콜 음성을 받아써(whisper large-v3-turbo, 반복 구간은 large-v3로 다시 받아씀) "
               f"검색어 '{terms}'로 찾고, 걸린 구간은 들어서 확인함. 확인한 어닝콜: {calls}. 음성 출처: {src}.")
        if hit:
            row = {"class": "미완", "retry": "채움", "after": hit}
        else:
            row = {"class": "공개 자료 없음", "retry": "못 찾음",
                   "after": f"개별 언급 없음 (거래 연도·다음 연도 어닝콜 음성을 모두 받아써 확인: {calls})"}
        for col, v in row.items():
            miss.loc[k, col] = v
        miss.loc[k, "reason"] = miss.loc[k, "reason"] + f" / {MARK}: {how}"

        rv_path = REC / f"review_{did}.json"
        rv = json.loads(rv_path.read_text(encoding="utf-8"))
        if MARK in rv["review_note"]:
            skip += 1
            continue
        corr = rv["corrections"]
        corr[FIELD] = row["after"]
        corr["notes"] = corr.get("notes", "") + f" / {MARK}: {'언급 있음' if hit else '언급 없음'}."
        left = miss[(miss.ciq_id == cid) & (miss["class"] == "미완") & (miss.retry != "채움")]
        corr["collect_status"] = "완료" if left.empty else "부분"
        rv["evidence_add"].append({"field": FIELD, "phase": "인수 후", "event_date": "", "event_type": "어닝콜",
                                   "content": row["after"], "url": src.split(" ")[0], "doc_type": "어닝콜",
                                   "doc_date": "", "doc_id": ""})
        rv["review_note"] += f" / {MARK}: {how}"
        if not dry:
            rv_path.write_text(json.dumps(rv, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        done += 1
        print(did, cid, "언급 있음" if hit else "언급 없음", corr["collect_status"])
    print(f"반영 {done}건, 이미 반영돼 건너뜀 {skip}건")
    if not dry:
        miss.to_csv(MISS, index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
