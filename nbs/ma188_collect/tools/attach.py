"""attach.py list <rcp>              -- list attachments (dcmNo, title)
   attach.py get <rcp> <dcmNo> <out>   -- download all sections of an attachment as plain text"""
import sys, time, re, html
sys.path.insert(0, r"C:/Users/1029l/AppData/Local/Temp/claude/D--KUfolio-Researches-Research-SNP500MNA/ccb194d9-de7b-4623-9724-9f6d514f1a86/scratchpad/tools")
import dart
cmd = sys.argv[1]; rcp = sys.argv[2]
if cmd == "list":
    t = dart._get(dart.BASE + "/dsaf001/main.do", params={"rcpNo": rcp})
    m = re.search(r'<select id="att".*?</select>', t, re.S)
    if m:
        for v, title in re.findall(r'<option value="rcpNo=\d+&amp;dcmNo=(\d+)"[^>]*>(.*?)</option>', m.group(0), re.S):
            print(v, re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", title))).strip())
else:
    dcm, out = sys.argv[3], sys.argv[4]
    t2 = dart._get(dart.BASE + "/dsaf001/main.do", params={"rcpNo": rcp, "dcmNo": dcm})
    nodes = []
    for blk in re.findall(r"var node\d+ = \{\};(.*?)(?=var node\d+ = \{\};|$)", t2, re.S):
        g = dict(re.findall(r"node\d+\['(\w+)'\] = \"([^\"]*)\";", blk))
        if g.get("dcmNo") == dcm:
            nodes.append(g)
    if not nodes:
        m = re.search(r'viewDoc\("(\d+)", "(\d+)", "(\d+)", "(\d+)", "(\d+)", "([^"]+)"', t2)
        if m:
            nodes = [{"text": "본문", "dcmNo": m.group(2), "eleId": m.group(3), "offset": m.group(4), "length": m.group(5), "dtd": m.group(6)}]
    parts = []
    for n in nodes:
        for a in range(3):
            try:
                r = dart._get(dart.BASE + "/report/viewer.do", params={"rcpNo": rcp, "dcmNo": n["dcmNo"], "eleId": n["eleId"], "offset": n["offset"], "length": n["length"], "dtd": n["dtd"]})
                break
            except Exception as e:
                r = f"[ERR {e}]"; time.sleep(5)
        parts.append("##### " + n.get("text", "") + "\n" + dart._plain(r))
    open(out, "w", encoding="utf-8").write("\n".join(parts))
    print(rcp, dcm, len(nodes), "nodes", sum(len(p) for p in parts), "chars")
