"""수집 기록 구조 점검: python -X utf8 check_records.py <records 폴더> <deal_id ...>"""
import json, sys
from pathlib import Path
COLS = ['subtype_chk','pre_incorp_chk','status_chk','value_chk_local','value_chk_usdmm','chk_note','notes',
        'announce_date_chk','acquirer_entity','purpose_quote','acquirer_core','is_core','core_basis',
        'acq_total_assets','apex_total_assets','deal_to_assets_pct','deal_to_equity_pct','acq_mktcap','size_basis',
        'event_ticker','event_ticker_basis','first_filing_date','pre_events_summary','post_events_summary',
        'impairment','target_rev_pre','target_rev_post','target_op_pre','target_op_post','perf_basis',
        'earnings_call_note','collect_status']
EV = ['field','phase','event_date','event_type','content','url','doc_type','doc_date','doc_id']
d = Path(sys.argv[1])
for did in sys.argv[2:]:
    p = d / f"{did}.json"
    if not p.exists():
        print(did, "기록 없음"); continue
    r = json.loads(p.read_text(encoding="utf-8")); sh = r["sheet"]
    miss = [c for c in COLS if c not in sh]; extra = [c for c in sh if c not in COLS]
    empty = [c for c in COLS if c in sh and not str(sh[c]).strip()]
    unk = [c for c in COLS if str(sh.get(c, "")).startswith("미확인")]
    bad = [e for e in r["evidence"] if set(EV) - set(e) or not e.get("url") or e.get("phase") not in ("인수 전", "발표", "인수 후")]
    ph = {k: sum(e.get("phase") == k for e in r["evidence"]) for k in ("인수 전", "발표", "인수 후")}
    flag = "OK" if not (miss or extra or empty or bad) else "점검 필요"
    print(f"{did} {flag} | 근거 {len(r['evidence'])} {ph} | {sh.get('collect_status')} | {sh.get('subtype_chk')}"
          + (f" | 빠진 열 {miss}" if miss else "") + (f" | 여분 열 {extra}" if extra else "")
          + (f" | 빈 값 {empty}" if empty else "") + (f" | 형식 오류 근거 {len(bad)}" if bad else "")
          + (f" | 미확인 {unk}" if unk else ""))
