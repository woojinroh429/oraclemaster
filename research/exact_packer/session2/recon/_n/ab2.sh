cd /home/user/oraclemaster/research/exact_packer/session2/recon
for p in 35 26 31 39 33 37; do
  python3.12 harness/run.py ab prob_$p 300 OGC_PREFBKT_LO=9 >> _n/ab2.log 2>&1
done
echo DONE >> _n/ab2.log
