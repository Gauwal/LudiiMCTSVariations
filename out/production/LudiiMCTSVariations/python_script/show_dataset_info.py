import os
import json
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
KRR = os.path.join(os.path.dirname(__file__), 'krr_dataset.csv')
CANDIDATES = [os.path.join(os.path.dirname(__file__), 'parsed_slurm_results.csv'), os.path.join(ROOT, 'parsed_slurm_results.csv')]

print('KRR dataset path:', KRR)
if not os.path.isfile(KRR):
    raise SystemExit('krr_dataset.csv not found')

df = pd.read_csv(KRR)
print('usable_dataset_rows:', len(df))

# sample: first row as JSON
sample = df.iloc[0].to_dict()
print('\nSAMPLE_ROW_JSON:\n')
print(json.dumps(sample, indent=2, default=str))

# find parsed results
parsed_path = None
for p in CANDIDATES:
    if os.path.isfile(p):
        parsed_path = p
        break

if parsed_path:
    pr = pd.read_csv(parsed_path)
    # count failed
    if 'failed' in pr.columns:
        # handle booleans or string values
        try:
            failed_mask = pr['failed'].astype(bool)
        except Exception:
            failed_mask = pr['failed'].astype(str).str.lower().isin(['true', '1', 'yes'])
        n_errors = int(failed_mask.sum())
    elif 'err_file' in pr.columns:
        # count .err files that exist and are non-empty in the results folder
        def err_exists(fn):
            try:
                if not isinstance(fn, str) or not fn.strip():
                    return False
                p = os.path.join(ROOT, 'slurm_jobs', 'results', fn)
                return os.path.exists(p) and os.path.getsize(p) > 0
            except Exception:
                return False
        n_errors = int(pr['err_file'].apply(err_exists).sum())
    else:
        n_errors = 0
    print('\nparsed_results_path:', parsed_path)
    print('n_error_jobs:', n_errors)
else:
    # fallback: count non-empty .err files in slurm_jobs/results
    results_dir = os.path.join(ROOT, 'slurm_jobs', 'results')
    n_err = 0
    for fname in os.listdir(results_dir):
        if fname.endswith('.err'):
            p = os.path.join(results_dir, fname)
            try:
                if os.path.getsize(p) > 0:
                    n_err += 1
            except OSError:
                pass
    print('parsed_results_path: (not found)')
    print('n_error_jobs:', n_err)
