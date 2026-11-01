# '공개 자료 없음' 2차 확인 지침 (확인 에이전트용, 2026-11-01)

경로 약칭: `SP` = `C:/Users/1029l/AppData/Local/Temp/claude/D--KUfolio-Researches-Research-SNP500MNA/ccb194d9-de7b-4623-9724-9f6d514f1a86/scratchpad`, `REPO` = `D:/KUfolio/Researches/Research_SNP500MNA`

## 0. 배경

1차 재수집에서 일부 칸을 '공개 자료 없음'으로 분류했다. 그런데 그중에는 출처를 다 열어 보지 않고 "비상장이라 공개 의무가 없다"처럼 제도나 추론으로 판단한 칸이 섞여 있다. 연구자의 기준은 이렇다. **모든 원자료를 실제로 찾아보고 없어야 진짜 없는 것이다.** 이번 일은 그 기준으로 각 칸을 다시 확인하는 것이다.

## 1. 먼저 읽을 것

- `REPO/nbs/ma188_collect/brief_collect.md`의 §0(토큰 절약), §3(항목 정의), §4(근거), §5(신뢰성), §6(도구)
- `REPO/nbs/ma188_recollect/brief_recollect.md`의 §2-1. 특히 **'공개 자료 없음'의 기준과 항목별 출처 목록**
- 맡은 입력 `SP/recollect/verify_inputs/verify_part<N>.json`. 거래마다 `context`(거래 정보와 수집·검토 메모)와 `targets`(다시 볼 칸)가 있다. `targets`의 각 칸에는 지금 값(`value_now`)과 1차 재수집의 이유(`reason_now`)가 있다.
- 1차 재수집의 전체 결과 `SP/recollect/results/<deal_id>.json`과, 그때 받은 문서(`SP/cache/`, `SP/work*/`, `SP/recollect/work*/`)를 먼저 확인한다. 이미 연 출처는 다시 받지 말고 저장된 파일을 grep한다.

## 2. 할 일

`targets`의 칸마다:

1. 그 칸의 항목에 맞는 출처 목록(brief_recollect.md §2-1)을 하나씩 실제로 확인한다. 1차 재수집이나 원래 수집이 이미 확인한 출처는, 메모에 접수번호·문서명이 적혀 있으면 확인한 것으로 쳐도 된다. 적혀 있지 않으면 직접 확인한다.
2. 결과를 셋 중 하나로 적는다.
   - 값을 찾았다 → `class: 미완`, `retry: 채움` 또는 `일부 채움`, `after`에 새 전체 값. 근거 행을 남긴다.
   - 목록의 출처를 모두 열었는데 값이 없다 → `class: 공개 자료 없음`, `retry: 못 찾음`.
   - 목록의 출처 가운데 열지 못한 것이 있다(접속 차단, 유료, 예산 소진) → `class: 미완`, `retry: 못 찾음`. 어느 출처를 열지 못했는지 적는다.
3. `reason`에는 확인한 출처를 **모두** 적는다. 출처마다 접수번호·문서명·URL·검색어와 결과를 쓴다. 예: `DART 대상회사 목록(dart.py search 01234567 20150101 20251231) 0건; 카카오 2016 사업보고서(20170331004123) 연결주석 종속기업 요약재무에 없음; 공정위 기업집단현황공시 2016-05(20160531000111) 회사 손익현황 표에 없음; 네이버 뉴스 '회사명 매출' 검색 결과 없음`.

- **도구 호출 예산**: 칸 하나에 6회 안팎, 거래 하나에 20회 이내. 같은 출처가 여러 칸에 해당하면(예: 같은 감사보고서에 매출과 영업이익이 함께 있음) 한 번 열어 함께 확인한다.
- 값의 형식은 원래 수집 지침 §3을 따르고, 이미 아는 부분은 지우지 않는다.
- `targets`에 없는 칸은 바꾸지 않는다. 다른 문제를 발견하면 `other_issues`에 적는다.
- `impairment_class`는 이번 대상에 없다.

## 3. 출력

거래마다 `SP/recollect/verify_results/<deal_id>.json`을 한 번에 쓴다.

```json
{
  "deal_id": "K012",
  "ciq_id": "IQTR...",
  "checks": [
    {"field": "target_op_pre", "class": "공개 자료 없음", "retry": "못 찾음",
     "reason": "확인한 출처를 모두, 결과와 함께", "after": "재확인 뒤의 전체 값"}
  ],
  "corrections": {"target_op_pre": "값이 바뀐 칸만"},
  "evidence_add": [ {"field": "...", "phase": "...", "event_date": "...", "event_type": "...", "content": "...",
                     "url": "...", "doc_type": "...", "doc_date": "...", "doc_id": "..."} ],
  "other_issues": "",
  "summary": "한두 문장"
}
```

- `checks`에는 `targets`의 칸을 모두, 빠짐없이 넣는다.
- `class`는 `공개 자료 없음` 또는 `미완`, `retry`는 `채움`, `일부 채움`, `못 찾음` 가운데 하나만 쓴다. 설명은 `reason`에 쓴다.
- JSON이 파싱되는지 확인한다.

## 4. 마지막 응답

거래마다 한 줄: `deal_id`, 공개 자료 없음 확정 칸 수 / 미완으로 바뀐 칸 수 / 새로 채운 칸 수, 특이사항.
