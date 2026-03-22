#!/usr/bin/env python3
"""
Analyze feature correlation with "Job Completed No Results" failure.
Identify which features are most problematic.
"""

import os
import csv
import re
import glob
from collections import defaultdict
from datetime import datetime

import matplotlib.pyplot as plt

RESULTS_DIR = r"d:\Master Thesis\LudiiMCTSVariations\slurm_jobs\1f_timevar\results"
PLANNED_TESTS = r"d:\Master Thesis\LudiiMCTSVariations\planned_tests_1f_timevar.csv"
OUTPUT_PLOT = r"d:\Master Thesis\LudiiMCTSVariations\src\python_script\failure_ratio_by_start_time.png"
OUTPUT_CSV = r"d:\Master Thesis\LudiiMCTSVariations\src\python_script\failure_ratio_by_start_time.csv"
OUTPUT_COUNTS_PLOT = r"d:\Master Thesis\LudiiMCTSVariations\src\python_script\failure_counts_by_start_time.png"

def categorize_test(out_file_path):
    """Categorize a test: 'success' or 'no_results' or 'other'."""
    try:
        with open(out_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read().strip()
        
        if not content:
            return 'other'
        
        has_results = 'Completed T' in content and 'completed=' in content
        if has_results:
            match = re.search(r'completed=(\d+)/(\d+)', content)
            if match:
                completed = int(match.group(1))
                total = int(match.group(2))
                if completed == total:
                    match_failures = re.search(r'failures=(\d+)', content)
                    failures = int(match_failures.group(1)) if match_failures else 0
                    if failures == 0:
                        return 'success'
        
        if 'Job completed' in content and not has_results:
            return 'no_results'
        
        return 'other'
    
    except:
        return 'other'


def parse_start_time(content):
    """Extract start timestamp from the first 'Running ... at ...' line."""
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("Running ") and " at " in line:
            ts = line.rsplit(" at ", 1)[-1].strip()
            # Example: Thu Mar 12 15:16:59 CET 2026
            parts = ts.split()
            try:
                if len(parts) == 6:
                    # Drop timezone token (CET), parse naive local time.
                    ts = " ".join(parts[:4] + parts[5:])
                return datetime.strptime(ts, "%a %b %d %H:%M:%S %Y")
            except ValueError:
                return None
    return None


def extract_test_id(out_filename):
    """Extract test ID from filename like 'planned_T1000_6071840.out'"""
    match = re.search(r'_T(\d+)_', out_filename)
    if match:
        return f"T{match.group(1)}"
    return None


def load_planned_tests(csv_path):
    """Load planned tests with their features."""
    tests = {}
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            test_id = row['testId']
            tests[test_id] = row
    return tests


def main():
    print("=" * 120)
    print("FEATURE CORRELATION WITH 'JOB COMPLETED NO RESULTS' FAILURE")
    print("=" * 120)
    
    # Load planned tests
    planned_tests = load_planned_tests(PLANNED_TESTS)
    print(f"\nLoaded {len(planned_tests)} planned tests")
    
    # Categorize all tests
    test_results = {}
    out_files = sorted(glob.glob(os.path.join(RESULTS_DIR, "*.out")))
    
    for i, out_file in enumerate(out_files):
        
        test_id = extract_test_id(os.path.basename(out_file))
        if test_id:
            category = categorize_test(out_file)
            start_time = None
            try:
                with open(out_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                start_time = parse_start_time(content)
            except Exception:
                start_time = None

            test_results[test_id] = {
                'category': category,
                'features': planned_tests.get(test_id, {}),
                'start_time': start_time,
            }
    
    # Features to analyze
    features = [
        'gameName',
        'component',
        'variantSelection',
        'variantSimulation',
        'variantBackprop',
        'variantFinalMove',
        'moveTimeSeconds',
        'gamesPerMatchup',
        'usesHeuristic'
    ]
    
    print("\n" + "=" * 120)
    print("FEATURE ANALYSIS - NO_RESULTS FAILURE RATE")
    print("=" * 120)
    
    for feature_name in features:
        print(f"\n{'=' * 120}")
        print(f"FEATURE: {feature_name}")
        print(f"{'=' * 120}\n")
        
        feature_data = defaultdict(lambda: {'success': 0, 'no_results': 0, 'other': 0})
        
        for test_id, result in test_results.items():
            feature_val = result['features'].get(feature_name, 'UNKNOWN')
            category = result['category']
            feature_data[feature_val][category] += 1
        
        # Sort by no_results rate (descending)
        sorted_features = sorted(
            feature_data.items(),
            key=lambda x: (x[1]['no_results'] / (x[1]['no_results'] + x[1]['success']) if x[1]['no_results'] + x[1]['success'] > 0 else 0),
            reverse=True
        )
        
        print(f"{'Feature Value':<50} {'Success':<10} {'No Results':<12} {'Failure %':<12}")
        print("-" * 120)
        
        for feature_val, counts in sorted_features:
            total = counts['success'] + counts['no_results'] + counts['other']
            no_results_pct = (counts['no_results'] / (counts['no_results'] + counts['success']) * 100) if (counts['no_results'] + counts['success']) > 0 else 0
            
            print(f"{str(feature_val):<50} {counts['success']:<10} {counts['no_results']:<12} {no_results_pct:>7.1f}%")
    
    # Summary statistics
    print("\n" + "=" * 120)
    print("SUMMARY STATISTICS")
    print("=" * 120)
    
    total_success = sum(1 for r in test_results.values() if r['category'] == 'success')
    total_no_results = sum(1 for r in test_results.values() if r['category'] == 'no_results')
    total_other = sum(1 for r in test_results.values() if r['category'] == 'other')
    
    print(f"\nTotal tests: {len(test_results)}")
    print(f"  Success: {total_success} ({total_success/len(test_results)*100:.1f}%)")
    print(f"  No Results: {total_no_results} ({total_no_results/len(test_results)*100:.1f}%)")
    print(f"  Other: {total_other} ({total_other/len(test_results)*100:.1f}%)")

    # Time-based analysis and graph generation
    print("\n" + "=" * 120)
    print("FAILURE RATIO BY START TIME")
    print("=" * 120)

    time_buckets = defaultdict(lambda: {'success': 0, 'no_results': 0, 'other': 0})
    timed_rows = []
    for test_id, result in test_results.items():
        dt = result.get('start_time')
        if dt is None:
            continue
        hour_key = dt.replace(minute=0, second=0, microsecond=0)
        category = result['category']
        time_buckets[hour_key][category] += 1
        timed_rows.append((dt, category))

    if time_buckets:
        sorted_hours = sorted(time_buckets.keys())
        print(f"Timed tests parsed: {len(timed_rows)}")
        print(f"Time window: {sorted_hours[0]} to {sorted_hours[-1]}")

        # Write per-hour CSV for quick external plotting/inspection.
        with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'hour',
                'total',
                'success',
                'no_results',
                'other',
                'failure_ratio_no_results',
                'success_ratio',
            ])
            for hour in sorted_hours:
                c = time_buckets[hour]
                total = c['success'] + c['no_results'] + c['other']
                failure_ratio = c['no_results'] / total if total > 0 else 0.0
                success_ratio = c['success'] / total if total > 0 else 0.0
                writer.writerow([
                    hour.isoformat(sep=' '),
                    total,
                    c['success'],
                    c['no_results'],
                    c['other'],
                    f"{failure_ratio:.6f}",
                    f"{success_ratio:.6f}",
                ])

        # Build chart lines.
        hourly_failure_ratio = []
        hourly_success_ratio = []
        rolling_failure_ratio = []
        rolling_success_ratio = []
        hourly_success_count = []
        hourly_no_results_count = []
        hourly_other_count = []
        rolling_success_count = []
        rolling_no_results_count = []
        rolling_other_count = []

        cum_total = 0
        cum_fail = 0
        cum_success = 0
        cum_other = 0
        for hour in sorted_hours:
            c = time_buckets[hour]
            total = c['success'] + c['no_results'] + c['other']
            fail = c['no_results']
            succ = c['success']
            oth = c['other']

            hourly_failure_ratio.append(fail / total if total > 0 else 0.0)
            hourly_success_ratio.append(succ / total if total > 0 else 0.0)
            hourly_success_count.append(succ)
            hourly_no_results_count.append(fail)
            hourly_other_count.append(oth)

            cum_total += total
            cum_fail += fail
            cum_success += succ
            cum_other += oth
            rolling_failure_ratio.append(cum_fail / cum_total if cum_total > 0 else 0.0)
            rolling_success_ratio.append(cum_success / cum_total if cum_total > 0 else 0.0)
            rolling_success_count.append(cum_success)
            rolling_no_results_count.append(cum_fail)
            rolling_other_count.append(cum_other)

        # Find strongest regime shift (hourly failure increase).
        biggest_jump = None
        for i in range(1, len(sorted_hours)):
            jump = hourly_failure_ratio[i] - hourly_failure_ratio[i - 1]
            if biggest_jump is None or jump > biggest_jump[0]:
                biggest_jump = (jump, sorted_hours[i - 1], sorted_hours[i])

        if biggest_jump is not None:
            jump_val, from_t, to_t = biggest_jump
            print(
                f"Largest one-hour failure-ratio jump: {jump_val * 100:.1f} percentage points "
                f"({from_t} -> {to_t})"
            )

        # Plot and save figure.
        fig, ax = plt.subplots(1, 1, figsize=(14, 6))
        ax.plot(sorted_hours, hourly_failure_ratio, marker='o', linewidth=2, label='Hourly failure ratio (no_results/total)')
        ax.plot(sorted_hours, rolling_failure_ratio, linestyle='--', linewidth=2, label='Cumulative failure ratio')
        ax.plot(sorted_hours, hourly_success_ratio, marker='.', linewidth=1.5, alpha=0.8, label='Hourly success ratio')
        ax.plot(sorted_hours, rolling_success_ratio, linestyle=':', linewidth=2, label='Cumulative success ratio')
        ax.set_title('Failure Ratio vs Start Time (1f_timevar)')
        ax.set_xlabel('Start Time (hour bucket)')
        ax.set_ylabel('Ratio')
        ax.set_ylim(0.0, 1.05)
        ax.grid(True, alpha=0.3)
        ax.legend(loc='best')
        fig.autofmt_xdate()
        plt.tight_layout()
        plt.savefig(OUTPUT_PLOT, dpi=180)
        plt.close(fig)

        # Plot and save raw-count figure.
        fig, ax = plt.subplots(1, 1, figsize=(14, 6))
        ax.plot(sorted_hours, hourly_no_results_count, marker='o', linewidth=2, label='Hourly no_results count')
        ax.plot(sorted_hours, hourly_success_count, marker='o', linewidth=2, label='Hourly success count')
        if any(v > 0 for v in hourly_other_count):
            ax.plot(sorted_hours, hourly_other_count, marker='o', linewidth=1.5, label='Hourly other count')

        ax.plot(sorted_hours, rolling_no_results_count, linestyle='--', linewidth=2, label='Cumulative no_results count')
        ax.plot(sorted_hours, rolling_success_count, linestyle='--', linewidth=2, label='Cumulative success count')
        if any(v > 0 for v in rolling_other_count):
            ax.plot(sorted_hours, rolling_other_count, linestyle='--', linewidth=1.5, label='Cumulative other count')

        ax.set_title('Failure Counts vs Start Time (1f_timevar)')
        ax.set_xlabel('Start Time (hour bucket)')
        ax.set_ylabel('Raw Count')
        ax.grid(True, alpha=0.3)
        ax.legend(loc='best')
        fig.autofmt_xdate()
        plt.tight_layout()
        plt.savefig(OUTPUT_COUNTS_PLOT, dpi=180)
        plt.close(fig)

        print(f"Saved graph: {OUTPUT_PLOT}")
        print(f"Saved graph: {OUTPUT_COUNTS_PLOT}")
        print(f"Saved hourly data: {OUTPUT_CSV}")
    else:
        print("No start timestamps could be parsed from .out files.")
    
    # Find worst games
    print("\n" + "-" * 120)
    print("WORST PERFORMING GAMES (by no_results rate):")
    print("-" * 120)
    
    game_stats = defaultdict(lambda: {'success': 0, 'no_results': 0})
    for test_id, result in test_results.items():
        game = result['features'].get('gameName', 'UNKNOWN')
        if result['category'] == 'success':
            game_stats[game]['success'] += 1
        elif result['category'] == 'no_results':
            game_stats[game]['no_results'] += 1
    
    sorted_games = sorted(
        game_stats.items(),
        key=lambda x: (x[1]['no_results'] / (x[1]['no_results'] + x[1]['success']) if x[1]['no_results'] + x[1]['success'] > 0 else 0),
        reverse=True
    )
    
    for game, counts in sorted_games[:30]:
        total = counts['success'] + counts['no_results']
        no_results_pct = counts['no_results'] / total * 100 if total > 0 else 0
        print(f"{game:<50} {counts['success']:>3} success, {counts['no_results']:>3} no_results ({no_results_pct:>5.1f}% fail)")
    
    # Find best games
    print("\n" + "-" * 120)
    print("BEST PERFORMING GAMES (by success rate):")
    print("-" * 120)
    
    for game, counts in sorted(sorted_games, key=lambda x: x[1]['success'] / (x[1]['success'] + x[1]['no_results']) if x[1]['success'] + x[1]['no_results'] > 0 else 0, reverse=True)[:20]:
        total = counts['success'] + counts['no_results']
        success_pct = counts['success'] / total * 100 if total > 0 else 0
        if counts['success'] > 0:
            print(f"{game:<50} {counts['success']:>3} success, {counts['no_results']:>3} no_results ({success_pct:>5.1f}% pass)")
    
    # Analyze by selection strategy
    print("\n" + "-" * 120)
    print("WORST SELECTION STRATEGIES (by no_results rate):")
    print("-" * 120)
    
    selection_stats = defaultdict(lambda: {'success': 0, 'no_results': 0})
    for test_id, result in test_results.items():
        strategy = result['features'].get('variantSelection', 'UNKNOWN')
        if result['category'] == 'success':
            selection_stats[strategy]['success'] += 1
        elif result['category'] == 'no_results':
            selection_stats[strategy]['no_results'] += 1
    
    sorted_strategies = sorted(
        selection_stats.items(),
        key=lambda x: (x[1]['no_results'] / (x[1]['no_results'] + x[1]['success']) if x[1]['no_results'] + x[1]['success'] > 0 else 0),
        reverse=True
    )
    
    for strategy, counts in sorted_strategies[:15]:
        total = counts['success'] + counts['no_results']
        no_results_pct = counts['no_results'] / total * 100 if total > 0 else 0
        print(f"{strategy:<50} {counts['success']:>3} success, {counts['no_results']:>3} no_results ({no_results_pct:>5.1f}% fail)")

    # Explanatory notes removed: scripts should only print titles or data


if __name__ == "__main__":
    main()
