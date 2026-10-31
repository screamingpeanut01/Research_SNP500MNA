"""M&A 188건 근거 사본의 목록(data/ma188_sources/manifest.csv)을 만든다.

사본은 두 곳에 있다.
- repo: data/ma188_sources/dart/  DART 공시 본문 텍스트(<접수번호>_<목차번호>.txt)
- archive: 저장소 밖 D:/KUfolio/Researches/MA188_sources/work/<작업폴더>/  수집·검토 중 받은 PDF·HTML·텍스트

작업폴더 이름은 유닛 번호(U###), 묶음 이름(KK-A 등), 검토 묶음(review_KK-A 등) 중 하나다.
유닛과 묶음이 다룬 거래 번호를 deals 열에 붙인다.

실행(저장소 루트): python -X utf8 nbs/ma188_collect/tools/make_source_manifest.py [archive 경로]
"""
import csv
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ARCHIVE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("D:/KUfolio/Researches/MA188_sources")
COLLECT = REPO / "nbs" / "ma188_collect"
OUT = REPO / "data" / "ma188_sources" / "manifest.csv"
SKIP = {".py", ".pyc"}


def folder_deals():
    m = {}
    for bf in (COLLECT / "batches").glob("*.json"):
        b = json.loads(bf.read_text(encoding="utf-8"))
        ids = [d["deal_id"] for d in b["deals"]]
        m[b["batch"]] = ids
        m["review_" + b["batch"]] = ids
    st = ARCHIVE / "units_state.json"
    if st.exists():
        for uid, u in json.loads(st.read_text(encoding="utf-8"))["units"].items():
            m[uid] = u["deals"]
    return m


def main():
    deals = folder_deals()
    rows = []
    for p in sorted((REPO / "data" / "ma188_sources" / "dart").glob("*.txt")):
        rows.append(["repo", p.relative_to(REPO).as_posix(), p.stat().st_size, "", "", p.name[:14]])
    for p in sorted((ARCHIVE / "work").rglob("*")):
        if not p.is_file() or p.suffix.lower() in SKIP:
            continue
        folder = p.relative_to(ARCHIVE / "work").parts[0]
        rcp = re.search(r"(?<!\d)(\d{14})(?!\d)", p.name)
        rows.append(["archive", p.relative_to(ARCHIVE).as_posix(), p.stat().st_size, folder,
                     " ".join(deals.get(folder, [])), rcp.group(1) if rcp else ""])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["location", "path", "size_bytes", "work_folder", "deals", "dart_rcp_no"])
        w.writerows(rows)
    print(f"{len(rows)}행 → {OUT.relative_to(REPO).as_posix()}")


if __name__ == "__main__":
    main()
