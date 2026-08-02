#!/bin/bash
# Build the technical report end to end: generate the training table from the logs, inject it,
# compile, check the page limit, and package for Overleaf.
#
# Nothing here retypes a number.  mktable.py reads results/train/*.log -- the files the sweep
# harness wrote and committed -- and this script substitutes its output for the %%TRAINTABLE%%
# marker in a COPY, leaving techreport.tex with the marker intact so the build is repeatable
# after another sweep.
#
# The page limit is 10 and it is checked here rather than discovered at submission time.
set -u
cd "$(dirname "$0")/.." || exit 1
R=report
TBL=/tmp/traintable.tex

python3.12 harness/mktable.py > "$TBL" 2>/dev/null
grep -q 'end{tabular}' "$TBL" || { echo "no table generated -- is the sweep finished?"; exit 1; }
# strip the trailing summary comments; only the tabular goes into the document
sed -n '/\\begin{tabular}/,/\\end{tabular}/p' "$TBL" > "$TBL.clean"

python3.12 - "$R/techreport.tex" "$TBL.clean" "$R/techreport_built.tex" <<'PY'
import sys
doc, tbl, out = sys.argv[1], sys.argv[2], sys.argv[3]
s = open(doc).read()
t = open(tbl).read().rstrip()
assert '%%TRAINTABLE%%' in s, 'marker missing from techreport.tex'
open(out, 'w').write(s.replace('%%TRAINTABLE%%', t))
print('injected %d table rows' % t.count(r'\\'))
PY

cd "$R" || exit 1
for i in 1 2; do pdflatex -interaction=nonstopmode techreport_built.tex > /tmp/tex$i.log 2>&1; done
if [ ! -s techreport_built.pdf ]; then
    echo "COMPILE FAILED"; grep -m5 "^! " /tmp/tex2.log; exit 1
fi
PAGES=$(pdfinfo techreport_built.pdf | awk '/^Pages/{print $2}')
ERRS=$(grep -c "^! " /tmp/tex2.log || true)
echo "pages: $PAGES / 10 limit    latex errors: $ERRS"
[ "$PAGES" -gt 10 ] && echo "  OVER THE LIMIT -- trim before submitting"

# The anonymity check is real only if the text actually came out.  A grep against empty input
# passes for the wrong reason, which is exactly how this check failed the first time.
WORDS=$(pdftotext techreport_built.pdf - | wc -w)
echo "extracted $WORDS words from the PDF"
if [ "$WORDS" -lt 500 ]; then
    echo "  TEXT EXTRACTION FAILED -- the anonymity check below would be meaningless"
else
    HITS=$(pdftotext techreport_built.pdf - | grep -icE "teamname|kyonggi|github|oraclemaster|[a-z]+@[a-z]+\.[a-z]|Writing Guidelines" || true)
    echo "identifying strings found: $HITS  (0 expected; the AI tool name is allowed and not matched here)"
fi

cp techreport_built.pdf "[OGC2026_TechReport].pdf"
rm -f overleaf_techreport.zip
zip -q overleaf_techreport.zip techreport_built.tex llncs.cls
echo "wrote report/[OGC2026_TechReport].pdf and report/overleaf_techreport.zip"
