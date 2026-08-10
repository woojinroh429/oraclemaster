# Bmul > 1.0 IS DEAD CODE, AND ONE OF THE SIX AXES DEPENDS ON IT

    def _beam_width(mul):
        _BCAP = max(8, int(os.environ.get("OGC_BCAP", "96")))
        return max(8, min(_BCAP, int(mul * _BCAP)))

The ceiling and the base are the SAME constant.  So `int(mul * _BCAP)` exceeds `_BCAP` for every
mul > 1 and is clipped back to it.  Bmul is therefore "a fraction of 96, never more than 96", and
only values at or below 1.0 do anything at all.

Read straight off the deterministic table, where beam1 prints the width it actually used:

    axis   Bmul   B used   K
    0      1.0      96     4
    1      1.0      96     4
    2      0.7      67     5
    3      0.7      67     5
    4      1.4      96     3     <- asks for 134, gets 96
    5      0.5      48     6

Axes 0, 1 and 4 run at identical width.  Whatever axis 4 was meant to contribute as "the wide
one", it has never contributed, and the three of them differ only in K (4 / 4 / 3) and the
non-width fields.

## WHY THIS MATTERS BEYOND TIDINESS

The portfolio's whole justification is that six configurations reach six different valleys, and
the file measures that at 32-210% between configs.  Two defects now reduce what is actually in
play:

    axes 5 and 0 never OPEN a run   -- `gen[0] += 1` before indexing, so the opener is
                                       _AXES[(wid+1) % 6] and nw is 4
    Bmul > 1 is inert               -- axis 4's width is axis 0's width

## WHAT I AM NOT DOING ABOUT IT

Not fixing it.  Raising _BCAP so 1.4 means 134 changes the shipped behaviour of three axes at
once, and the file already records that width is not a monotone good: at equal work, 16 of 18
cells were identical to the last digit across B = 48/67/96, and of the two that moved one was
+0.98% and the other -2.40%.  So "axis 4 finally gets its width" could go either way, and it is
testable in isolation with OGC_BCAP=134 rather than by guessing.

Recorded as a defect with a test attached, not as a patch.
