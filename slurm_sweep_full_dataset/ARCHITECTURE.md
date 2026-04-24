# Architecture Overview

## New Independent Jobs Workflow

Instead of running all methods sequentially in one job, we now run each method as an **independent SLURM job**.

### Before (Sequential - Old Approach)
```
Single SLURM Job (2+ hours):
  ├─ Timing Probe
  ├─ Baseline (all seeds sequential)
  ├─ Warm w=5 (all seeds sequential)
  ├─ Warm w=20
  ├─ Warm w=50
  ├─ Warm w=100
  ├─ Warm w=200
  └─ Warm w=500

Total Wall Time: ~2+ hours (everything sequential)
```

### After (Parallel - New Approach)
```
Master Script (submit_all.sh)
  │
  ├─ Job 1: Baseline (seeds 0-4 in parallel) ──────┐
  ├─ Job 2: Warm w=5 (seeds 0-4 in parallel) ──────┤
  ├─ Job 3: Warm w=20 (seeds 0-4 in parallel) ─────┤ All run
  ├─ Job 4: Warm w=50 (seeds 0-4 in parallel) ──────┤ in parallel
  ├─ Job 5: Warm w=100 (seeds 0-4 in parallel) ────┤ on SLURM
  ├─ Job 6: Warm w=200 (seeds 0-4 in parallel) ────┤
  └─ Job 7: Warm w=500 (seeds 0-4 in parallel) ────┘

Total Wall Time: ~10 minutes per seed = ~2 hours for all 35 runs
(Each job runs 5 seeds with --array=0-4)
```

## File Structure

```
slurm_sweep_full_dataset/
│
├── main_sweep.py              ← Single method runner
│                               (baseline or warm:<weight>)
│
├── submit_all.sh              ← MASTER: Submit all 7 jobs
│                               (bash submit_all.sh)
│
├── submit_method.sh           ← Job template
│                               (called by submit_all.sh)
│
├── aggregate_results.py       ← Combine results after jobs finish
│
├── README.md                  ← Full documentation
├── QUICKSTART.md              ← 5-minute setup guide
├── ARCHITECTURE.md            ← This file
│
├── slurm_logs/                ← Created after first run
│   ├── sweep_12345001.log
│   ├── sweep_12345002.log
│   └── ...
│
└── results_20260424_130000/   ← Created after runs finish
    ├── sweep_baseline_0_*.json
    ├── sweep_baseline_0_*_regret.png
    ├── sweep_baseline_1_*.json
    ├── ...
    ├── sweep_warm_5_0_*.json
    ├── sweep_warm_5_0_*_regret.png
    └── ...
```

## Execution Flow

### 1. Preparation (One-Time)

```bash
# Edit PROJECT_ROOT in submit_method.sh
# Create log directory
mkdir -p slurm_sweep_full_dataset/slurm_logs
```

### 2. Submit All Jobs

```bash
cd slurm_sweep_full_dataset
bash submit_all.sh
```

Output:
```
Submitting baseline...
  Submitted job ID: 12345001
Submitting warm:5...
  Submitted job ID: 12345002
Submitting warm:20...
  Submitted job ID: 12345003
...
```

### 3. Monitor Progress

```bash
# Check all jobs
squeue -u $USER

# Watch logs
tail -f slurm_sweep_full_dataset/slurm_logs/sweep_*.log
```

### 4. Aggregate After Completion

```bash
python slurm_sweep_full_dataset/aggregate_results.py \
    --results-dir slurm_sweep_full_dataset/results_YYYYMMDD_HHMMSS
```

## Why This Architecture?

| Aspect | Old (Sequential) | New (Independent) |
|--------|-----------------|-------------------|
| **Parallelization** | Limited to SLURM array (seeds only) | Full parallelization (methods + seeds) |
| **Wall Time** | ~2+ hours | ~10 min per seed (all 35 runs ≈ 2 hours total) |
| **Job Management** | 1 complex job | 7 simple jobs |
| **Scalability** | Hard to add new methods | Easy: just add to METHODS array in submit_all.sh |
| **Fault Tolerance** | 1 failure = restart all | 1 failure = restart that method only |
| **Debugging** | Mixed output from all methods | Clean separation per method |

## Example: Adding a New Warm Weight

To test w=1000, just edit `submit_all.sh`:

```bash
# Before:
METHODS=("baseline" "warm:5" "warm:20" "warm:50" "warm:100" "warm:200" "warm:500")

# After:
METHODS=("baseline" "warm:5" "warm:20" "warm:50" "warm:100" "warm:200" "warm:500" "warm:1000")

# Also update main_sweep.py:
DEFAULT_WEIGHTS = [5, 20, 50, 100, 200, 500, 1000]
```

Then:
```bash
bash submit_all.sh
```

Automatically submits 8 jobs (1 baseline + 7 warm weights).

## Timing Example

Assume each method takes ~10 minutes per seed:

**Old approach (sequential):**
```
Baseline: 10 min
Warm 5:   10 min
Warm 20:  10 min
Warm 50:  10 min
Warm 100: 10 min
Warm 200: 10 min
Warm 500: 10 min
─────────────────
Total:    70 minutes
```

**New approach (parallel):**
```
All 7 methods running simultaneously:
Max time = 10 minutes (longest single method)
× 5 seeds (--array=0-4)
= 10 minutes total per SLURM run
```

## Result Files

Each method/seed combination generates:

```
sweep_<method>_<seed>_<timestamp>.json       ← Results data
sweep_<method>_<seed>_<timestamp>_regret.png ← Regret plot
sweep_<method>_<seed>_<timestamp>_ape.png    ← Accuracy plot
```

Example:
```
sweep_baseline_0_20260424_130030.json
sweep_warm_5_0_20260424_131000.json
sweep_warm_50_2_20260424_132000.json
```

---

**See `README.md` for full documentation and troubleshooting.**