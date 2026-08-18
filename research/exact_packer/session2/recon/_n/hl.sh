cd /home/user/oraclemaster/research/exact_packer/session2/recon
for p in 37 26 31; do
  python3.12 _n/hintloop.py $p 300 4 >> _n/hintloop.log 2>&1
done
echo DONE >> _n/hintloop.log
