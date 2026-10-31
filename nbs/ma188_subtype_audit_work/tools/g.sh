#!/bin/bash
# usage: g.sh RCPNO [pattern] [ctx]
R=/d/KUfolio/Researches/Research_SNP500MNA
A=/d/KUfolio/Researches/MA188_sources
rcp=$1; pat=$2; ctx=${3:-120}
files=$(grep ",$rcp\$" $R/data/ma188_sources/manifest.csv | awk -F, -v R=$R -v A=$A '{ if($1=="repo") print R"/"$2; else print A"/"$2 }' | sort -u)
for f in $files; do
  [ -s "$f" ] || continue
  if [ -z "$pat" ]; then echo "== $f $(wc -c <"$f")"; else grep -o -E ".{0,$ctx}($pat).{0,$ctx}" "$f" | sed "s|^|[$(basename $f)] |" | head -8; fi
done
