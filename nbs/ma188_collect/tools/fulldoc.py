"""fulldoc.py <out_txt> <rcp> [node_idx]  -- download whole main document (offset 0) as plain text"""
import sys, time
sys.path.insert(0, r"C:/Users/1029l/AppData/Local/Temp/claude/D--KUfolio-Researches-Research-SNP500MNA/ccb194d9-de7b-4623-9724-9f6d514f1a86/scratchpad/tools")
import dart
out, rcp = sys.argv[1], sys.argv[2]
idx = int(sys.argv[3]) if len(sys.argv) > 3 else 0
for a in range(3):
    try:
        nodes = dart._nodes(rcp); break
    except Exception as e:
        print("retry", e); time.sleep(5)
n = nodes[idx]
time.sleep(1)
r = dart.S.get(dart.BASE + "/report/viewer.do", params={"rcpNo": n["rcpNo"], "dcmNo": n["dcmNo"], "eleId": n["eleId"], "offset": "0", "length": "0", "dtd": n["dtd"]}, timeout=120)
t = dart._decode(r)
p = dart._plain(t)
open(out, "w", encoding="utf-8").write(p)
print(rcp, len(p), "chars;", len(nodes), "nodes")
