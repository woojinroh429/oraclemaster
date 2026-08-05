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
FTBL=/tmp/finaltable.tex

# TWO ROUNDS, TWO TABLES.  The preliminary and final training sets are different instances and
# the report shows both, so both are generated from their own logs and injected at their own
# markers.  Neither is retyped.
python3.12 harness/mktable.py results/train t train 3 > "$TBL" 2>/dev/null
python3.12 harness/mksummary.py > "$FTBL" 2>/dev/null
for f in "$TBL" "$FTBL"; do
  grep -q 'end{tabular}' "$f" || { echo "no table in $f -- is that sweep finished?"; exit 1; }
  sed -n '/\\begin{tabular}/,/\\end{tabular}/p' "$f" > "$f.clean"
done

python3.12 - "$R/techreport.tex" "$TBL.clean" "$FTBL.clean" "$R/techreport_built.tex" <<'PY'
import sys
doc, tbl, ftbl, out = sys.argv[1:5]
s = open(doc).read()
for marker, path in (('%%TRAINTABLE%%', tbl), ('%%FINALTABLE%%', ftbl)):
    assert marker in s, marker + ' missing from techreport.tex'
    t = open(path).read().rstrip()
    s = s.replace(marker, t)
    print('injected %d rows at %s' % (t.count(chr(92)*2), marker))
open(out, 'w').write(s)
PY

cd "$R" || exit 1
# DELETE THE OLD PDF FIRST.  "did a PDF come out" is not the same question as "did THIS compile
# produce one", and the difference is not academic: a missing tcolorbox.sty aborted the run with
# a fatal error, the August 3rd PDF was still sitting there, and this script reported 8 pages and
# a passing anonymity check -- all of it measured on the previous build.  A failed compile must
# leave nothing behind to be mistaken for a result.
rm -f techreport_built.pdf
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
