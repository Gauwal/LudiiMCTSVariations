# SLURM Sweep Experiments - Full Dataset - Independent Methods

Complete setup for running warm-start RCP experiments on a SLURM cluster using the full Ludii dataset (no subsampling).

## Overview

This folder contains everything needed to run **independent parallel jobs** for each method:
- Baseline (cold start)
- Warm-start with weights: w = 5, 20, 50, 100, 200, 500

Each method runs with **5 seeds in parallel** using SLURM array jobs.

**Key Features:**
- Uses **full dataset** (no subsampling)
- Tests **6 warm-start weights**: 5, 20, 50, 100, 200, 500
- Each method runs **independently** (can parallelize across different SLURM jobs)
- Each job uses **array=0-4** for 5 seeds in parallel
- Includes **predictor-only baseline** (single line on plots)
- Generates **regret and APE curves** with publication-quality plots
- Results saved as **JSON** for aggregation

## Files

- **`main_sweep.py`** — Main experiment script (runs ONE method: baseline or warm:<weight>)
- **`submit_method.sh`** — SLURM job template (called for each method)
- **`submit_all.sh`** — **Master script: submit all 7 methods at once**
- **`aggregate_results.py`** — Combine results from all methods and seeds
- **`README.md`** — This file

## Setup (First Time Only)

### 1. Copy This Folder to Your SLURM Cluster

```bash
scp -r slurm_sweep_full_dataset/ <user>@<cluster>:/path/to/workspace/
cd /path/to/workspace
```

### 2. Edit `submit_method.sh`

Set `PROJECT_ROOT` to your workspace path (line ~31):

```bash
PROJECT_ROOT="/your/actual/workspace/path"
```

### 3. Create Log Directory

```bash
mkdir -p slurm_sweep_full_dataset/slurm_logs
```

### 4. Verify Dependencies

```bash
source .venv/bin/activate
pip install -r slurm_sweep_full_dataset/requirements.txt
```

## Quick Start

### Option A: Submit All Jobs at Once (Recommended)

```bash
cd slurm_sweep_full_dataset
bash submit_all.sh
```

This submits 7 independent jobs (1 baseline + 6 warm weights), each with 5 seeds (--array=0-4):

```
Submitting baseline...
  Submitted job ID: 12345001
Submitting warm:5...
  Submitted job ID: 12345002
Submitting warm:20...
  Submitted job ID: 12345003
...
```

**Total:** 7 jobs × 5 seeds = 35 runs, all executed in parallel!

### Option B: Dry Run (Check Without Submitting)

```bash
bash submit_all.sh --dry-run
```

Shows all commands that would be submitted without actually submitting.

### Option C: Submit Single Method

```bash
sbatch --array=0-4 submit_method.sh baseline
sbatch --array=0-4 submit_method.sh warm:50
```

## Monitoring Jobs

### Check Job Status

```bash
# View all your running jobs
squeue -u $USER

# View specific job
squeue -j 12345001
```

### View Live Logs

```bash
# Watch log file (live)
tail -f slurm_sweep_full_dataset/slurm_logs/sweep_12345001.log

# View all logs at once
ls -la slurm_sweep_full_dataset/slurm_logs/
```

### Check Errors

```bash
cat slurm_sweep_full_dataset/slurm_logs/sweep_12345001.err
```

## Output Files

Results are saved to timestamped directories:

```
slurm_sweep_full_dataset/
├── results_20260424_130000/
│   ├── sweep_baseline_0_20260424_130030.json
│   ├── sweep_baseline_0_20260424_130030_regret.png
│   ├── sweep_baseline_0_20260424_130030_ape.png
│   ├── sweep_baseline_1_20260424_130150.json
│   ├── sweep_baseline_1_20260424_130150_regret.png
│   ├── ...
│   ├── sweep_warm_5_0_20260424_131000.json
│   ├── sweep_warm_5_0_20260424_131000_regret.png
│   ├── ...
```

**File naming:** `sweep_<method>_<seed>_<timestamp>_<metric>.{json,png}`

### JSON Structure (Single Method)

```json
{
  "meta": {
    "method": "warm:50",
    "time_limit": 7200,
    "seed": 0,
    "batch_size": 20,
    "num_games": 1085,
    "secs_per_pull": 0.05,
    "per_method_n": 1070,
    "wall_time": 120.3
  },
  "predictor": {
    "regret": 0.1114,
    "ape": 0.4959
  },
  "warm": {
    "50": {
      "regret": [0.135, 0.133, ..., 0.106],
      "ape": [0.679, 0.675, ..., 0.564]
    }
  }
}
```

## Post-Processing: Aggregate Results

After all jobs complete, combine results from all methods and seeds:

```bash
cd slurm_sweep_full_dataset
python aggregate_results.py --results-dir ./results_20260424_130000
```

This generates:
- `aggregated_regret.png` — All methods with error bands (mean ± std)
- `aggregated_ape.png` — All methods with error bands
- `aggregated_summary.json` — Summary statistics

### Plotting Manually

```python
import json
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Load all results
results_dir = Path('results_20260424_130000')
results = {}
for json_file in results_dir.glob('sweep_*.json'):
    with open(json_file) as f:
        data = json.load(f)
        method = data['meta']['method']
        if method not in results:
            results[method] = []
        results[method].append(data)

# Plot baseline mean across seeds
baseline_regrets = [r['baseline']['regret'] for r in results['baseline']]
mean_regret = np.mean(baseline_regrets, axis=0)

plt.plot(mean_regret, label='Baseline (mean)')
plt.legend()
plt.show()
```

## Timing Estimates

Expected wall-clock time per method:

| Method | Per-Run Time | Total (5 seeds) |
|--------|-------------|-----------------|
| Baseline | ~2 minutes | ~10 minutes |
| Warm w=5 | ~2 minutes | ~10 minutes |
| Warm w=50 | ~2 minutes | ~10 minutes |
| All 7 methods | — | **~70 minutes total** |

**With SLURM parallelization:** All 7 jobs run simultaneously, so wall-clock time ≈ **10 minutes per seed** ≈ **2 hours for all 35 runs**.

### Adjusting Time Limits

Edit `submit_method.sh` to change the Python time limit:

```bash
python slurm_sweep_full_dataset/main_sweep.py \
    --method "${METHOD}" \
    --time-limit 7200 \  # ← Change this (seconds)
    ...
```

And adjust SLURM wall-clock time:

```bash
#SBATCH --time=02:00:00  # ← Change this
```

## Workflow Example

### Step 1: Submit All Jobs

```bash
bash submit_all.sh
```

Expected output:
```
Submitting baseline...
  Submitted job ID: 12345001
Submitting warm:5...
  Submitted job ID: 12345002
...all 7 jobs submitted
```

### Step 2: Monitor

```bash
watch -n 10 "squeue -u \$USER"  # Refresh every 10s
tail -f slurm_sweep_full_dataset/slurm_logs/sweep_12345001.log
```

### Step 3: Aggregate Results

Once all jobs finish:

```bash
python slurm_sweep_full_dataset/aggregate_results.py \
    --results-dir slurm_sweep_full_dataset/results_<timestamp>
```

### Step 4: Copy Results

```bash
scp -r <user>@<cluster>:/path/to/workspace/slurm_sweep_full_dataset/results_* ./
scp -r <user>@<cluster>:/path/to/workspace/slurm_sweep_full_dataset/aggregated_* ./
```

## Troubleshooting

### Jobs Not Submitting

Check that `PROJECT_ROOT` in `submit_method.sh` is correct:

```bash
grep "PROJECT_ROOT=" slurm_sweep_full_dataset/submit_method.sh
```

### Job Fails with ModuleNotFoundError

Ensure Python dependencies are installed:

```bash
pip install -r slurm_sweep_full_dataset/requirements.txt
```

### Job Timeout

Increase `--time=` in `submit_method.sh` or reduce `--time-limit` in the Python script.

### Out of Memory

Increase `#SBATCH --mem=` in `submit_method.sh` (default 16G).

## File Reference

### Core Scripts

| File | Purpose |
|------|---------|
| `main_sweep.py` | Runs ONE method (baseline or warm:<weight>) |
| `submit_all.sh` | Master: submit all 7 methods at once |
| `submit_method.sh` | Job template: called by submit_all.sh |
| `aggregate_results.py` | Combine results from all methods/seeds |

### Configuration

| File | Purpose |
|------|---------|
| `requirements.txt` | Python dependencies |
| `README.md` | This file |
| `QUICKSTART.md` | Quick reference |

## Advanced Usage

### Run Subset of Methods

Edit `submit_all.sh` and modify the `METHODS` array:

```bash
METHODS=("baseline" "warm:50" "warm:100")
```

Then run:

```bash
bash submit_all.sh
```

### Run with Custom Time Limit

Modify `submit_method.sh` before submitting:

```bash
# Change this line:
--time-limit 7200 \  # seconds

# To:
--time-limit 3600 \  # 1 hour instead of 2
```

### Retrieve Just One Job's Results

```bash
scp <user>@<cluster>:/path/workspace/slurm_sweep_full_dataset/results_*/sweep_warm_50_0_* ./
```

---

**Last Updated:** 2026-04-24  
**Status:** Production Ready  
**Contact:** See parent workspace README for support
