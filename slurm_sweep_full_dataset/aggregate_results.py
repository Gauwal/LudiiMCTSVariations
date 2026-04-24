#!/usr/bin/env python3
"""
Aggregate Results from Multiple Seeds

Loads all JSON results from multiple runs (different seeds) and produces:
  - Mean and std curves for baseline and each warm-start weight
  - Combined plots with error bands
  - Summary statistics JSON

Usage:
    python aggregate_results.py --results-dir ./results_20260424_130000
"""

import os
import json
import argparse
from pathlib import Path
from collections import defaultdict

import numpy as np
import matplotlib.pyplot as plt


def load_all_results(results_dir):
    """Load all sweep_full_dataset_*.json files from a directory."""
    results_dir = Path(results_dir)
    all_files = list(results_dir.glob('*/sweep_full_dataset_*.json'))
    
    if not all_files:
        # Also check current directory
        all_files = list(results_dir.glob('sweep_full_dataset_*.json'))
    
    if not all_files:
        raise FileNotFoundError(f'No JSON files found in {results_dir}')
    
    print(f'Found {len(all_files)} result files')
    
    results = []
    for json_file in sorted(all_files):
        with open(json_file) as f:
            data = json.load(f)
            results.append(data)
            print(f'  Loaded: {json_file.name} (seed={data["meta"]["seed"]})')
    
    return results


def aggregate_curves(results, metric='regret'):
    """
    Aggregate curves across seeds.
    
    Returns:
        {
            'baseline': {'mean': [...], 'std': [...], 'curves': [...]},
            '5': {'mean': [...], 'std': [...], 'curves': [...]},
            ...
        }
    """
    aggregated = defaultdict(list)
    
    for result in results:
        baseline = result['baseline'][metric]
        aggregated['baseline'].append(baseline)
        
        for w_str in sorted(result['warm'].keys()):
            warm_curve = result['warm'][w_str][metric]
            aggregated[w_str].append(warm_curve)
    
    # Compute mean and std, padding to same length
    aggregated_stats = {}
    for key, curves in aggregated.items():
        # Pad all curves to the same length (max length)
        max_len = max(len(c) for c in curves)
        padded = []
        for curve in curves:
            if len(curve) < max_len:
                # Pad with last value
                padded_curve = list(curve) + [curve[-1]] * (max_len - len(curve))
            else:
                padded_curve = list(curve)
            padded.append(padded_curve)
        
        mean_curve = np.mean(padded, axis=0).tolist()
        std_curve = np.std(padded, axis=0).tolist()
        
        aggregated_stats[key] = {
            'mean': mean_curve,
            'std': std_curve,
            'num_seeds': len(curves),
            'curves': padded
        }
    
    return aggregated_stats


def plot_with_error_bands(aggregated_stats, metric, batch_size, output_path):
    """Plot curves with error bands (mean ± std)."""
    weights = sorted([k for k in aggregated_stats.keys() if k != 'baseline'])
    
    fig, ax = plt.subplots(figsize=(12, 7))
    
    # Baseline
    baseline_data = aggregated_stats['baseline']
    x = [(i+1) * batch_size for i in range(len(baseline_data['mean']))]
    ax.plot(x, baseline_data['mean'], label='Baseline', color='black', linestyle='--', linewidth=2.5)
    ax.fill_between(x, 
                     np.array(baseline_data['mean']) - np.array(baseline_data['std']),
                     np.array(baseline_data['mean']) + np.array(baseline_data['std']),
                     color='gray', alpha=0.2)
    
    # Warm-start variants
    colors = plt.cm.tab10(np.linspace(0, 1, len(weights)))
    for idx, w in enumerate(weights):
        w_data = aggregated_stats[w]
        x_w = [(i+1) * batch_size for i in range(len(w_data['mean']))]
        ax.plot(x_w, w_data['mean'], label=f'Warm w={w}', color=colors[idx], linewidth=2)
        ax.fill_between(x_w,
                        np.array(w_data['mean']) - np.array(w_data['std']),
                        np.array(w_data['mean']) + np.array(w_data['std']),
                        color=colors[idx], alpha=0.15)
    
    ax.set_xlabel('Number of Pulls', fontsize=12)
    ax.set_ylabel('Simple Regret' if metric == 'regret' else 'Accuracy per Game', fontsize=12)
    title = 'Warm-Start RCP: Aggregated Results (Full Dataset)' + \
            (' - Simple Regret' if metric == 'regret' else ' - Accuracy')
    ax.set_title(title, fontsize=13)
    ax.legend(loc='best', fontsize=10)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f'Saved: {output_path}')


def save_summary(aggregated_stats, predictor_stats, output_path):
    """Save aggregated results as JSON."""
    summary = {
        'baseline': {k: v for k, v in aggregated_stats['baseline'].items() if k != 'curves'},
        'warm': {w: {k: v for k, v in aggregated_stats[w].items() if k != 'curves'} 
                 for w in aggregated_stats if w != 'baseline'},
        'predictor': predictor_stats
    }
    
    with open(output_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f'Saved summary: {output_path}')


def main():
    parser = argparse.ArgumentParser(description='Aggregate results from multiple seeds')
    parser.add_argument('--results-dir', type=str, default='.',
                        help='Directory containing result folders or JSON files')
    parser.add_argument('--output-dir', type=str, default=None,
                        help='Output directory for aggregated plots (default: same as results-dir)')
    parser.add_argument('--batch-size', type=int, default=20,
                        help='Batch size (for x-axis scaling)')
    
    args = parser.parse_args()
    
    results_dir = Path(args.results_dir)
    if args.output_dir is None:
        output_dir = results_dir
    else:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f'Loading results from: {results_dir}')
    
    # Load all results
    results = load_all_results(results_dir)
    
    # Aggregate metrics
    print('\nAggregating metrics...')
    agg_regret = aggregate_curves(results, 'regret')
    agg_ape = aggregate_curves(results, 'ape')
    
    # Get predictor stats (same across all runs)
    predictor_stats = results[0]['predictor'] if results else {'regret': None, 'ape': None}
    print(f'Predictor: regret={predictor_stats.get("regret")}, ape={predictor_stats.get("ape")}')
    
    # Generate plots
    print('\nGenerating plots...')
    plot_with_error_bands(agg_regret, 'regret', args.batch_size, 
                         output_dir / 'aggregated_regret.png')
    plot_with_error_bands(agg_ape, 'ape', args.batch_size,
                         output_dir / 'aggregated_ape.png')
    
    # Save summary
    print('\nSaving summary...')
    save_summary(agg_regret, predictor_stats, output_dir / 'aggregated_summary.json')
    
    # Print summary stats
    print('\n' + '='*70)
    print('SUMMARY STATISTICS')
    print('='*70)
    print(f'\nBaseline (final regret): {agg_regret["baseline"]["mean"][-1]:.6f} ± {agg_regret["baseline"]["std"][-1]:.6f}')
    print(f'Baseline (final APE): {agg_ape["baseline"]["mean"][-1]:.4f} ± {agg_ape["baseline"]["std"][-1]:.4f}')
    
    for w in sorted([k for k in agg_regret.keys() if k != 'baseline']):
        r_final = agg_regret[w]['mean'][-1]
        r_std = agg_regret[w]['std'][-1]
        a_final = agg_ape[w]['mean'][-1]
        a_std = agg_ape[w]['std'][-1]
        print(f'\nWarm w={w}:')
        print(f'  Final regret: {r_final:.6f} ± {r_std:.6f}')
        print(f'  Final APE: {a_final:.4f} ± {a_std:.4f}')
    
    if predictor_stats.get('regret') is not None:
        print(f'\nPredictor (single):')
        print(f'  Regret: {predictor_stats["regret"]:.6f}')
        print(f'  APE: {predictor_stats["ape"]:.4f}')
    
    print('\n' + '='*70)
    print(f'Results saved to: {output_dir}')


if __name__ == '__main__':
    main()
