# The six real hidden instances

These are the preliminary-round instances, committed because the working copy lives under
`data/`, which is a symlink into the container's scratch space and does not survive a restart.
Losing them once already cost a night's validation, since every paired A/B in this directory
runs against them at their real time limits.

Restore with:

    mkdir -p data/hidden && cp _hidden_backup/prob_*.json data/hidden/

    P1  60s   n=100  3 bays   w1=21622  w2=10  w3=150
    P2 120s   n=150  2 bays   w1= 8000  w2= 4  w3=200
    P3 240s   n=200  3 bays   w1=17778  w2= 5  w3=150
    P4 480s   n=150  3 bays   w1=13333  w2= 7  w3=150
    P5 600s   n=200  4 bays   w1=13333  w2= 7  w3=133
    P6 900s   n=250  3 bays   w1= 6667  w2= 8  w3=150
