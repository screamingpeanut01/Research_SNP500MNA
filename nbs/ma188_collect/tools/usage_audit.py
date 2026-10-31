"""에이전트 기록(JSONL)에서 사용량만 집계한다. 내용은 출력하지 않는다.
python -X utf8 usage_audit.py <tasks 폴더> [agentId ...]"""
import json, sys, glob, os
from collections import defaultdict
d = sys.argv[1]
ids = sys.argv[2:] or [os.path.basename(p)[:-7] for p in glob.glob(os.path.join(d, "*.output"))]
rows = []
for aid in ids:
    p = os.path.join(d, aid + ".output")
    if not os.path.exists(p) or os.path.getsize(p) == 0: continue
    seen = set(); calls = 0; inp = cr = cc = out = 0; maxctx = 0
    tool_sizes = []; tool_name = {}
    for line in open(p, encoding="utf-8", errors="replace"):
        try: e = json.loads(line)
        except Exception: continue
        if e.get("type") == "assistant":
            m = e.get("message", {}); u = m.get("usage") or {}
            mid = m.get("id")
            if u and mid not in seen:
                seen.add(mid); calls += 1
                i, r, c, o = u.get("input_tokens", 0), u.get("cache_read_input_tokens", 0), u.get("cache_creation_input_tokens", 0), u.get("output_tokens", 0)
                inp += i; cr += r; cc += c; out += o; maxctx = max(maxctx, i + r + c)
            for b in m.get("content", []) or []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    inp_ = b.get("input", {})
                    desc = inp_.get("command") or inp_.get("url") or inp_.get("query") or inp_.get("file_path") or ""
                    tool_name[b["id"]] = (b.get("name"), str(desc)[:70].replace("\n", " "))
        elif e.get("type") == "user":
            for b in (e.get("message", {}).get("content") or []):
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    c = b.get("content"); n = len(json.dumps(c, ensure_ascii=False)) if c else 0
                    tool_sizes.append((n, b.get("tool_use_id")))
    tot = inp + cr + cc
    big = sorted(tool_sizes, reverse=True)[:5]
    rows.append((aid, calls, maxctx, inp, cc, cr, out, sum(n for n, _ in tool_sizes),
                 [(n, tool_name.get(t, ("?", ""))) for n, t in big]))
print(f"{'agent':18} {'calls':>5} {'maxctx':>8} {'uncached':>9} {'cache_w':>9} {'cache_r':>11} {'out':>7} {'tool_chars':>10}")
for r in sorted(rows, key=lambda r: -r[5]):
    print(f"{r[0]:18} {r[1]:5d} {r[2]:8d} {r[3]:9d} {r[4]:9d} {r[5]:11d} {r[6]:7d} {r[7]:10d}")
T = [sum(r[i] for r in rows) for i in range(1, 8)]
print("TOTAL calls", T[0], "uncached", T[2], "cache_write", T[3], "cache_read", T[4], "out", T[5], "tool_chars", T[6])
if "-v" in os.environ.get("AUDIT", ""):
    for r in rows:
        print(r[0]); [print("   ", n, nm) for n, nm in r[8]]
