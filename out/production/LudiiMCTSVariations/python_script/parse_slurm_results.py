"""Parse SLURM .out and .err files and save summary CSV.
Placed in src/python_script so it can be imported or run.
"""
import os
import re
import pandas as pd

# Determine repository root relative to this script (two levels up)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
RESULTS_DIR = os.path.join(REPO_ROOT, 'slurm_jobs', 'results')

def parse_results(results_dir: str) -> pd.DataFrame:
    files = os.listdir(results_dir)
    out_files = [f for f in files if f.endswith('.out')]
    err_files = [f for f in files if f.endswith('.err')]

    jobs = {}
    for f in out_files:
        base = f[:-4]
        jobs.setdefault(base, {})['out'] = f
    for f in err_files:
        base = f[:-4]
        jobs.setdefault(base, {})['err'] = f

    results = []
    for job, files in sorted(jobs.items()):
        out_path = os.path.join(results_dir, files.get('out', ''))
        err_path = os.path.join(results_dir, files.get('err', ''))

        out_content = ''
        if os.path.exists(out_path):
            with open(out_path, 'r', encoding='utf-8', errors='ignore') as fh:
                out_content = fh.read()

        err_content = ''
        if os.path.exists(err_path):
            with open(err_path, 'r', encoding='utf-8', errors='ignore') as fh:
                err_content = fh.read()

        failed = False
        error_type = ''
        if err_content.strip():
            failed = True
            match = re.search(r'(\w+(Error|Exception))', err_content)
            if match:
                error_type = match.group(1)
            else:
                error_type = err_content.strip().split('\n')[0][:200]

        results.append({
            'job': job,
            'out_file': files.get('out', ''),
            'err_file': files.get('err', ''),
            'failed': failed,
            'error_type': error_type,
            'out_preview': out_content[:200],
            'err_preview': err_content[:200],
        })

    return pd.DataFrame(results)


def main():
    if not os.path.isdir(RESULTS_DIR):
        raise SystemExit(f"Results directory not found: {RESULTS_DIR}")

    df = parse_results(RESULTS_DIR)
    out_csv = os.path.join(HERE, 'parsed_slurm_results.csv')
    df.to_csv(out_csv, index=False)
    print(f"Parsed results saved to {out_csv} (rows={len(df)})")


if __name__ == '__main__':
    main()
