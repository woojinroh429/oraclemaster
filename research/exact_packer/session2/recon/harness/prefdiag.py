"""Where is the objective spent, and how much Z3 is reachable at ZERO tardiness cost?
For each instance: the Z1/Z2/Z3 split of a pipeline answer, plus
  misplaced      : blocks NOT in their top-preference bay
  free-slack     : of those, the ones whose exit is still before their due date, i.e.
                   delaying them costs no tardiness at all
  z3reachable    : the preference points those free-slack blocks are giving up -- an
                   UPPER bound on what a delay-for-preference move could recover."""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
REC = os.path.dirname(HERE)
sys.path.insert(0, REC); os.chdir(REC)
import myalg_legacy as M, utils
M._CPP_ENGINE_MODE = M.HAVE_OGC_FAST

def load(p):
    for c in ('data/train/prob_%d.json' % p, 'data/set1/prob_%d.json' % p):
        if os.path.exists(c):
            return json.load(open(c))
    raise SystemExit("prob_%d.json not found -- is data/ linked?" % p)

for p in (int(x) for x in sys.argv[1].split(',')):
    d = load(p)
    B = d['blocks']; n = len(B); w = d['weights']
    sol = M.algorithm(d, timelimit=float(sys.argv[2]))
    c = utils.check_feasibility(d, sol)
    if not c.get('feasible'):
        print('p%-3d INFEASIBLE' % p, flush=True); continue
    o = float(c['objective'])
    z1 = w['w1']*float(c['obj1']); z2 = w['w2']*float(c['obj2']); z3 = w['w3']*float(c['obj3'])
    ent={}; ext={}; bay={}
    for t, ops in sol['operations'].items():
        for op in ops:
            if op['type']=='ENTRY': ent[op['block_id']]=int(t); bay[op['block_id']]=op['bay_id']
            else: ext[op['block_id']]=int(t)
    nfree=0; z3free=0.0; npref=0; nmis=0
    for b in range(n):
        pv=B[b]['bay_preferences']; gap=max(pv)-pv[bay[b]]
        if gap<=0: npref+=1; continue
        nmis+=1
        if B[b]['due_date']-ext[b] > 0:
            nfree+=1; z3free+=gap
    print('p%-3d n=%-4d dr=%.3f obj=%-11d | Z1%6.1f%% Z2%6.1f%% Z3%6.1f%% | inpref%4d misplaced%4d '
          'free-slack%4d  z3free=%.0f pts = %.1f%% of obj'
          % (p, n, M._demand_ratio_phys(d), int(o), 100*z1/o, 100*z2/o, 100*z3/o,
             npref, nmis, nfree, z3free, 100.0*w['w3']*z3free/o), flush=True)
