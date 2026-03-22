#!/usr/bin/env python3
"""
Find successful test combinations - which games/features work best.
"""

import os
import csv
import re
import glob
from collections import defaultdict
import json

RESULTS_DIR = r"d:\Master Thesis\LudiiMCTSVariations\slurm_jobs\1f_timevar\results"
PLANNED_TESTS = r"d:\Master Thesis\LudiiMCTSVariations\planned_tests_1f_timevar.csv"

def categorize_test(out_file_path):
    """Categorize test result."""
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
        
        return 'failed'
    except:
        return 'failed'


def extract_test_id(out_filename):
    """Extract test ID from filename."""
    match = re.search(r'_T(\d+)_', out_filename)
    if match:
        return f"T{match.group(1)}"
    return None


def load_planned_tests(csv_path):
    """Load planned tests with features."""
    tests = {}
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            test_id = row['testId']
            tests[test_id] = row
    return tests


def main():
    print("=" * 100)
    print("SUCCESSFUL FEATURE COMBINATIONS ANALYSIS")
    print("=" * 100)
    
    # Load data
    planned_tests = load_planned_tests(PLANNED_TESTS)
    print(f"\nLoaded {len(planned_tests)} planned tests")
    
    # Find all successful tests
    print("Analyzing successes...")
    successful_tests = {}
    out_files = sorted(glob.glob(os.path.join(RESULTS_DIR, "*.out")))
    
    for i, out_file in enumerate(out_files):
        if i % 2000 == 0:
            print(f"  {i}/{len(out_files)}")
        
        test_id = extract_test_id(os.path.basename(out_file))
        if test_id:
            if categorize_test(out_file) == 'success':
                successful_tests[test_id] = planned_tests.get(test_id, {})
    
    print(f"\nFound {len(successful_tests)} successful tests")
    
    # Convert to list for sorting
    success_list = [(tid, features) for tid, features in successful_tests.items()]
    
    # Find game-component combinations that work
    print("\n" + "=" * 100)
    print("SUCCESSFUL GAME-COMPONENT COMBINATIONS")
    print("=" * 100)
    
    combo_stats = defaultdict(lambda: {'count': 0, 'tests': []})
    
    for test_id, features in successful_tests.items():
        game = features.get('gameName', 'UNKNOWN')
        component = features.get('component', 'UNKNOWN')
        key = f"{game} + {component}"
        combo_stats[key]['count'] += 1
        combo_stats[key]['tests'].append(test_id)
    
    sorted_combos = sorted(combo_stats.items(), key=lambda x: -x[1]['count'])
    
    print(f"\n{'Game + Component':<60} {'Count':<8} {'Tests'}")
    print("-" * 100)
    for combo, data in sorted_combos[:30]:
        tests_str = ', '.join(data['tests'][:3])
        if len(data['tests']) > 3:
            tests_str += f", ... ({len(data['tests'])} total)"
        print(f"{combo:<60} {data['count']:<8} {tests_str}")
    
    # Find game-selection combinations that work
    print("\n" + "=" * 100)
    print("SUCCESSFUL GAME-SELECTION STRATEGY COMBINATIONS")
    print("=" * 100)
    
    combo_stats2 = defaultdict(lambda: {'count': 0, 'tests': []})
    
    for test_id, features in successful_tests.items():
        game = features.get('gameName', 'UNKNOWN')
        selection = features.get('variantSelection', 'UNKNOWN')
        key = f"{game} + {selection}"
        combo_stats2[key]['count'] += 1
        combo_stats2[key]['tests'].append(test_id)
    
    sorted_combos2 = sorted(combo_stats2.items(), key=lambda x: -x[1]['count'])
    
    print(f"\n{'Game + Selection Strategy':<60} {'Count':<8} {'Tests'}")
    print("-" * 100)
    for combo, data in sorted_combos2[:30]:
        tests_str = ', '.join(data['tests'][:2])
        if len(data['tests']) > 2:
            tests_str += f", ... ({len(data['tests'])} total)"
        print(f"{combo:<60} {data['count']:<8} {tests_str}")
    
    # Best games (those with most successful tests)
    print("\n" + "=" * 100)
    print("GAMES WITH MOST SUCCESSFUL TESTS")
    print("=" * 100)
    
    game_counts = defaultdict(list)
    for test_id, features in successful_tests.items():
        game = features.get('gameName', 'UNKNOWN')
        game_counts[game].append(test_id)
    
    sorted_games = sorted(game_counts.items(), key=lambda x: -len(x[1]))
    
    print(f"\n{'Game':<50} {'Success Count':<15} {'Tests'}")
    print("-" * 100)
    for game, tests in sorted_games[:20]:
        tests_str = ', '.join(tests[:3])
        if len(tests) > 3:
            tests_str += f", +{len(tests)-3} more"
        print(f"{game:<50} {len(tests):<15} {tests_str}")
    
    # Find best selection strategies among successes
    print("\n" + "=" * 100)
    print("SELECTION STRATEGIES WITH MOST SUCCESSFUL TESTS")
    print("=" * 100)
    
    selection_counts = defaultdict(list)
    for test_id, features in successful_tests.items():
        selection = features.get('variantSelection', 'UNKNOWN')
        selection_counts[selection].append(test_id)
    
    sorted_selections = sorted(selection_counts.items(), key=lambda x: -len(x[1]))
    
    print(f"\n{'Selection Strategy':<50} {'Success Count':<15} {'Tests'}")
    print("-" * 100)
    for strategy, tests in sorted_selections:
        tests_str = ', '.join(tests[:3])
        if len(tests) > 3:
            tests_str += f", +{len(tests)-3} more"
        print(f"{strategy:<50} {len(tests):<15} {tests_str}")
    
    # Output JSON summary
    summary = {
        'total_successful': len(successful_tests),
        'successful_tests': list(successful_tests.keys()),
        'best_games': {game: len(tests) for game, tests in sorted_games[:10]},
        'best_selections': {strategy: len(tests) for strategy, tests in sorted_selections},
        'game_component_combinations': {combo: data['count'] for combo, data in sorted_combos[:10]},
    }
    
    output_file = r"d:\Master Thesis\LudiiMCTSVariations\src\python_script\successful_combinations.json"
    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary saved to: {output_file}")


if __name__ == "__main__":
    main()
