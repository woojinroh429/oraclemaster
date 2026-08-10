# THE RASTER MASKS ARE EXACTLY CORRECT AND EXACTLY USELESS, AND THE REASON MATTERS

Implemented, verified, measured, and reverted.  Written down so it is not attempted again.

## What was built

Two rasterisations per layer polygon on a unit grid over its own bounding box -- OUTER, every cell
the polygon touches, and INNER, every cell wholly inside -- and a layer-pair test that reads

    outer_A AND outer_B  empty      ->  cannot overlap     (exact rejection)
    inner_A AND inner_B  non-empty  ->  do overlap         (exact acceptance)
    otherwise                       ->  the polygon test

Neither shortcut can be wrong, so the graph is identical by construction rather than by hope.  The
attraction was that mask resolution is independent of the PLACEMENT grid: halving STEP quadruples
the columns and leaves every mask untouched, which is what would have made a finer search
affordable -- the file's own note says NOUT 40 and STEP 4 are held where they are by what the
build can afford and that "raising it safely requires a FASTER BUILD, not a bigger table".

## What it measured

    ncol      3,878      13,494      17,163
    raster 1  562,879    7,407,056   16,022,864   edges     build 2326 ms
    raster 0  562,879    7,407,056   16,022,864   edges     build 2252 ms

Edge sets identical at all three sizes.  Build 3% SLOWER with the masks.

## Why, and the arithmetic error that led here

bayrepack hands cranepack `_layers_bbox`, so every layer is a RECTANGLE.  poly_overlap_off on two
rectangles is four point-in-polygon tests and sixteen segment crossings -- already about a hundred
nanoseconds.  There was no expensive geometry to replace, and the masks cost more than what they
were replacing.

The estimate that sent me here: the memo note reports 23,208,767 hits against 1,090,614 misses, I
priced a miss at ~2 us, and concluded 4.5% of the visits were 90% of the build.  The real
measurement says 17,163 columns produce 16,022,864 edges in 2.3 s, i.e. **95 ns per pair visit** --
the loop is enumeration and memo probes end to end, and the polygon path was never the bottleneck.

Two analyses were made of the same loop tonight.  The first said enumeration dominates, the second
said geometry does; the second was arithmetic on an assumed constant and it was the wrong one.

## What it costs the factorisation idea

10.9% of pairs are genuine conflicts, and those 16M edges have to be emitted whatever the geometry
costs.  Skipping non-conflicting geometry pairs in O(1) therefore cannot approach the r^2 the
algebra allows -- the ceiling on this input is 2-3x, not 25x.  conflictfactor.md's derivation is
still correct; its expected payoff is not.

## Left in the tree

Nothing.  cranepack.cpp and its four binaries are reverted, so the package guard still reads 4/4
matching on both extensions.  A verified-negative change does not ship: this project has measured
a proved bit-identical edit move an objective 7.7% through code layout alone, so rebuilding four
.so files for zero gain is pure risk.  The masks would be worth revisiting only if bayrepack ever
sends real polygons instead of bounding boxes.
