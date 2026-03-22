#!/usr/bin/env python3
"""
Diagnose why tests are being rejected - check actual output files.
"""

import argparse
import os
import glob
import re
from collections import defaultdict

RESULTS_DIR = r"d:\Master Thesis\LudiiMCTSVariations\slurm_jobs\1f_timevar\results"
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))


def extract_test_id_from_name(path_or_name):
    """Extract T#### from filename/path like planned_T10000_6080840.out."""
    name = os.path.basename(path_or_name)
    m = re.search(r'_T(\d+)_', name)
    if m:
        return f"T{m.group(1)}"
    return None


def classify_err(err_file_path):
    """Classify root cause from .err text."""
    if not os.path.exists(err_file_path):
        return 'ERR_MISSING', ''

    try:
        with open(err_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read().strip()
    except Exception as e:
        return f'ERR_READ_ERROR: {str(e)[:40]}', ''

    if not content:
        return 'ERR_EMPTY', ''

    if 'TestId not found in plan:' in content:
        m = re.search(r'TestId not found in plan:\s*(T\d+)', content)
        missing_id = m.group(1) if m else ''
        return 'TEST_ID_NOT_FOUND_IN_PLAN', missing_id

    if 'DUE TO TIME LIMIT' in content or 'CANCELLED' in content:
        return 'SLURM_TIME_LIMIT_OR_CANCELLED', ''

    if 'OutOfMemoryError' in content or 'oom-kill' in content:
        return 'OOM', ''

    if 'Game exceeded time limit' in content:
        return 'GAME_SAFETY_TIMEOUT', ''

    if 'Exception' in content or 'error' in content.lower():
        return 'OTHER_ERR_EXCEPTION', ''

    return 'ERR_OTHER', ''


def load_plan_ids(plan_path):
    """Load test IDs from plan CSV (first column named testId)."""
    ids = set()
    if not os.path.isfile(plan_path):
        return ids

    with open(plan_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.read().splitlines()

    if not lines:
        return ids

    # Skip header
    for line in lines[1:]:
        if not line.strip():
            continue
        # First CSV token can be quoted
        first = line.split(',', 1)[0].strip().strip('"')
        if re.match(r'^T\d+$', first):
            ids.add(first)
    return ids

def categorize_test(out_file_path):
    """Categorize a test by analyzing its output."""
    try:
        with open(out_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read().strip()
        
        if not content:
            return 'EMPTY'
        
        # Check for the key markers
        has_started = 'Running ' in content
        has_job_completed = 'Job completed' in content
        has_results = 'Completed T' in content and 'completed=' in content
        has_error = 'Error' in content or 'Exception' in content or 'error' in content
        
        if has_results:
            # Check if it's complete
            match = re.search(r'completed=(\d+)/(\d+)', content)
            if match:
                completed = int(match.group(1))
                total = int(match.group(2))
                if completed == total:
                    match_failures = re.search(r'failures=(\d+)', content)
                    failures = int(match_failures.group(1)) if match_failures else 0
                    if failures == 0:
                        return 'SUCCESS'
                    else:
                        return f'PARTIAL_FAILURES ({failures})'
                else:
                    return f'PARTIAL_COMPLETE ({completed}/{total})'
            return 'HAS_RESULTS_BUT_MALFORMED'
        
        elif has_error:
            # Extract error context
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'error' in line.lower() or 'exception' in line.lower():
                    return f'ERROR: {line[:60]}'
            return 'ERROR_UNKNOWN'
        
        elif has_job_completed and not has_results:
            return 'JOB_COMPLETED_NO_RESULTS'
        
        elif has_started:
            return 'STARTED_NO_COMPLETION'
        
        else:
            return 'UNKNOWN_FORMAT'

    except Exception as e:
        return f'READ_ERROR: {str(e)[:40]}'


def main():
    parser = argparse.ArgumentParser(description='Diagnose SLURM test-output failures')
    parser.add_argument('--results-dir', default=RESULTS_DIR, help='Path to SLURM results directory')
    args = parser.parse_args()

    results_dir = os.path.abspath(args.results_dir)

    print("=" * 100)
    print("TEST OUTPUT DIAGNOSTICS")
    print("=" * 100)

    print(f"Results dir: {results_dir}")

    # Get all .out files
    out_files = sorted(glob.glob(os.path.join(results_dir, "*.out")))
    print(f"\nFound {len(out_files)} .out files")

    # Categorize each
    categories = defaultdict(list)
    err_categories = defaultdict(list)
    out_to_err_root = {}
    test_ids_seen = set()
    missing_in_plan_ids = set()
    
    for i, out_file in enumerate(out_files):
        if i % 1000 == 0:
            print(f"Processing {i}/{len(out_files)}...")

        category = categorize_test(out_file)
        test_name = os.path.basename(out_file).replace('.out', '')
        test_id = extract_test_id_from_name(out_file)
        if test_id:
            test_ids_seen.add(test_id)

        err_file = out_file[:-4] + '.err'
        err_category, missing_test_id = classify_err(err_file)

        categories[category].append(test_name)
        err_categories[err_category].append(test_name)
        out_to_err_root[test_name] = err_category
        if missing_test_id:
            missing_in_plan_ids.add(missing_test_id)
    
    print("\n" + "=" * 100)
    print("RESULTS BREAKDOWN")
    print("=" * 100)
    
    # Sort by frequency
    sorted_categories = sorted(categories.items(), key=lambda x: -len(x[1]))
    
    total_tests = len(out_files)
    for category, tests in sorted_categories:
        count = len(tests)
        pct = count / total_tests * 100
        print(f"\n{category:<50} {count:>6} ({pct:>5.1f}%)")

        # Show examples
        for test_name in tests[:3]:
            out_path = os.path.join(results_dir, test_name + '.out')
            with open(out_path, 'r', encoding='utf-8', errors='ignore') as f:
                first_lines = f.read().split('\n')[:3]
            print(f"    Example: {test_name}")
            for line in first_lines:
                if line.strip():
                    print(f"      {line[:70]}")

    print("\n" + "=" * 100)
    print("ERROR ROOT-CAUSE BREAKDOWN (.err)")
    print("=" * 100)
    sorted_err_categories = sorted(err_categories.items(), key=lambda x: -len(x[1]))
    for category, tests in sorted_err_categories:
        count = len(tests)
        pct = count / total_tests * 100 if total_tests else 0.0
        print(f"{category:<50} {count:>6} ({pct:>5.1f}%)")

    no_results_tests = categories.get('JOB_COMPLETED_NO_RESULTS', [])
    if no_results_tests:
        no_results_with_missing_plan = sum(
            1 for t in no_results_tests if out_to_err_root.get(t) == 'TEST_ID_NOT_FOUND_IN_PLAN'
        )
        no_results_pct = no_results_with_missing_plan / len(no_results_tests) * 100

        print("\n" + "=" * 100)
        print("NO_RESULTS CORRELATION WITH .err ROOT CAUSE")
        print("=" * 100)
        print(
            f"JOB_COMPLETED_NO_RESULTS explained by TEST_ID_NOT_FOUND_IN_PLAN: "
            f"{no_results_with_missing_plan}/{len(no_results_tests)} ({no_results_pct:.1f}%)"
        )

    # Plan-coverage cross-check for quick diagnosis
    default_plan = os.path.join(REPO_ROOT, 'planned_tests.csv')
    timevar_plan = os.path.join(REPO_ROOT, 'planned_tests_1f_timevar.csv')
    default_ids = load_plan_ids(default_plan)
    timevar_ids = load_plan_ids(timevar_plan)

    if test_ids_seen and default_ids:
        missing_in_default = sorted(test_ids_seen - default_ids, key=lambda s: int(s[1:]))
        present_in_timevar_missing_default = sorted(
            (set(missing_in_default) & timevar_ids),
            key=lambda s: int(s[1:])
        )

        print("\n" + "=" * 100)
        print("PLAN CROSS-CHECK")
        print("=" * 100)
        print(f"IDs seen in result filenames: {len(test_ids_seen)}")
        print(f"IDs in planned_tests.csv: {len(default_ids)}")
        print(f"IDs in planned_tests_1f_timevar.csv: {len(timevar_ids)}")
        print(f"IDs seen but missing from planned_tests.csv: {len(missing_in_default)}")
        print(f"...of those present in planned_tests_1f_timevar.csv: {len(present_in_timevar_missing_default)}")
        if missing_in_default:
            preview = ', '.join(missing_in_default[:10])
            print(f"Example missing-in-default IDs: {preview}")
        if missing_in_plan_ids:
            preview_missing = ', '.join(sorted(missing_in_plan_ids, key=lambda s: int(s[1:]))[:10])
            print(f"Example IDs reported by RunPlannedTest as missing: {preview_missing}")
    
    print("\n" + "=" * 100)
    print(f"Summary: {len(categories.get('SUCCESS', []))}/{total_tests} tests succeeded")
    print("=" * 100)


if __name__ == "__main__":
    main()
