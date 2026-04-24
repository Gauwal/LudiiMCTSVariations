# Setup Summary

## What Changed

Your SLURM setup is now fully **independent and parallelized**:

- ✅ **One master script** (`submit_all.sh`) submits **7 independent SLURM jobs**
- ✅ Each job runs **5 seeds in parallel** using `--array=0-4`  
- ✅ **Baseline + 6 warm weights** run simultaneously (not sequentially)
- ✅ **Full dataset** (50,000 samples) with **predictor comparison line** on plots
- ✅ Results saved as JSON for aggregation

## Files Overview

| File | Purpose |
|------|---------|
| **submit_all.sh** | 🌟 **Master script** — Submit all 7 jobs with one command |
| **submit_method.sh** | Job template (called by submit_all.sh for each method) |
| **main_sweep.py** | Runs ONE method (baseline or warm:<weight>) |
| **aggregate_results.py** | Combine results from all methods/seeds after jobs finish |
| **README.md** | Full documentation |
| **ARCHITECTURE.md** | Visual overview of the new design |
| **QUICKSTART.md** | 5-minute setup guide |
| **validate_setup.sh** | Verify everything is configured before submitting |

## Quick Setup (3 Steps)

### Step 1: Edit One Path

Open `slurm_sweep_full_dataset/submit_method.sh` and change line ~31:

```bash
PROJECT_ROOT="/your/actual/workspace/path"
```

### Step 2: Create Log Directory

```bash
mkdir -p slurm_sweep_full_dataset/slurm_logs
```

### Step 3: Submit All Jobs

```bash
cd slurm_sweep_full_dataset
bash submit_all.sh
```

**Done!** All 7 jobs submitted. Go to Step 4.

### Step 4: Monitor & Collect

```bash
# Watch progress
tail -f slurm_sweep_full_dataset/slurm_logs/sweep_*.log

# When done, aggregate results
python slurm_sweep_full_dataset/aggregate_results.py \
    --results-dir slurm_sweep_full_dataset/results_YYYYMMDD_HHMMSS
```

## What Gets Submitted

```bash
bash submit_all.sh
```

Submits 7 SLURM jobs automatically:

| Job | Command | Seeds | Duration |
|-----|---------|-------|----------|
| 1 | baseline | 0-4 (parallel) | ~10 min |
| 2 | warm:5 | 0-4 (parallel) | ~10 min |
| 3 | warm:20 | 0-4 (parallel) | ~10 min |
| 4 | warm:50 | 0-4 (parallel) | ~10 min |
| 5 | warm:100 | 0-4 (parallel) | ~10 min |
| 6 | warm:200 | 0-4 (parallel) | ~10 min |
| 7 | warm:500 | 0-4 (parallel) | ~10 min |

**All 7 run in parallel on SLURM** → **Total ~10 min per seed** → **~2 hours for all 35 runs**

## Before vs After

### Before (Old)
```
1 job (sequential):
  timing_probe
  + baseline (10 min)
  + warm:5 (10 min)
  + warm:20 (10 min)
  + warm:50 (10 min)
  + warm:100 (10 min)
  + warm:200 (10 min)
  + warm:500 (10 min)
  ───────────────────
  Total: ~70+ minutes per seed
```

### After (New)
```
7 independent jobs (all parallel):
  Job 1: baseline (10 min)
  Job 2: warm:5 (10 min)      } All running
  Job 3: warm:20 (10 min)     } simultaneously
  Job 4: warm:50 (10 min)     } on SLURM
  Job 5: warm:100 (10 min)    } = ~10 min
  Job 6: warm:200 (10 min)    } total per
  Job 7: warm:500 (10 min)    } seed
  ───────────────────────────
  Total: ~10 minutes per seed (~2 hours for all 35 runs)
```

## Testing (Optional)

Run a quick local test first:

```bash
python slurm_sweep_full_dataset/main_sweep.py \
    --method baseline \
    --time-limit 600 \
    --seed 0 \
    --output-dir test_results
```

Expected output:
```
test_results/
├── sweep_baseline_0_20260424_130000.json
├── sweep_baseline_0_20260424_130000_regret.png
└── sweep_baseline_0_20260424_130000_ape.png
```

## Validation

Before submitting to SLURM, validate your setup:

```bash
bash slurm_sweep_full_dataset/validate_setup.sh
```

## Output Structure

After all jobs finish, you'll have:

```
slurm_sweep_full_dataset/results_20260424_130000/
├── sweep_baseline_0_*.json          # Seed 0
├── sweep_baseline_1_*.json          # Seed 1
├── sweep_baseline_2_*.json          # Seed 2
├── ... (3 more baseline seeds)
├── sweep_warm_5_0_*.json
├── sweep_warm_5_1_*.json
├── ... (5 seeds × 6 warm weights)
├── sweep_warm_500_4_*.json
├── sweep_baseline_0_*_regret.png
├── sweep_baseline_0_*_ape.png
├── ... (2 plots × 7 methods × 5 seeds = 70 plots)
└── ... (35 JSON files + 70 PNG files)
```

## Post-Processing

Combine all results with error bars:

```bash
cd slurm_sweep_full_dataset
python aggregate_results.py --results-dir results_20260424_130000
```

Generates:
```
results_20260424_130000/
├── aggregated_regret.png      ← Mean ± std for all methods
├── aggregated_ape.png         ← Mean ± std for all methods  
└── aggregated_summary.json    ← Statistics across seeds
```

## Advanced Options

### Add or Remove Methods

Edit `submit_all.sh` line ~50:

```bash
# Current:
METHODS=("baseline" "warm:5" "warm:20" "warm:50" "warm:100" "warm:200" "warm:500")

# Custom:
METHODS=("baseline" "warm:10" "warm:100" "warm:1000")
```

Then:

```bash
bash submit_all.sh
```

### Change Time Limits

Edit `submit_method.sh` line ~62:

```bash
python slurm_sweep_full_dataset/main_sweep.py \
    --method "${METHOD}" \
    --time-limit 3600 \    # ← Change from 7200 (2 hrs) to 3600 (1 hr)
    ...
```

### Dry Run (No Actual Submission)

```bash
bash submit_all.sh --dry-run
```

Shows all sbatch commands without executing them.

## Support

See these files for details:

- **Full docs:** `slurm_sweep_full_dataset/README.md`
- **Visual overview:** `slurm_sweep_full_dataset/ARCHITECTURE.md`
- **5-minute guide:** `slurm_sweep_full_dataset/QUICKSTART.md`

## Questions?

1. **Setup issues?** → Run `validate_setup.sh` 
2. **Want to understand the design?** → Read `ARCHITECTURE.md`
3. **Need quick reference?** → Read `QUICKSTART.md`
4. **Full documentation?** → Read `README.md`

---

**You're all set! Run `bash submit_all.sh` to get started.** 🚀
