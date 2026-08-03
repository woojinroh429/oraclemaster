"""Tally night_winw.log by arm, split by whether the instance can make the trade at all.

The split matters: an instance whose w3*regret/w1 is under 1 offers no late window, so its two
arms run the same code and any difference is a reading of the noise.  Mixing those into one
count is how a -7.67% "win" was reported on prob_34, where the mechanism provably cannot fire.
"""
import re, json, os, sys, collections, statistics as st
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = collections.defaultdict(dict)
for ln in open(os.path.join(H, 'results/audit/night_winw.log')):
    m = re.match(r'P(\d+)\s+\[(\w+)\.\d+\]\s+\S+\s+obj=(\d+)\s+Z1=([\d.]+)\s+Z2=(\d+)\s+Z3=([\d.]+)', ln)
    if m:
        d[int(m.group(1))][m.group(2)] = (int(m.group(3)), float(m.group(4)), float(m.group(6)))
live = {}
for p in d:
    j = json.load(open(os.path.join(H, 'data/stage2/prob_%d.json' % p)))
    w = j['weights']
    reg = max(max(b['bay_preferences']) - min(b['bay_preferences']) for b in j['blocks'])
    live[p] = int(w['w3'] * reg / w['w1']) >= 1
print("%-6s %-4s %13s %9s %9s %8s %8s" % ("inst", "거래", "base", "old", "new", "dZ1", "dZ3"))
G = {True: {'old': [], 'new': []}, False: {'old': [], 'new': []}}
for p in sorted(d):
    r = d[p]
    if 'base' not in r:
        continue
    ob, z1b, z3b = r['base']
    row = "P%-5d %-4s %13d" % (p, "가능" if live[p] else "불가", ob)
    for a in ('old', 'new'):
        if a in r:
            v = r[a][0]; pc = 100.0 * (v - ob) / ob
            G[live[p]][a].append(pc); row += " %+8.2f%%" % pc
        else:
            row += " %9s" % "-"
    if 'new' in r:
        row += " %+8.0f %+8.0f" % (r['new'][1] - z1b, r['new'][2] - z3b)
    print(row)
for k, name in ((True, "거래 가능"), (False, "거래 불가")):
    print("\n== %s ==" % name)
    for a in ('old', 'new'):
        v = G[k][a]
        if v:
            b = sum(1 for x in v if x < -1e-9); s = sum(1 for x in v if x > 1e-9)
            print("  %-4s  좋음 %2d / 나쁨 %2d / 동일 %2d   평균 %+.2f%%  중앙값 %+.2f%%"
                  % (a, b, s, len(v) - b - s, st.mean(v), st.median(v)))
