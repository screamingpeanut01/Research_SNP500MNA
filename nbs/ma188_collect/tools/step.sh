#!/usr/bin/env bash
# main의 알림 한 번 처리: 유닛 닫기 → 검토 끝난 거래 병합·커밋·푸시 → 다음 유닛 출력
# 사용: bash step.sh "<닫을 유닛들>" <새로 열 유닛 수> [review|collect]
SP="C:/Users/1029l/AppData/Local/Temp/claude/D--KUfolio-Researches-Research-SNP500MNA/ccb194d9-de7b-4623-9724-9f6d514f1a86/scratchpad"
REPO="D:/KUfolio/Researches/Research_SNP500MNA"
[ -n "$1" ] && python -X utf8 -I "$SP/tools/units.py" close $1
# 수집 기록과 검토 기록이 모두 있는 거래만 병합 폴더로 복사
for r in "$SP"/records/review_*.json; do
  [ -e "$r" ] || continue
  id=$(basename "$r" .json); id=${id#review_}
  [ -e "$SP/records/$id.json" ] && cp -u "$SP/records/$id.json" "$r" "$SP/merged/"
done
cd "$REPO" && python -X utf8 nbs/ma188_build_sheet.py --out meeting/20261102 --merge "$SP/merged" | tail -1
if ! git diff --quiet -- meeting/20261102; then
  n=$(ls "$SP"/merged/review_*.json | wc -l)
  git add meeting/20261102/MA188_수집시트.csv meeting/20261102/MA188_근거.csv
  git commit -q -m "Merge reviewed M&A collection records ($n of 188 deals)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" && git push -q origin main 2>&1 | tail -1
  echo "커밋 $(git log --oneline -1 | cut -c1-7) (병합 $n건)"
fi
python -X utf8 -I "$SP/tools/units.py" status
[ "${2:-0}" -gt 0 ] && python -X utf8 -I "$SP/tools/units.py" next "$2" $3
exit 0
