"""Feature-by-feature failure analysis: diagnose test rejection patterns.

Analyzes:
  1. Feature breakdown: which features/components have high rejection/failure rates
  2. Test completion diagnostics: why the 9004 rejected tests failed to complete
  3. Timeout patterns: feature combinations prone to timeouts
  4. Performance correlations: game properties affecting completion rate
  5. Rejection categories: grouped by diagnostic reason

Usage:
    python feature_failure_analysis.py [--verbose]
"""

import argparse
import json
import os
from collections import defaultdict
from typing import Dict, Any, List, Tuple

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
RESULTS_DIR = os.path.join(REPO_ROOT, 'slurm_jobs', 'results')

DATASET_ALL = os.path.join(HERE, 'dataset_all.csv')
DATASET_RAW = os.path.join(HERE, 'dataset_raw.csv')

from parse_slurm_results import build_raw_dataset


def analyze_feature_combinations(raw_df: pd.DataFrame, verbose: bool = False) -> Dict[str, Any]:
    """Analyze success/failure rates by feature combinations."""
    results = {
        'total_jobs': len(raw_df),
        'completed_jobs': int(raw_df['parse_ok'].sum()),
        'rejected_jobs': int((~raw_df['parse_ok']).sum()),
        'completion_rate_pct': float(raw_df['parse_ok'].mean() * 100.0),
    }
    
    # Breakdown by diagnostic reason
    reason_breakdown = raw_df['diagnostic_reason'].value_counts().to_dict()
    results['rejection_by_reason'] = {
        str(k): {'count': int(v), 'pct': float(v / len(raw_df) * 100.0)}
        for k, v in sorted(reason_breakdown.items(), key=lambda x: -x[1])
    }
    
    # Extract variant components from successful jobs
    completed_df = raw_df[raw_df['parse_ok']].copy()
    if len(completed_df) == 0:
        results['variant_analysis'] = {'note': 'no completed jobs to analyze'}
        return results
    
    # Component-level analysis (from full raw dataset)
    variant_components = [
        'variant_select',
        'variant_simulation', 
        'variant_backprop',
        'variant_finalmove'
    ]
    
    component_analysis = {}
    for comp in variant_components:
        # Find all jobs mentioning each component value in the variant string
        comp_index = variant_components.index(comp)
        
        comp_values = defaultdict(lambda: {'total': 0, 'completed': 0, 'failures': 0})
        
        # Parse variant strings
        for idx, row in raw_df.iterrows():
            if pd.isna(row['variant']):
                continue
            variant_str = str(row['variant'])
            parts = [p.strip() for p in variant_str.split('|')]
            if len(parts) > comp_index:
                val = parts[comp_index].strip()
                if val:
                    comp_values[val]['total'] += 1
                    if row['parse_ok']:
                        comp_values[val]['completed'] += 1
                    else:
                        comp_values[val]['failures'] += 1
        
        component_analysis[comp] = {}
        for val, counts in sorted(comp_values.items()):
            total = counts['total']
            completed = counts['completed']
            fail_pct = float((1.0 - completed / total) * 100.0) if total > 0 else 0
            component_analysis[comp][val] = {
                'total_jobs': total,
                'completed': completed,
                'rejected': total - completed,
                'failure_rate_pct': fail_pct,
            }
    
    results['variant_analysis'] = component_analysis
    
    # Game property analysis: which games complete more frequently
    game_analysis = defaultdict(lambda: {'total': 0, 'completed': 0})
    for idx, row in raw_df.iterrows():
        if pd.notna(row['game']):
            game = str(row['game'])
            game_analysis[game]['total'] += 1
            if row['parse_ok']:
                game_analysis[game]['completed'] += 1
    
    # Sort by failure rate
    game_stats = []
    for game, counts in game_analysis.items():
        total = counts['total']
        completed = counts['completed']
        fail_pct = (1.0 - completed / total) * 100.0 if total > 0 else 0
        game_stats.append({
            'game': game,
            'total': total,
            'completed': completed,
            'rejected': total - completed,
            'failure_rate_pct': fail_pct,
        })
    
    # Sort by failure rate descending
    game_stats.sort(key=lambda x: -x['failure_rate_pct'])
    results['game_completion_by_game'] = game_stats
    
    # Timeout analysis
    timeout_stats = {
        'jobs_with_timeouts': int((raw_df['n_timeouts'] > 0).sum()),
        'total_timeout_events': int(raw_df['n_timeouts'].sum()),
        'avg_timeouts_per_job': float(raw_df['n_timeouts'].mean()),
        'max_timeouts_in_single_job': int(raw_df['n_timeouts'].max()),
    }
    
    # Group by timeout count
    timeout_by_count = defaultdict(int)
    for n in raw_df['n_timeouts']:
        timeout_by_count[int(n)] += 1
    timeout_stats['distribution'] = dict(timeout_by_count)
    
    results['timeout_analysis'] = timeout_stats
    
    # Failure analysis: reasons correlating with bad outcomes
    rejection_reasons = raw_df[~raw_df['parse_ok']]['diagnostic_reason'].value_counts()
    results['rejection_reasons_detail'] = {
        'missing_out_file': {
            'count': int(rejection_reasons.get('missing_out_file', 0)),
            'pct': float(rejection_reasons.get('missing_out_file', 0) / len(raw_df) * 100.0),
            'likely_cause': 'SLURM job did not generate output file',
        },
        'started_no_result_summary': {
            'count': int(rejection_reasons.get('started_no_result_summary', 0)),
            'pct': float(rejection_reasons.get('started_no_result_summary', 0) / len(raw_df) * 100.0),
            'likely_cause': 'Job started but did not complete (may still be running or out of time)',
        },
        'empty_out_file': {
            'count': int(rejection_reasons.get('empty_out_file', 0)),
            'pct': float(rejection_reasons.get('empty_out_file', 0) / len(raw_df) * 100.0),
            'likely_cause': 'Job produced no output (crash, no permission, etc)',
        },
        'missing_game_header': {
            'count': int(rejection_reasons.get('missing_game_header', 0)),
            'pct': float(rejection_reasons.get('missing_game_header', 0) / len(raw_df) * 100.0),
            'likely_cause': 'Output file corrupted or unusual format',
        },
        'missing_variant_header': {
            'count': int(rejection_reasons.get('missing_variant_header', 0)),
            'pct': float(rejection_reasons.get('missing_variant_header', 0) / len(raw_df) * 100.0),
            'likely_cause': 'Variant parsing failed',
        },
        'missing_wins_only': {
            'count': int(rejection_reasons.get('missing_wins_only', 0)),
            'pct': float(rejection_reasons.get('missing_wins_only', 0) / len(raw_df) * 100.0),
            'likely_cause': 'Wins data missing from result summary',
        },
        'missing_total_only': {
            'count': int(rejection_reasons.get('missing_total_only', 0)),
            'pct': float(rejection_reasons.get('missing_total_only', 0) / len(raw_df) * 100.0),
            'likely_cause': 'Total game count not in result summary',
        },
        'other_partial_parse': {
            'count': int(rejection_reasons.get('other_partial_parse', 0)),
            'pct': float(rejection_reasons.get('other_partial_parse', 0) / len(raw_df) * 100.0),
            'likely_cause': 'Unusual partial parse, check manually',
        },
    }
    
    return results


def analyze_accepted_vs_rejected(raw_df: pd.DataFrame, verbose: bool = False) -> Dict[str, Any]:
    """Compare characteristics of accepted vs rejected jobs."""
    accepted = raw_df[raw_df['parse_ok']]
    rejected = raw_df[~raw_df['parse_ok']]
    
    results = {
        'accepted_count': len(accepted),
        'rejected_count': len(rejected),
        'acceptance_rate_pct': float(len(accepted) / len(raw_df) * 100.0),
        'rejection_rate_pct': float(len(rejected) / len(raw_df) * 100.0),
    }
    
    # File existence patterns
    if 'out_exists' in raw_df.columns and 'err_exists' in raw_df.columns:
        results['file_patterns'] = {
            'accepted_with_both_files_pct': float((
                (accepted['out_exists'] & accepted['err_exists']).sum() / len(accepted) * 100.0
                if len(accepted) > 0 else 0
            )),
            'rejected_missing_out_file_pct': float((
                (~rejected['out_exists']).sum() / len(rejected) * 100.0
                if len(rejected) > 0 else 0
            )),
            'rejected_missing_err_file_pct': float((
                (~rejected['err_exists']).sum() / len(rejected) * 100.0
                if len(rejected) > 0 else 0
            )),
        }
    
    # Timeout patterns
    if len(accepted) > 0:
        results['timeout_patterns'] = {
            'accepted_mean_timeouts': float(accepted['n_timeouts'].mean()),
            'accepted_max_timeouts': int(accepted['n_timeouts'].max()),
            'accepted_pct_with_any_timeout': float((accepted['n_timeouts'] > 0).sum() / len(accepted) * 100.0),
        }
    
    if len(rejected) > 0:
        results['rejected_patterns'] = {
            'rejected_mean_timeouts': float(rejected['n_timeouts'].mean()),
            'rejected_max_timeouts': int(rejected['n_timeouts'].max()),
            'rejected_pct_with_any_timeout': float((rejected['n_timeouts'] > 0).sum() / len(rejected) * 100.0),
        }
    
    return results


def print_feature_failure_summary(analysis: Dict[str, Any]):
    """Pretty-print feature failure analysis."""
    print("=" * 80)
    print("FEATURE-BY-FEATURE FAILURE ANALYSIS")
    print("=" * 80)
    
    print(f"\nOVERALL TEST COMPLETION:")
    print(f"  Total jobs:         {analysis['total_jobs']}")
    print(f"  Completed:          {analysis['completed_jobs']}")
    print(f"  Rejected:           {analysis['rejected_jobs']} ({analysis['completion_rate_pct']:.1f}% completed)")
    
    print(f"\n{'-' * 80}")
    print("REJECTION BREAKDOWN BY DIAGNOSTIC REASON:")
    print(f"{'-' * 80}")
    for reason, info in analysis['rejection_by_reason'].items():
        print(f"  {reason:40s}: {info['count']:6d} ({info['pct']:5.1f}%)")
    
    print(f"\n{'-' * 80}")
    print("DETAILED FAILURE CAUSES:")
    print(f"{'-' * 80}")
    for reason, details in analysis['rejection_reasons_detail'].items():
        if details['count'] > 0:
            print(f"\n  {reason}:")
            print(f"    Count:        {details['count']} ({details['pct']:.1f}%)")
            print(f"    Cause:        {details['likely_cause']}")
    
    print(f"\n{'-' * 80}")
    print("VARIANT COMPONENT FAILURE RATES:")
    print(f"{'-' * 80}")
    
    for comp, values in analysis['variant_analysis'].items():
        if comp == 'note':
            print(f"  {values}")
            continue
        print(f"\n  {comp}:")
        for val, stats in sorted(values.items(), key=lambda x: -x[1]['failure_rate_pct']):
            print(f"    {val:30s}: {stats['failure_rate_pct']:5.1f}% fail "
                  f"({stats['rejected']:3d}/{stats['total_jobs']:3d})")
    
    print(f"\n{'-' * 80}")
    print("TOP 10 GAMES WITH HIGHEST FAILURE RATES:")
    print(f"{'-' * 80}")
    for i, game_stat in enumerate(analysis['game_completion_by_game'][:10], 1):
        print(f"  {i:2d}. {game_stat['game']:30s}: {game_stat['failure_rate_pct']:5.1f}% fail "
              f"({game_stat['rejected']:3d}/{game_stat['total']:3d})")
    
    print(f"\n{'-' * 80}")
    print("TIMEOUT ANALYSIS:")
    print(f"{'-' * 80}")
    timeout_analysis = analysis['timeout_analysis']
    print(f"  Jobs with any timeout:  {timeout_analysis['jobs_with_timeouts']}")
    print(f"  Total timeout events:   {timeout_analysis['total_timeout_events']}")
    print(f"  Avg timeouts/job:       {timeout_analysis['avg_timeouts_per_job']:.2f}")
    print(f"  Max timeouts in 1 job:  {timeout_analysis['max_timeouts_in_single_job']}")
    

def print_acceptance_summary(analysis: Dict[str, Any]):
    """Pretty-print acceptance vs rejection analysis."""
    print(f"\n{'=' * 80}")
    print("ACCEPTED VS REJECTED COMPARISON")
    print(f"{'=' * 80}")
    
    print(f"\n  Accepted:           {analysis['accepted_count']} ({analysis['acceptance_rate_pct']:.1f}%)")
    print(f"  Rejected:           {analysis['rejected_count']} ({analysis['rejection_rate_pct']:.1f}%)")
    
    if 'file_patterns' in analysis:
        print(f"\n  FILE PATTERNS:")
        for key, val in analysis['file_patterns'].items():
            print(f"    {key:40s}: {val:.1f}%")
    
    if 'timeout_patterns' in analysis:
        print(f"\n  ACCEPTED JOBS:")
        for key, val in analysis['timeout_patterns'].items():
            if isinstance(val, float):
                print(f"    {key:40s}: {val:.2f}")
            else:
                print(f"    {key:40s}: {val}")
    
    if 'rejected_patterns' in analysis:
        print(f"\n  REJECTED JOBS:")
        for key, val in analysis['rejected_patterns'].items():
            if isinstance(val, float):
                print(f"    {key:40s}: {val:.2f}")
            else:
                print(f"    {key:40s}: {val}")


def main():
    parser = argparse.ArgumentParser(
        description='Feature-by-feature failure and rejection analysis'
    )
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--output-json', help='Save analysis to JSON file')
    args = parser.parse_args()
    
    raw_df = build_raw_dataset(RESULTS_DIR)
    print(f"Loaded {len(raw_df)} job results")

    feature_analysis = analyze_feature_combinations(raw_df, args.verbose)
    acceptance_analysis = analyze_accepted_vs_rejected(raw_df, args.verbose)
    
    # Print summaries
    print_feature_failure_summary(feature_analysis)
    print_acceptance_summary(acceptance_analysis)
    
    # Save to JSON if requested
    if args.output_json:
        output = {
            'feature_analysis': feature_analysis,
            'acceptance_analysis': acceptance_analysis,
        }
        with open(args.output_json, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"\n\nAnalysis saved to {args.output_json}")


if __name__ == '__main__':
    main()
