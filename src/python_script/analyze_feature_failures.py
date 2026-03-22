#!/usr/bin/env python3
"""
Analyze test failures and rejections feature by feature.
This script examines which tests failed/were rejected and correlates this with features.
"""

import os
import csv
import re
from collections import defaultdict
import glob
import json

# Paths
RESULTS_DIR = r"d:\Master Thesis\LudiiMCTSVariations\slurm_jobs\1f_timevar\results"
PLANNED_TESTS = r"d:\Master Thesis\LudiiMCTSVariations\planned_tests_1f_timevar.csv"

def parse_test_result(test_id, out_file_path):
    """
    Parse a single .out file to extract test result status.
    Returns: {
        'test_id': str,
        'game': str,
        'variant': str,
        'completed': int,
        'total': int,
        'wins': int,
        'losses': int,
        'draws': int,
        'failures': int,
        'avg_moves': float,
        'status': 'completed' | 'partial' | 'failed' | 'missing'
    }
    """
    result = {
        'test_id': test_id,
        'game': None,
        'variant': None,
        'completed': 0,
        'total': 0,
        'wins': 0,
        'losses': 0,
        'draws': 0,
        'failures': 0,
        'avg_moves': 0.0,
        'status': 'missing',
        'rejected': False
    }
    
    if not os.path.exists(out_file_path):
        return result
    
    try:
        with open(out_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        if not content.strip():
            result['status'] = 'empty'
            result['rejected'] = True
            return result
        
        lines = content.strip().split('\n')
        
        # Parse metadata
        for line in lines:
            if line.startswith('Game:'):
                result['game'] = line.replace('Game:', '').strip()
            elif line.startswith('Variant:'):
                result['variant'] = line.replace('Variant:', '').strip()
            elif 'Completed' in line or 'completed=' in line:
                # Example: "Completed T1000 (Veloop (Square)) -> completed=30/30, wins=19, losses=11, draws=0, failures=0, avgMoves=49.1"
                match = re.search(r'completed=(\d+)/(\d+)', line)
                if match:
                    result['completed'] = int(match.group(1))
                    result['total'] = int(match.group(2))
                
                match = re.search(r'wins=(\d+)', line)
                if match:
                    result['wins'] = int(match.group(1))
                
                match = re.search(r'losses=(\d+)', line)
                if match:
                    result['losses'] = int(match.group(1))
                
                match = re.search(r'draws=(\d+)', line)
                if match:
                    result['draws'] = int(match.group(1))
                
                match = re.search(r'failures=(\d+)', line)
                if match:
                    result['failures'] = int(match.group(1))
                
                match = re.search(r'avgMoves=(\d+\.?\d*)', line)
                if match:
                    result['avg_moves'] = float(match.group(1))
        
        # Determine status
        if result['total'] > 0:
            if result['completed'] == result['total'] and result['failures'] == 0:
                result['status'] = 'completed'
            elif result['completed'] > 0:
                result['status'] = 'partial'
                result['rejected'] = True
            else:
                result['status'] = 'failed'
                result['rejected'] = True
        else:
            result['status'] = 'failed'
            result['rejected'] = True
            
        return result
    
    except Exception as e:
        result['status'] = 'error'
        result['rejected'] = True
        print(f"Error parsing {out_file_path}: {e}")
        return result


def load_planned_tests(csv_path):
    """Load planned tests with their features."""
    tests = {}
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                test_id = row['testId']
                # Extract test number
                tests[test_id] = row
    except Exception as e:
        print(f"Error loading planned tests: {e}")
    
    return tests


def extract_test_id(out_filename):
    """Extract test ID from filename like 'planned_T1000_6071840.out'"""
    match = re.search(r'_T(\d+)_', out_filename)
    if match:
        return f"T{match.group(1)}"
    return None


def main():
    print("=" * 100)
    print("FEATURE-BY-FEATURE FAILURE ANALYSIS")
    print("=" * 100)

    planned_tests = load_planned_tests(PLANNED_TESTS)
    print(f"Loaded {len(planned_tests)} planned tests")

    test_results = {}
    rejected_count = 0
    completed_count = 0

    out_files = glob.glob(os.path.join(RESULTS_DIR, "*.out"))
    print(f"Found {len(out_files)} .out files")

    for out_file in sorted(out_files):
        test_id = extract_test_id(os.path.basename(out_file))
        if test_id:
            result = parse_test_result(test_id, out_file)
            test_results[test_id] = result

            if result['rejected']:
                rejected_count += 1
            if result['status'] == 'completed':
                completed_count += 1
    
    print(f"Completed parsing: {completed_count} completed, {rejected_count} rejected")
    print(f"Total unique tests: {len(test_results)}")
    
    # Merge with planned test features
    print("\nMerging with feature data...")
    for test_id in test_results:
        if test_id in planned_tests:
            test_results[test_id]['features'] = planned_tests[test_id]
        else:
            test_results[test_id]['features'] = {}
    
    # Analyze features
    features_to_analyze = [
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
    
    print("\n" + "=" * 100)
    print("FAILURE ANALYSIS BY FEATURE")
    print("=" * 100)
    
    for feature in features_to_analyze:
        print(f"\n{'=' * 100}")
        print(f"FEATURE: {feature}")
        print(f"{'=' * 100}")
        
        feature_stats = defaultdict(lambda: {
            'total': 0,
            'rejected': 0,
            'completed': 0,
            'partial': 0,
            'failed': 0,
            'test_ids': []
        })
        
        for test_id, result in test_results.items():
            features = result.get('features', {})
            feature_value = features.get(feature, 'UNKNOWN')
            
            feature_stats[feature_value]['total'] += 1
            feature_stats[feature_value]['test_ids'].append(test_id)
            
            if result['rejected']:
                feature_stats[feature_value]['rejected'] += 1
            if result['status'] == 'completed':
                feature_stats[feature_value]['completed'] += 1
            elif result['status'] == 'partial':
                feature_stats[feature_value]['partial'] += 1
            else:
                feature_stats[feature_value]['failed'] += 1
        
        # Sort by rejection rate (descending)
        sorted_values = sorted(
            feature_stats.items(),
            key=lambda x: (x[1]['rejected'] / x[1]['total'] if x[1]['total'] > 0 else 0),
            reverse=True
        )
        
        print(f"\n{'Value':<40} {'Total':<8} {'Completed':<12} {'Partial':<10} {'Failed':<10} {'Reject %':<10}")
        print("-" * 100)
        
        for feature_value, stats in sorted_values:
            total = stats['total']
            completed = stats['completed']
            partial = stats['partial']
            failed = stats['failed']
            reject_pct = (stats['rejected'] / total * 100) if total > 0 else 0
            
            print(f"{str(feature_value):<40} {total:<8} {completed:<12} {partial:<10} {failed:<10} {reject_pct:>7.1f}%")
            
            # Show worst cases
            if stats['rejected'] > 0 and stats['rejected'] <= 5:
                rejected_ids = [tid for tid in stats['test_ids'] if test_results[tid]['rejected']]
                for rid in rejected_ids[:5]:
                    res = test_results[rid]
                    print(f"    -> {rid}: {res['status']} (completed={res['completed']}/{res['total']}, failures={res['failures']})")
    
    # Overall summary
    print(f"\n{'=' * 100}")
    print("OVERALL SUMMARY")
    print(f"{'=' * 100}")
    print(f"Total tests processed: {len(test_results)}")
    print(f"Completed successfully: {completed_count} ({completed_count/len(test_results)*100:.1f}%)")
    print(f"Rejected/Failed: {rejected_count} ({rejected_count/len(test_results)*100:.1f}%)")
    
    # Analyze rejected tests
    print(f"\n{'=' * 100}")
    print("REJECTED TESTS ANALYSIS")
    print(f"{'=' * 100}")
    
    rejected_tests = {tid: res for tid, res in test_results.items() if res['rejected']}
    status_counts = defaultdict(int)
    
    for test_id, result in rejected_tests.items():
        status_counts[result['status']] += 1
    
    print("\nRejected test breakdown by status:")
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        pct = count / len(rejected_tests) * 100
        print(f"  {status:<15}: {count:>6} ({pct:>5.1f}%)")
    
    # Find tests with partial completion
    partial_tests = {tid: res for tid, res in test_results.items() if res['status'] == 'partial'}
    if partial_tests:
        print(f"\nPartial completion details (showing up to 20):")
        for i, (test_id, result) in enumerate(list(partial_tests.items())[:20]):
            game = result.get('features', {}).get('gameName', 'UNKNOWN')
            variant = result.get('features', {}).get('variantSelection', 'UNKNOWN')
            print(f"  {test_id} ({game}, {variant}): {result['completed']}/{result['total']} completed, {result['failures']} failures")
    
    # Find tests with zero completion
    failed_tests = {tid: res for tid, res in test_results.items() if res['status'] == 'failed'}
    if failed_tests:
        print(f"\nZero-completion tests by game:")
        game_failures = defaultdict(list)
        for test_id, result in failed_tests.items():
            game = result.get('features', {}).get('gameName', 'UNKNOWN')
            game_failures[game].append(test_id)
        
        for game, test_ids in sorted(game_failures.items(), key=lambda x: -len(x[1]))[:10]:
            print(f"  {game}: {len(test_ids)} tests failed")
            for tid in test_ids[:3]:
                print(f"    -> {tid}")
    
    # Save detailed results to JSON
    output_file = r"d:\Master Thesis\LudiiMCTSVariations\src\python_script\feature_failure_report.json"
    report = {
        'summary': {
            'total_tests': len(test_results),
            'completed': completed_count,
            'rejected': rejected_count,
            'completion_rate': completed_count / len(test_results) if test_results else 0
        },
        'by_feature': {}
    }
    
    for feature in features_to_analyze:
        feature_stats = defaultdict(lambda: {
            'total': 0,
            'rejected': 0,
            'completed': 0,
            'partial': 0,
            'failed': 0
        })
        
        for test_id, result in test_results.items():
            features = result.get('features', {})
            feature_value = features.get(feature, 'UNKNOWN')
            
            feature_stats[feature_value]['total'] += 1
            if result['rejected']:
                feature_stats[feature_value]['rejected'] += 1
            if result['status'] == 'completed':
                feature_stats[feature_value]['completed'] += 1
            elif result['status'] == 'partial':
                feature_stats[feature_value]['partial'] += 1
            else:
                feature_stats[feature_value]['failed'] += 1
        
        report['by_feature'][feature] = dict(feature_stats)
    
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\nDetailed report saved to: {output_file}")


if __name__ == "__main__":
    main()
