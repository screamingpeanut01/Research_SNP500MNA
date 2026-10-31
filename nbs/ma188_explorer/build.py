"""수집 시트·근거 CSV를 탐색 페이지(template.html)에 넣어 meeting/20261102/MA188_탐색기.html을 만든다.

데이터를 JSON으로 바꿔 HTML 안에 넣으므로 결과 파일 하나만 있으면 열린다(글꼴만 Google Fonts에서 받는다).
실행(저장소 루트): python -X utf8 nbs/ma188_explorer/build.py
"""
import json, re, sys
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = REPO / "meeting/20261102/MA188_탐색기.html"
d = pd.read_csv(REPO / "meeting/20261102/MA188_수집시트.csv", dtype=str).fillna("")
e = pd.read_csv(REPO / "meeting/20261102/MA188_근거.csv", dtype=str).fillna("")

def code(s):
    m = re.search(r"MA[①-⑦]", s); return m.group(0) if m else ""
def imp(s):
    s = s.strip()
    for k in ("있음", "확인 안 됨", "해당 없음", "없음"):
        if s.startswith(k): return k
    return "기타"
def val(s):
    if s.startswith("원자료와 일치"): return "일치"
    if s.startswith("원자료와 불일치") or s.startswith("원자료 오류"): return "불일치"
    return "기타"
def pre(s): return s.split(" (")[0].split(":")[0].strip()

d["chk"] = d.subtype_chk.map(code)
d["imp"] = d.impairment_class.where(d.impairment_class != "", d.impairment.map(imp)); d["valc"] = d.value_chk_usdmm.map(val); d["prec"] = d.pre_incorp_chk.map(pre)
# v4 분야(cat·subcat)는 수집에서 확인하지 않아 싣지 않는다. 필요하면 ciq_id로 기초 CSV와 연결한다.
# 핵심 여부(is_core·core_basis)는 판정 근거가 부족하고 기준이 불명확해 싣지 않는다(2026-11-01).
# 10-19 규칙의 거래 형태(subtype)는 공시 확인 값(subtype_chk)으로 대체돼 싣지 않는다.
deals = d.drop(columns=["cat", "subcat", "is_core", "core_basis", "subtype"]).to_dict(orient="records")
ev = {}
for r in e.to_dict(orient="records"):
    ev.setdefault(r["ciq_id"], []).append([r["phase"], r["event_date"], r["event_type"], r["content"], r["url"], r["doc_type"], r["doc_date"], r["doc_id"], r["field"]])
payload = json.dumps({"deals": deals, "ev": ev}, ensure_ascii=False, separators=(",", ":")).replace("</", "<" + chr(92) + "/")
html = (HERE / "template.html").read_text(encoding="utf-8").replace("__DATA__", payload)
OUT.write_text(html, encoding="utf-8")
print(len(deals), "deals,", len(e), "evidence,", round(len(html.encode())/1e6, 2), "MB")
