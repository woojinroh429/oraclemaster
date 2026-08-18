# CONFIG A IS THREE SETTINGS, NOT TWO, AND THE THIRD IS WORTH 2x

The 3+1 arm was built by lengthening OGC_AIMSET and OGC_MSET so wid 3 would become a third config-A
worker.  It did not.  Five runs, slots read straight off WSTAT:

    slot 0  (aim 0.90, m=1, direction)   median 482,866   min 422,629
    slot 1  (aim 0.10, m=2, no dir)      median 689,187   -- config B, as expected
    slot 2  (aim 0.90, m=1, direction)   median 489,878
    slot 3  (aim 0.90, m=1, NO dir)      median 993,027   min 967,114

Slot 3 has config A's aim and config A's m and lands 2.03x worse than config A -- worse than
config B, which is the arm that has never won anything.  The missing piece is at line 2940:

    _dsv = os.environ.get("OGC_DIRSET", "2")
    if (_dsv == "1" and (wid % 2) == 1) or (_dsv == "2" and (wid % 2) == 0):
        os.environ.setdefault("OGC_ORDER", "lst")
        os.environ.setdefault("OGC_W3MUL", "0.5")

So config A = aim 0.90 AND m=1 AND order=lst AND w3mul=0.5, with the last two arriving through a
default that keys on the same wid % 2.  Three knobs, one index, and only two of them are reachable
by lengthening a list.

## THE MEASUREMENT NOBODY ASKED FOR IS THE BIGGEST ONE OF THE NIGHT

    same aim, same m, direction present    median ~486,000
    same aim, same m, direction absent     median  993,027

A factor of 2.03 on draw quality, isolated by accident, from a knob that has been shipped as a
default since DIRSET=2 was adopted.  Nothing else measured tonight moves a draw by more than a few
percent.  It says the ordering rule and the Z3 weight are not a tuning detail on prob_1 -- they are
most of what makes a draw a winning ticket.

WHAT THIS DOES NOT SAY.  It is five runs on one instance, and DIRSET=2 already puts the direction
exactly where the winning draws are, so there is no gain sitting here -- the shipped default is
already correct.  What it changes is the PICTURE: the search's left tail is governed by order and
w3mul far more than by aim, m, worker count or round count, all of which were swept tonight for
single-digit effects.

## AND IT MAKES A B A A REACHABLE

DIRSET picks even or odd, so it cannot give the direction to 0, 2 and 3.  Setting it globally can:

    WORKERS=4  OGC_AIMSET=0.90,0.10,0.90,0.90  OGC_MSET=1,2,1,1  OGC_ORDER=lst  OGC_W3MUL=0.5

Every worker then carries the direction, aim and m make wid 0, 2, 3 config A, and wid 1 becomes a
config B that also has the direction -- which costs nothing, since B has not produced a draw under
450,000 in 388 tries.  Rerunning as a3d.*; the invalid a3.* runs stay in the log as the evidence
for the paragraph above.
