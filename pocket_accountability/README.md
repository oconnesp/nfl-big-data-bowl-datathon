# Pocket Accountability Map — pipeline (Workstream 1)

Square Yards Surrendered (SYS): every 0.1 s, the QB's pocket (5-yd disk) is split
between the QB and the rushers; space a rusher takes beyond what he held at the snap
is charged to the blocker(s) PFF lists as blocking him.

## Run

```
pip install -r pocket_accountability/requirements.txt
python pocket_accountability/compute.py --games 2   # quick check
python pocket_accountability/compute.py             # all 122 games (~1 min)
```

Outputs go to `pocket_accountability/out/`.
