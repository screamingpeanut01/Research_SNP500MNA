"""거래 형태 검수(2026-11-01)에 쓴 입력 묶음 inputs/part{1,2,3}.json을 만든다.

10-19 규칙의 거래 형태(subtype)와 수집 판정(subtype_chk)이 다른 45건을 시트 순서대로 15건씩 나누고,
거래마다 원자료 칸·두 판정·확인 메모와 관련 근거 행을 붙인다. 검수 에이전트 셋이 한 묶음씩 받아
보관한 공시 원문과 대조했고, 그 판정이 results/result{1,2,3}.json이다(합친 표: data/ma188_subtype_audit.csv).

주의: inputs/는 검수 당시(커밋 cd5e9a5)의 시트로 만든 사본이다. 검수 뒤 시트의 확인 메모 3건을 고쳤으므로,
지금 다시 실행하면 그 3건의 chk_note만 다르게 나온다.

실행(저장소 루트): python -X utf8 nbs/ma188_subtype_audit_work/make_parts.py <출력 폴더>
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FIELDS = ["ciq_id", "firm", "date", "target", "status", "value", "buyers", "sellers", "comment", "role", "stake",
          "subtype", "subtype_chk", "chk_note", "pre_incorp_chk", "notes", "acquirer_entity", "review_note"]


def code(s):
    m = re.search(r"MA[①-⑦]", s)
    return m.group(0) if m else ""


def main(out):
    out.mkdir(parents=True, exist_ok=True)
    d = pd.read_csv(ROOT / "meeting/20261102/MA188_수집시트.csv", dtype=str).fillna("")
    e = pd.read_csv(ROOT / "meeting/20261102/MA188_근거.csv", dtype=str).fillna("")
    ch = d[d.subtype.map(code) != d.subtype_chk.map(code)].reset_index(drop=True)
    for i in range(3):
        recs = []
        for r in ch.iloc[i * 15:(i + 1) * 15].itertuples():
            rec = {f: getattr(r, f) for f in FIELDS}
            ev = e[e.ciq_id == r.ciq_id]
            # 거래 형태 판단에 쓰일 근거: 분류·지분·당사자 칸을 뒷받침하는 행과 발표 시점의 행
            ev = ev[ev.field.str.contains("subtype|stake|buyer|seller|pre_incorp|분류|거래 형태") | (ev.phase == "발표")]
            rec["evidence"] = ev[["field", "phase", "event_date", "event_type", "content", "url", "doc_type",
                                  "doc_id"]].to_dict(orient="records")
            recs.append(rec)
        (out / f"part{i + 1}.json").write_text(json.dumps(recs, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
