# Quick Start Guide

**Independent SLURM Jobs for Each Method**

## 1. Edit `submit_method.sh`

Line ~31, set your workspace path:

```bash
PROJECT_ROOT="/path/to/your/workspace"  # ← CHANGE THIS
```

## 2. Create log directory

```bash
mkdir -p slurm_sweep_full_dataset/slurm_logs
```

## 3. Submit ALL jobs at once

```bash
cd slurm_sweep_full_dataset
bash submit_all.sh
```

This submits **7 independent SLURM jobs** (baseline + 6 warm weights):
- Each job runs **5 seeds in parallel** (--array=0-4)
- Total: **35 runs** all executing in parallel
- Estimated time: **2 hours for all runs** (since jobs run simultaneously)

## 4. Monitor

```bash
squeue -u $USER
tail -f slurm_sweep_full_dataset/slurm_logs/sweep_*.log
```

## 5. Aggregate results when done

```bash
cd slurm_sweep_full_dataset
python aggregate_results.py --results-dir ./results_YYYYMMDD_HHMMSS
```

## Or: Test Locally First

```bash
python slurm_sweep_full_dataset/main_sweep.py \
    --method baseline \
    --time-limit 600 \
    --seed 0 \
    --output-dir test_results
```

---

**For full documentation, see `README.md`**
