"""검수 결과 results/result{1,2,3}.json을 합쳐 data/ma188_subtype_audit.csv를 만든다.

실행(저장소 루트): python -X utf8 nbs/ma188_subtype_audit_work/combine.py
"""
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1] / "data" / "ma188_subtype_audit.csv"


def main():
    r = pd.concat([pd.DataFrame(json.loads((HERE / "results" / f"result{i}.json").read_text(encoding="utf-8")))
                   for i in (1, 2, 3)])
    r = r.rename(columns={"subtype": "subtype_10_19", "subtype_chk": "subtype_chk_before"})
    cols = ["ciq_id", "target", "subtype_10_19", "subtype_chk_before", "verdict", "correct_code", "cause", "evidence", "note"]
    r[cols].to_csv(OUT, index=False, encoding="utf-8-sig")
    print(len(r), "건 →", OUT)


if __name__ == "__main__":
    main()
