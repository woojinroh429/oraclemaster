"""AST undefined-name finder: catches use_cpp-style bugs (a Name used in a function
that is not a param / local assignment / module global / builtin / enclosing local)."""
import ast, sys, builtins

path=sys.argv[1]
tree=ast.parse(open(path).read(), path)
BUILT=set(dir(builtins))|{"__file__","__name__","__doc__","__builtins__"}

# module-level names (globals): top-level assignments, def/class, imports
GLOBALS=set()
def collect_bindings(node, names):
    for n in ast.walk(node):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
            pass
for stmt in tree.body:
    if isinstance(stmt,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
        GLOBALS.add(stmt.name)
    elif isinstance(stmt,(ast.Import,ast.ImportFrom)):
        for a in stmt.names: GLOBALS.add((a.asname or a.name).split(".")[0])
    elif isinstance(stmt,ast.Assign):
        for t in stmt.targets:
            for nn in ast.walk(t):
                if isinstance(nn,ast.Name): GLOBALS.add(nn.id)
    elif isinstance(stmt,(ast.AnnAssign,ast.AugAssign)):
        if isinstance(stmt.target,ast.Name): GLOBALS.add(stmt.target.id)
    elif isinstance(stmt,(ast.For,ast.With,ast.If,ast.Try,ast.While)):
        for nn in ast.walk(stmt):
            if isinstance(nn,ast.Name) and isinstance(nn.ctx,ast.Store): GLOBALS.add(nn.id)

def func_locals(fn):
    """names bound inside a function: params + assignments + comprehension + as + nested defs + global/nonlocal."""
    loc=set()
    a=fn.args
    for arg in list(a.posonlyargs)+list(a.args)+list(a.kwonlyargs): loc.add(arg.arg)
    if a.vararg: loc.add(a.vararg.arg)
    if a.kwarg: loc.add(a.kwarg.arg)
    for node in ast.walk(fn):
        if node is fn: continue
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
            loc.add(node.name)
        elif isinstance(node,ast.Name) and isinstance(node.ctx,ast.Store):
            loc.add(node.id)
        elif isinstance(node,(ast.Global,ast.Nonlocal)):
            for nm in node.names: loc.add(nm)
        elif isinstance(node,ast.arg):
            loc.add(node.arg)
        elif isinstance(node,(ast.Import,ast.ImportFrom)):
            for al in node.names: loc.add((al.asname or al.name).split(".")[0])
        elif isinstance(node,ast.ExceptHandler) and node.name:
            loc.add(node.name)
    return loc

# walk functions with scope stack
issues=[]
def visit(fn, enclosing):
    loc=func_locals(fn)
    avail=enclosing|loc|GLOBALS|BUILT
    # check Name loads directly in this function body (not in nested funcs -- those recurse)
    nested=[n for n in ast.walk(fn) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n is not fn]
    nested_nodes=set()
    for nf in nested:
        for x in ast.walk(nf): nested_nodes.add(id(x))
    for node in ast.walk(fn):
        if node is fn: continue
        if id(node) in nested_nodes: continue
        if isinstance(node,ast.Name) and isinstance(node.ctx,ast.Load):
            if node.id not in avail:
                issues.append((fn.name, node.lineno, node.id))
    for nf in nested:
        # only direct children (avoid double recursion)
        pass
    # recurse into nested funcs with this scope as enclosing
    for nf in [n for n in fn.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]:
        _recurse(nf, avail)

def _recurse(fn, enclosing):
    loc=func_locals(fn)
    avail=enclosing|loc|GLOBALS|BUILT
    direct_nested=[n for n in fn.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
    nested_ids=set()
    for nf in direct_nested:
        for x in ast.walk(nf): nested_ids.add(id(x))
    for node in ast.walk(fn):
        if node is fn or id(node) in nested_ids: continue
        if isinstance(node,ast.Name) and isinstance(node.ctx,ast.Load) and node.id not in avail:
            issues.append((fn.name, node.lineno, node.id))
    for nf in direct_nested: _recurse(nf, avail)

for stmt in tree.body:
    if isinstance(stmt,(ast.FunctionDef,ast.AsyncFunctionDef)):
        _recurse(stmt, set())

seen=set(); out=[]
for fn,ln,name in issues:
    if name in BUILT: continue
    k=(fn,name)
    out.append((ln,fn,name))
out.sort()
for ln,fn,name in out:
    print(f"  L{ln} in {fn}(): undefined '{name}'")
print(f"TOTAL {len(out)} undefined-name references")
