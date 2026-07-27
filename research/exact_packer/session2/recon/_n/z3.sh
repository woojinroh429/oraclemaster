cd /home/user/oraclemaster/research/exact_packer/session2/recon
for p in 37 26 31 39; do
  python3.12 _n/z3loop.py $p 300 6 15 >> _n/z3loop.log 2>&1
done
echo DONE >> _n/z3loop.log
