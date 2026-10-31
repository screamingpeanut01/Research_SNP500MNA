"""DART 공시 조회 도구 (API 키 없이 공개 웹 화면을 조회한다).

사용 (python -X utf8 dart.py <명령> ...)
    corp <회사명>                         정확한 회사명으로 DART 고유번호(8자리) 조회. 여러 개면 공백으로 구분
    search <고유번호> <시작YYYYMMDD> <끝YYYYMMDD> [제목키워드]
                                          기간 안의 공시 목록(최대 10년). 제목키워드가 있으면 제목에 그 문자열이 든 것만
    toc <접수번호>                         문서 목차(번호, 제목). 사업보고서·감사보고서 등 여러 절로 된 문서용
    text <접수번호> [목차번호]              본문 텍스트. 목차번호를 빼면 첫 문서 전체
    url <접수번호>                          사람이 열어 볼 수 있는 공시 URL

요청 사이에 1초를 쉰다. 출력은 표준출력(UTF-8)이다.
"""
import html
import re
import sys
import time

import requests

BASE = "https://dart.fss.or.kr"
S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 (research; KU media lab)"


def _decode(r):
    # 거래소 공시(접수번호 9번째 자리 8) 본문은 EUC-KR이고 나머지는 UTF-8이다. 문서가 밝힌 charset을 따른다.
    head = r.content[:3000].decode("ascii", errors="ignore").lower()
    m = re.search(r"charset=[\"']?([\w-]+)", head) or re.search(r"charset=([\w-]+)", r.headers.get("content-type", "").lower())
    enc = m.group(1) if m else "utf-8"
    enc = "cp949" if enc in ("euc-kr", "ks_c_5601-1987", "ksc5601") else enc
    try:
        return r.content.decode(enc)
    except (LookupError, UnicodeDecodeError):
        return r.content.decode("utf-8", errors="replace")


def _get(url, **kw):
    time.sleep(1)
    r = S.get(url, timeout=30, **kw)
    r.raise_for_status()
    return _decode(r)


def _post(url, data):
    time.sleep(1)
    r = S.post(url, data=data, timeout=30)
    r.raise_for_status()
    return _decode(r)


def _plain(t):
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", t, flags=re.S | re.I)
    t = re.sub(r"<br\s*/?>|</p>|</tr>|</div>|</h\d>", "\n", t, flags=re.I)
    t = re.sub(r"</t[dh]>", " | ", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t)
    t = re.sub(r"[ \t\xa0]+", " ", t)
    t = re.sub(r"\s*\|\s*\n\s*", " | ", t)  # 표의 한 행을 한 줄로
    t = re.sub(r"(\s*\|\s*){2,}", " | ", t)
    t = re.sub(r"\n\s*\n+", "\n", t)
    return t.strip()


def corp(name):
    return _post(BASE + "/corp/searchExistAll.ax", {"textCrpNm": name}).strip()


def search(cik, start, end, kw=None):
    rows, page = [], 1
    while True:
        t = _post(BASE + "/dsab007/detailSearch.ax", {
            "currentPage": page, "maxResults": 100, "maxLinks": 10, "sort": "date", "series": "asc",
            "textCrpCik": cik, "startDate": start, "endDate": end, "businessCode": "all"})
        found = 0
        for m in re.finditer(r"<tr[^>]*>(.*?)</tr>", t, re.S):
            rc = re.search(r"rcpNo=(\d+)", m.group(1))
            if not rc:
                continue
            cells = [re.sub(r"\s+", " ", _plain(c)).replace(" |", "").strip()
                     for c in re.findall(r"<td[^>]*>(.*?)</td>", m.group(1), re.S)]
            found += 1
            title = re.sub(r"\s+", " ", cells[2]) if len(cells) > 2 else ""
            if kw and kw not in title.replace(" ", ""):
                continue
            rows.append((rc.group(1), cells[4] if len(cells) > 4 else "", cells[1] if len(cells) > 1 else "",
                         title, cells[3] if len(cells) > 3 else ""))
        tot = re.search(r"\[(\d+)/(\d+)\]", t)
        if not found or not tot or page >= int(tot.group(2)):
            break
        page += 1
    return rows


def _nodes(rcp):
    t = _get(BASE + "/dsaf001/main.do", params={"rcpNo": rcp})
    nodes = []
    for blk in re.findall(r"var node\d+ = \{\};(.*?)(?=var node\d+ = \{\};|$)", t, re.S):
        g = dict(re.findall(r"node\d+\['(\w+)'\] = \"([^\"]*)\";", blk))
        if g.get("dcmNo"):
            nodes.append(g)
    if not nodes:  # 목차가 없는 단일 문서
        m = re.search(r'viewDoc\("(\d+)", "(\d+)", "(\d+)", "(\d+)", "(\d+)", "([^"]+)"', t)
        if m:
            nodes.append({"text": "본문", "rcpNo": m.group(1), "dcmNo": m.group(2), "eleId": m.group(3),
                          "offset": m.group(4), "length": m.group(5), "dtd": m.group(6)})
    return nodes


def toc(rcp):
    return [(i, n.get("text", "")) for i, n in enumerate(_nodes(rcp))]


CACHE = __import__("pathlib").Path(__file__).resolve().parent.parent / "cache"


def text(rcp, idx=None):
    # 같은 문서를 두 번 받지 않도록 SP/cache/<접수번호>_<목차번호>.txt에 저장해 둔다.
    cf = CACHE / f"{rcp}_{idx if idx is not None else 'all'}.txt"
    if cf.exists():
        return cf.read_text(encoding="utf-8")
    out = _text(rcp, idx)
    CACHE.mkdir(exist_ok=True)
    cf.write_text(out, encoding="utf-8")
    return out


def _text(rcp, idx=None):
    nodes = _nodes(rcp)
    n = nodes[int(idx)] if idx is not None else nodes[0]
    if idx is None:  # 첫 문서 전체: 오프셋 없이 요청
        n = dict(n, eleId="0", offset="0", length="0")
    t = _get(BASE + "/report/viewer.do", params={
        "rcpNo": n["rcpNo"], "dcmNo": n["dcmNo"], "eleId": n["eleId"], "offset": n["offset"],
        "length": n["length"], "dtd": n["dtd"]})
    return _plain(t)


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "corp":
        print(corp(args[0]))
    elif cmd == "search":
        for r in search(*args[:3], kw=args[3] if len(args) > 3 else None):
            print(" | ".join(r))
    elif cmd == "toc":
        for i, t in toc(args[0]):
            print(i, t)
    elif cmd == "text":
        print(text(args[0], args[1] if len(args) > 1 else None))
    elif cmd == "url":
        print(f"{BASE}/dsaf001/main.do?rcpNo={args[0]}")
