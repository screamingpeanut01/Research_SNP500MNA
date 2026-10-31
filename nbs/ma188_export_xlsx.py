"""M&A 188건 수집 시트와 근거 CSV를 보기 쉬운 엑셀 파일로 만든다.

저장소 루트에서 실행: python -X utf8 nbs/ma188_export_xlsx.py
입력: meeting/20261102/MA188_수집시트.csv, MA188_근거.csv
출력: meeting/20261102/MA188_수집시트.xlsx (시트: 안내, 요약, 거래, 근거)

'요약' 시트의 수치는 '거래' 시트를 COUNTIFS로 세는 수식이다.
'거래' 시트의 '분류 요약' 열(원자료 코드, 확인 코드, 분류 변경, 손상 구분, 금액 대조)은
nbs/ma188_summary.py와 같은 규칙으로 이 스크립트가 원래 열에서 뽑은 값이다.
"""
import re
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

DIR = Path("meeting/20261102")
OUT = DIR / "MA188_수집시트.xlsx"
FONT = "맑은 고딕"

# (그룹, 열 키, 표시 이름, 폭, 줄바꿈)
COLS = [
    ("식별", "ciq_id", "CIQ ID", 16, False), ("식별", "firm", "기업", 9, False), ("식별", "date", "날짜", 11, False),
    ("식별", "target", "대상회사", 30, True), ("식별", "value_rank", "금액 순위", 7, False),
    ("식별", "top50", "상위 50", 7, False), ("식별", "event_group", "사건 묶음", 9, False),
    ("분류 요약", "_base", "거래 형태 (설명란 판정)", 11, False), ("분류 요약", "_chk", "거래 형태 (공시 확인)", 11, False),
    ("분류 요약", "_chg", "형태 변경", 8, False), ("분류 요약", "impairment_class", "손상 구분", 11, False),
    ("분류 요약", "_val", "금액 대조", 8, False), ("분류 요약", "_pre", "편입 시점", 14, False),
    ("원자료 (Capital IQ)", "status", "상태", 10, False), ("원자료 (Capital IQ)", "value", "금액 $M", 11, False),
    ("원자료 (Capital IQ)", "buyers", "매수자", 26, True), ("원자료 (Capital IQ)", "sellers", "매도자", 26, True),
    ("원자료 (Capital IQ)", "comment", "설명란", 60, True),
    ("10-19 설명란 판정", "role", "그룹 역할 (설명란 판정)", 18, True),
    ("10-19 설명란 판정", "stake", "지분 규모 (설명란 판정)", 14, True),
    ("10-19 설명란 판정", "subtype", "거래 형태 (설명란 판정)", 16, True),
    ("10-19 설명란 판정", "pre_incorp", "편입 전 표시 (배경지식)", 14, True),
    ("10-19 설명란 판정", "value_flag", "금액 의심 (설명란 대조)", 9, False),
    ("공시 확인", "subtype_chk", "거래 형태 (공시 확인)", 30, True), ("공시 확인", "pre_incorp_chk", "편입 시점 (공시 확인)", 40, True),
    ("공시 확인", "status_chk", "상태 (공시 확인)", 26, True), ("공시 확인", "value_chk_local", "금액 확인 (현지 통화)", 40, True),
    ("공시 확인", "value_chk_usdmm", "금액 확인 ($M)", 40, True), ("공시 확인", "announce_date_chk", "발표일", 24, True),
    ("공시 확인", "chk_note", "확인 메모", 60, True), ("공시 확인", "notes", "특이사항", 60, True),
    ("인수 목적·핵심", "acquirer_entity", "인수 주체", 30, True), ("인수 목적·핵심", "purpose_quote", "발표 당시 목적", 50, True),
    ("인수 목적·핵심", "acquirer_core", "인수 주체 주력 사업", 30, True), ("인수 목적·핵심", "is_core", "핵심 여부", 16, True),
    ("인수 목적·핵심", "core_basis", "핵심 판정 근거", 40, True),
    ("규모", "acq_total_assets", "인수 주체 총자산", 30, True), ("규모", "apex_total_assets", "그룹 정점 총자산", 30, True),
    ("규모", "deal_to_assets_pct", "총자산 대비", 22, True), ("규모", "deal_to_equity_pct", "자기자본 대비", 22, True),
    ("규모", "acq_mktcap", "시가총액", 30, True), ("규모", "size_basis", "규모 기준", 40, True),
    ("주가 이벤트", "event_ticker", "종목", 16, True), ("주가 이벤트", "event_ticker_basis", "종목 근거", 30, True),
    ("주가 이벤트", "first_filing_date", "처음 알려진 날", 24, True),
    ("전후 이벤트", "pre_events_summary", "인수 전 사건", 60, True), ("전후 이벤트", "post_events_summary", "인수 후 사건", 60, True),
    ("전후 이벤트", "impairment", "손상", 50, True),
    ("전후 이벤트", "impairment_class_basis", "손상 구분 근거", 40, True),
    ("성과", "target_rev_pre", "매출 (인수 전)", 36, True), ("성과", "target_rev_post", "매출 (인수 후)", 36, True),
    ("성과", "target_op_pre", "영업이익 (인수 전)", 36, True), ("성과", "target_op_post", "영업이익 (인수 후)", 36, True),
    ("성과", "perf_basis", "실적 기준", 40, True), ("성과", "earnings_call_note", "어닝콜·IR 언급", 40, True),
    ("수집", "collect_status", "수집 상태", 8, False), ("수집", "collected_on", "수집 일시", 17, False),
]
EV_COLS = [("ciq_id", "CIQ ID", 16, False), ("_target", "대상회사", 26, True), ("phase", "시점", 8, False),
           ("event_date", "사건 날짜", 12, False), ("event_type", "사건 종류", 16, True), ("content", "내용", 70, True),
           ("doc_type", "문서 종류", 16, True), ("doc_date", "문서 날짜", 12, False), ("doc_id", "문서 번호", 18, False),
           ("url", "URL", 45, False), ("field", "뒷받침하는 열", 30, True)]

GROUP_FILL = {"식별": "1F4E4C", "분류 요약": "0F5C5A", "원자료 (Capital IQ)": "5C6B67", "10-19 설명란 판정": "6B5A3E", "공시 확인": "7A4E00",
              "인수 목적·핵심": "3E5C2E", "규모": "34506E", "주가 이벤트": "4E3F6E", "전후 이벤트": "8A2E2E",
              "성과": "2E5E6E", "수집": "4A4A4A"}
IMP_CLASSES = ["있음", "없음 (확인)", "식별 불가", "미확인", "해당 없음"]
NAMES = {"MA①": "경영권 인수", "MA②": "기존 지분 확대", "MA③": "소수지분 매입", "MA④": "그룹 내부 재편",
         "MA⑤": "그룹의 지분 매각", "MA⑥": "외부자 간 거래", "MA⑦": "매수자 미기재"}
thin = Side(style="thin", color="D3DCD9")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)


def fill(hex_):
    return PatternFill("solid", fgColor=hex_)


def code(s):
    m = re.search(r"MA[①-⑦]", s)
    return m.group(0) if m else ""


def val_class(s):
    if s.startswith("원자료와 일치"):
        return "일치"
    if s.startswith("원자료와 불일치") or s.startswith("원자료 오류"):
        return "불일치"
    return "기타"


def header(ws, row, labels, widths, fill_hex="DDEBF7", color="17211F"):
    for i, (lab, w) in enumerate(zip(labels, widths), 1):
        c = ws.cell(row=row, column=i, value=lab)
        c.font = Font(name=FONT, bold=True, color=color, size=10)
        c.fill = fill(fill_hex)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BORDER
        ws.column_dimensions[get_column_letter(i)].width = w


def deals_sheet(wb, d):
    ws = wb.create_sheet("거래")
    # 1행: 열 묶음, 2행: 열 이름, 3행: CSV 열 키
    start = 1
    for i, (g, *_rest) in enumerate(COLS + [(None,)], 1):
        if i > len(COLS) or g != COLS[start - 1][0]:
            grp = COLS[start - 1][0]
            ws.merge_cells(start_row=1, start_column=start, end_row=1, end_column=i - 1)
            c = ws.cell(row=1, column=start, value=grp)
            c.font = Font(name=FONT, bold=True, color="FFFFFF", size=10)
            c.alignment = Alignment(horizontal="center", vertical="center")
            for j in range(start, i):
                ws.cell(row=1, column=j).fill = fill(GROUP_FILL[grp])
            start = i
    header(ws, 2, [c[2] for c in COLS], [c[3] for c in COLS])
    for i, c in enumerate(COLS, 1):
        k = ws.cell(row=3, column=i, value=c[1] if not c[1].startswith("_") else "(파생)")
        k.font = Font(name=FONT, size=8, color="5C6B67")
        k.alignment = Alignment(horizontal="center")
        k.fill = fill("F3F6F5")
    for r, rec in enumerate(d.to_dict(orient="records"), 4):
        for i, (_g, key, _l, _w, wrap) in enumerate(COLS, 1):
            v = rec[key]
            if key in ("value",) and v:
                v = float(v)
            elif key in ("value_rank",) and v:
                v = int(float(v))
            cell = ws.cell(row=r, column=i, value=v if v != "" else None)
            cell.font = Font(name=FONT, size=9.5)
            cell.alignment = Alignment(wrap_text=wrap, vertical="top")
            cell.border = BORDER
            if key == "value":
                cell.number_format = "#,##0.00"
        ws.row_dimensions[r].height = 72
    last = 3 + len(d)
    ws.row_dimensions[1].height = 18
    ws.row_dimensions[2].height = 30
    ws.freeze_panes = "E4"
    ws.auto_filter.ref = f"A3:{get_column_letter(len(COLS))}{last}"
    col = {c[1]: get_column_letter(i) for i, c in enumerate(COLS, 1)}
    rng = f"A4:{get_column_letter(len(COLS))}{last}"
    # 행 강조: 손상 있음(연한 빨강) 표시는 손상 구분 칸에만, 분류 변경은 확인 분류 칸에
    for key, rule, color in [
        ("impairment_class", f'${col["impairment_class"]}4="있음"', "FBE4E1"),
        ("impairment_class", f'${col["impairment_class"]}4="없음 (확인)"', "DFF1E4"),
        ("impairment_class", f'OR(${col["impairment_class"]}4="식별 불가",${col["impairment_class"]}4="미확인")', "FBEFD9"),
        ("_chk", f'${col["_chg"]}4="변경"', "D5EBE8"), ("_chg", f'${col["_chg"]}4="변경"', "D5EBE8"),
        ("_val", f'${col["_val"]}4="불일치"', "FBE4E1"),
        ("collect_status", f'${col["collect_status"]}4="완료"', "DFF1E4"),
    ]:
        ws.conditional_formatting.add(f"{col[key]}4:{col[key]}{last}", FormulaRule(formula=[rule], fill=fill(color)))
    del rng
    return ws, col, last


def evidence_sheet(wb, e, targets):
    ws = wb.create_sheet("근거")
    header(ws, 1, [c[1] for c in EV_COLS], [c[2] for c in EV_COLS])
    for r, rec in enumerate(e.to_dict(orient="records"), 2):
        rec["_target"] = targets.get(rec["ciq_id"], "")
        for i, (key, _l, _w, wrap) in enumerate(EV_COLS, 1):
            v = rec[key]
            cell = ws.cell(row=r, column=i, value=v if v != "" else None)
            cell.font = Font(name=FONT, size=9.5)
            cell.alignment = Alignment(wrap_text=wrap, vertical="top")
            cell.border = BORDER
            if key == "url" and v.startswith("http"):
                cell.hyperlink = v
                cell.font = Font(name=FONT, size=9.5, color="0F5C5A", underline="single")
        ws.row_dimensions[r].height = 45
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(EV_COLS))}{len(e) + 1}"
    ws.conditional_formatting.add(f"C2:C{len(e) + 1}", FormulaRule(formula=['$C2="인수 전"'], fill=fill("E8EEEC")))
    ws.conditional_formatting.add(f"C2:C{len(e) + 1}", FormulaRule(formula=['$C2="발표"'], fill=fill("D5EBE8")))
    ws.conditional_formatting.add(f"C2:C{len(e) + 1}", FormulaRule(formula=['$C2="인수 후"'], fill=fill("FBEFD9")))


def summary_sheet(wb, col, last):
    ws = wb.create_sheet("요약", 1)
    R = lambda k: f"거래!${col[k]}$4:${col[k]}${last}"
    bold = Font(name=FONT, bold=True, size=10)
    norm = Font(name=FONT, size=10)
    ws.column_dimensions["A"].width = 26
    for c in "BCDEFGHI":
        ws.column_dimensions[c].width = 12
    row = 1
    ws.cell(row=row, column=1, value="M&A 188건 수집 결과 요약").font = Font(name=FONT, bold=True, size=13)
    row += 1
    ws.cell(row=row, column=1, value="모든 수치는 '거래' 시트를 세는 수식이다. '거래' 시트를 고치면 함께 바뀐다.").font = Font(name=FONT, size=9, color="5C6B67")

    def table(title, row_vals, col_vals, row_key, col_key, extra=None, row_label=None):
        nonlocal row
        row += 2
        ws.cell(row=row, column=1, value=title).font = bold
        row += 1
        heads = [row_label or ""] + [c if col_key != "_chk" else f"{c} {NAMES[c]}" for c in col_vals] + ["합계"]
        for i, h in enumerate(heads, 1):
            c = ws.cell(row=row, column=i, value=h)
            c.font = bold; c.fill = fill("DDEBF7"); c.border = BORDER
            c.alignment = Alignment(horizontal="center", wrap_text=True, vertical="center")
        ws.row_dimensions[row].height = 32 if col_key == "_chk" else 18
        top = row + 1
        for rv in row_vals:
            row += 1
            lab = rv if row_key != "_base" else f"{rv} {NAMES[rv]}"
            ws.cell(row=row, column=1, value=lab).font = norm
            for j, cv in enumerate(col_vals, 2):
                crit = f'{R(row_key)},$A{row}' if row_key != "_base" else f'{R(row_key)},"{rv}"'
                f = f'=COUNTIFS({crit},{R(col_key)},"{cv}"' + (f",{extra}" if extra else "") + ")"
                c = ws.cell(row=row, column=j, value=f); c.font = norm; c.border = BORDER
            s = ws.cell(row=row, column=len(col_vals) + 2,
                        value=f"=SUM({get_column_letter(2)}{row}:{get_column_letter(len(col_vals) + 1)}{row})")
            s.font = bold; s.border = BORDER
            ws.cell(row=row, column=1).border = BORDER
        row += 1
        ws.cell(row=row, column=1, value="합계").font = bold
        for j in range(2, len(col_vals) + 3):
            L = get_column_letter(j)
            c = ws.cell(row=row, column=j, value=f"=SUM({L}{top}:{L}{row - 1})"); c.font = bold; c.border = BORDER

    firms = ["CJ ENM", "Kakao", "Naver"]
    table("기업별 수집 상태", firms, ["완료", "부분"], "firm", "collect_status", row_label="기업")
    codes_b = ["MA①", "MA②", "MA③", "MA④", "MA⑤", "MA⑥", "MA⑦"]
    codes_c = ["MA①", "MA②", "MA③", "MA④", "MA⑤", "MA⑥"]
    table("거래 형태: 설명란 판정(행) → 공시 확인(열)", codes_b, codes_c, "_base", "_chk", row_label="설명란 판정")
    table("기업별 손상 구분 (188건 전체)", firms, IMP_CLASSES, "firm", "impairment_class", row_label="기업")
    table("기업별 편입 시점 판정", firms, ["편입 후", "편입 전", "지분법 합작 계열"], "firm", "_pre", row_label="기업")
    table("기업별 금액 대조", firms, ["일치", "불일치", "기타"], "firm", "_val", row_label="기업")
    row += 2
    ws.cell(row=row, column=1, value="그룹이 산 거래(확인 분류 MA①②③)의 손상").font = bold
    row += 1
    heads = ["기업", "거래"] + IMP_CLASSES + ["손상 비율 (있음 ÷ (있음+없음))"]
    for i, h in enumerate(heads, 1):
        c = ws.cell(row=row, column=i, value=h); c.font = bold; c.fill = fill("DDEBF7"); c.border = BORDER
        c.alignment = Alignment(horizontal="center", wrap_text=True, vertical="center")
    ws.row_dimensions[row].height = 32
    top = row + 1
    buy = ("MA①", "MA②", "MA③")
    last_c = len(heads)
    for f in firms:
        row += 1
        ws.cell(row=row, column=1, value=f).font = norm
        ws.cell(row=row, column=2, value="=" + "+".join(f'COUNTIFS({R("firm")},$A{row},{R("_chk")},"{c}")' for c in buy))
        for j, k in enumerate(IMP_CLASSES, 3):
            ws.cell(row=row, column=j, value="=" + "+".join(
                f'COUNTIFS({R("firm")},$A{row},{R("_chk")},"{c}",{R("impairment_class")},"{k}")' for c in buy))
        p = ws.cell(row=row, column=last_c, value=f"=IF(C{row}+D{row}=0,0,C{row}/(C{row}+D{row}))")
        p.number_format = "0.0%"
        for j in range(1, last_c + 1):
            ws.cell(row=row, column=j).border = BORDER
    row += 1
    ws.cell(row=row, column=1, value="합계").font = bold
    for j in range(2, last_c):
        L = get_column_letter(j)
        ws.cell(row=row, column=j, value=f"=SUM({L}{top}:{L}{row - 1})").font = bold
    p = ws.cell(row=row, column=last_c, value=f"=IF(C{row}+D{row}=0,0,C{row}/(C{row}+D{row}))")
    p.number_format = "0.0%"; p.font = bold
    row += 1
    ws.cell(row=row, column=1, value="손상 구분은 data/ma188_impairment_class.csv(nbs/ma188_impairment_class.py)의 판정이다. 손상 비율은 판정할 수 있는 거래(있음·없음) 안에서 계산했다.").font = Font(name=FONT, size=9, color="5C6B67")
    ws.freeze_panes = "A3"


def guide_sheet(wb, n, ne):
    ws = wb.active
    ws.title = "안내"
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 100
    lines = [
        ("M&A 188건 수집 시트", None),
        ("", None),
        ("원본", "meeting/20261102/MA188_수집시트.csv, MA188_근거.csv (이 파일은 그 CSV를 nbs/ma188_export_xlsx.py로 옮긴 것)"),
        ("내용", f"CJ ENM 30·Kakao 74·Naver 84, 거래 {n}건과 근거 {ne}행. 설계와 결과 해석은 meeting/20261102/주차연구정리_20261102.md"),
        ("시트", None),
        ("  요약", "기업별 수집 상태, 분류 대조표, 손상·편입 시점·금액 대조 집계. 모두 '거래' 시트를 세는 수식"),
        ("  거래", "한 행이 한 거래. 1행은 열 묶음, 2행은 열 이름, 3행은 CSV 열 이름이며 3행에 필터가 있다. 거래·기업·날짜·대상회사 열은 고정"),
        ("  근거", "한 행이 근거 하나. URL을 누르면 원문이 열린다. '뒷받침하는 열'은 그 근거가 '거래' 시트의 어느 열 값을 뒷받침하는지 적은 것"),
        ("열 묶음", None),
        ("  식별", "CIQ ID(Capital IQ의 CIQ Transaction ID), 기업, 날짜, 대상회사, 원자료 금액 순위"),
        ("  분류 요약 (파생)", "원래 열에서 뽑은 값. 거래 형태 (설명란 판정)·거래 형태 (공시 확인)(MA①~⑦ 코드), 형태 변경(변경/같음), 손상 구분(있음 / 없음 (확인) / 식별 불가 / 미확인 / 해당 없음, 근거는 '손상 구분 근거' 열), 금액 대조(일치/불일치/기타), 편입 시점"),
        ("  원자료 (Capital IQ)", "Capital IQ에서 추출한 그대로의 값: 상태, 금액, 매수자, 매도자, 설명란"),
        ("  10-19 설명란 판정", "10-19 분석(nbs/pp_ma_record_audit.py)이 설명란·매수자·매도자 칸을 규칙으로 읽어 붙인 값. 편입 전 표시는 작성자의 배경지식(경영통합 연도 등)에 기댄다"),
        ("  공시 확인", "공시·감사보고서로 확인한 거래 형태, 편입 시점, 상태, 금액, 발표일과 메모"),
        ("  인수 목적·핵심 / 규모 / 주가 이벤트", "발표 당시 목적, 핵심 여부, 인수 주체·그룹 정점의 규모와 비율, 종목과 처음 알려진 날"),
        ("  전후 이벤트 / 성과", "인수 전후 사건, 손상, 대상회사 인수 전후 매출·영업이익, 어닝콜 언급"),
        ("  수집", "수집 상태(완료 = 모든 항목을 채움, 부분 = 공개 자료가 없어 비어 있는 항목이 있음)와 수집 일시"),
        ("값 표기", "미확인 = 찾았지만 근거가 없음 · 해당 없음 = 그 거래에 해당하지 않음 · 추정: = 추정한 값"),
        ("색", "거래 형태 (공시 확인)·형태 변경 칸 청록 = 설명란 판정과 거래 형태가 다름 · 손상 구분 빨강 = 있음, 초록 = 없음 (확인), 주황 = 식별 불가·미확인 · 금액 대조 빨강 = 불일치 · 수집 상태 초록 = 완료"),
        ("손상 구분", "있음 = 인수 뒤 손상 확인 · 없음 (확인) = 인수 뒤 영업권·투자주식이 손상 없이 유지됨을 확인 · 식별 불가 = 영업권이 부문 단위로 묶여 이 거래 몫을 알 수 없음 · 미확인 = 확인 기간이 짧거나 비어 판단 자료 부족 · 해당 없음 = 그룹 밖 매수자, 그룹의 매각, 동일지배 합병, 공정가치 금융자산 등 구조상 손상을 따지지 않는 거래"),
        ("금액 단위", "원자료 금액은 거래 당시 환율로 환산한 백만 달러. 공시로 확인한 금액은 '금액 확인' 열에 현지 통화와 환산값으로 적었다"),
        ("행 높이", "긴 글은 칸 안에서 줄바꿈되고 행 높이는 고정이다. 전체 내용은 셀을 선택해 수식 입력줄에서 보거나 행 높이를 늘려 본다"),
    ]
    for r, (a, b) in enumerate(lines, 1):
        ca = ws.cell(row=r, column=1, value=a)
        ca.font = Font(name=FONT, bold=(b is None or not a.startswith("  ")), size=14 if r == 1 else 10)
        if b:
            cb = ws.cell(row=r, column=2, value=b)
            cb.font = Font(name=FONT, size=10)
            cb.alignment = Alignment(wrap_text=True, vertical="top")
        ca.alignment = Alignment(vertical="top")


def main():
    # 엑셀이 받지 않는 제어 문자(원문 복사 중 섞인 것)를 지운다
    clean = lambda df: df.apply(lambda c: c.str.replace(ILLEGAL_CHARACTERS_RE, "", regex=True))
    d = clean(pd.read_csv(DIR / "MA188_수집시트.csv", dtype=str).fillna(""))
    e = clean(pd.read_csv(DIR / "MA188_근거.csv", dtype=str).fillna(""))
    d["_base"] = d.subtype.map(code)
    d["_chk"] = d.subtype_chk.map(code)
    d["_chg"] = (d._base != d._chk).map({True: "변경", False: "같음"})
    d["_val"] = d.value_chk_usdmm.map(val_class)
    d["_pre"] = d.pre_incorp_chk.map(lambda s: s.split(" (")[0].split(":")[0].strip())
    wb = Workbook()
    guide_sheet(wb, len(d), len(e))
    _, col, last = deals_sheet(wb, d)
    evidence_sheet(wb, e, dict(zip(d.ciq_id, d.target)))
    summary_sheet(wb, col, last)
    wb.calculation.fullCalcOnLoad = True  # 엑셀이 열 때 '요약' 수식을 계산하게 한다
    wb.save(OUT)
    print(f"{OUT} 저장: 거래 {len(d)}행, 근거 {len(e)}행")


if __name__ == "__main__":
    main()
