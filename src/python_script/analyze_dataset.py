"""Comprehensive dataset analysis: descriptive statistics, distributions, and correlations.

Usage:
    python analyze_dataset.py [--dataset DATASET_PATH] [--label all|notimeout]

Provides:
  - Row counts and basic stats
  - Win/draw/loss distribution
  - Winrate and drawrate statistics
  - Timeout analysis
  - Variant component value counts
  - Game-level statistics
  - Correlations with moveTime
  - Feature missing-value analysis
"""

import argparse
import json
import os
from typing import Dict, Any

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from parse_slurm_results import build_raw_dataset

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))

DATASET_ALL = os.path.join(HERE, 'dataset_all.csv')
DATASET_NOTIMEOUT = os.path.join(HERE, 'dataset_notimeout.csv')
DATASET_RAW = os.path.join(HERE, 'dataset_raw.csv')


def plot_winrate_distributions(df: pd.DataFrame, label: str, top_n: int = 12) -> Dict[str, str]:
    """Create winrate distribution plots for methods present in successful rows.

    Returns dict of generated plot paths.
    """
    outputs: Dict[str, str] = {}

    if 'winrate' not in df.columns:
        return outputs

    # Keep only rows with a valid winrate.
    d = df[df['winrate'].notna()].copy()
    if d.empty:
        return outputs

    # Overall distribution histogram.
    overall_path = os.path.join(HERE, f'winrate_distribution_overall_{label}.png')
    fig, ax = plt.subplots(1, 1, figsize=(10, 6))
    ax.hist(d['winrate'].values, bins=20, alpha=0.8, edgecolor='black')
    ax.set_title(f'Winrate Distribution [{label}]')
    ax.set_xlabel('Winrate')
    ax.set_ylabel('Count')
    ax.grid(True, alpha=0.25)
    plt.tight_layout()
    plt.savefig(overall_path, dpi=180)
    plt.close(fig)
    outputs['overall'] = overall_path

    # Method-wise distributions by variant components.
    method_cols = [
        ('variant_select', 'Selection method'),
        ('variant_simulation', 'Simulation method'),
        ('variant_backprop', 'Backprop method'),
        ('variant_finalmove', 'Final-move method'),
    ]

    existing = [(c, t) for c, t in method_cols if c in d.columns]
    if not existing:
        return outputs

    rows = 2
    cols = 2
    fig, axes = plt.subplots(rows, cols, figsize=(16, 11))
    axes = axes.flatten()

    for i, (col, title) in enumerate(existing):
        ax = axes[i]
        counts = d[col].value_counts()
        top_values = counts.head(top_n).index.tolist()
        sub = d[d[col].isin(top_values)].copy()

        # Order categories by median winrate (descending) for readability.
        med = sub.groupby(col)['winrate'].median().sort_values(ascending=False)
        order = med.index.tolist()

        data = [sub.loc[sub[col] == method, 'winrate'].values for method in order]
        labels = [f"{m} (n={len(sub[sub[col] == m])})" for m in order]

        if data:
            ax.boxplot(data, tick_labels=labels, vert=False, showfliers=True)
        ax.set_title(f'{title} (top {min(top_n, len(top_values))} by count)')
        ax.set_xlabel('Winrate')
        ax.grid(True, alpha=0.25, axis='x')

    for j in range(len(existing), rows * cols):
        axes[j].axis('off')

    plt.tight_layout()
    methods_path = os.path.join(HERE, f'winrate_distribution_by_method_{label}.png')
    plt.savefig(methods_path, dpi=180)
    plt.close(fig)
    outputs['by_method'] = methods_path

    return outputs


def analyze_dataset(df: pd.DataFrame, label: str = 'all') -> Dict[str, Any]:
    """Analyze a dataset and return a comprehensive stats dict."""
    stats = {
        'label': label,
        'basics': {
            'n_rows': len(df),
            'n_samples_with_timeout': int((df['n_timeouts'] > 0).sum()) if 'n_timeouts' in df.columns else None,
            'total_timeouts': int(df['n_timeouts'].sum()) if 'n_timeouts' in df.columns else None,
        },
    }

    if 'parse_ok' in df.columns:
        parsed_mask = df['parse_ok'].fillna(False).astype(bool)
        stats['raw_job_diagnostics'] = {
            'complete_jobs': int(parsed_mask.sum()),
            'incomplete_jobs': int((~parsed_mask).sum()),
            'complete_pct': float(parsed_mask.mean() * 100.0),
            'incomplete_pct': float((~parsed_mask).mean() * 100.0),
        }

        if 'diagnostic_reason' in df.columns:
            reason_counts = df['diagnostic_reason'].fillna('unknown').value_counts().to_dict()
            stats['raw_job_diagnostics']['reason_counts'] = {
                str(k): int(v) for k, v in reason_counts.items()
            }

        flag_cols = ['has_game', 'has_variant', 'has_wins', 'has_total', 'out_exists', 'err_exists']
        present_flag_cols = [c for c in flag_cols if c in df.columns]
        if present_flag_cols:
            stats['raw_job_diagnostics']['flag_counts'] = {
                col: int(df[col].fillna(False).astype(bool).sum()) for col in present_flag_cols
            }

        if 'err_size_bytes' in df.columns:
            nonempty_err = (df['err_size_bytes'].fillna(0) > 0)
            stats['raw_job_diagnostics']['jobs_with_nonempty_err'] = int(nonempty_err.sum())

    # --- Win/Draw/Loss analysis ---
    if 'winrate' in df.columns and 'drawrate' in df.columns:
        stats['winrate_drawrate'] = {
            'winrate_mean': float(df['winrate'].mean()),
            'winrate_std': float(df['winrate'].std()),
            'winrate_min': float(df['winrate'].min()),
            'winrate_max': float(df['winrate'].max()),
            'winrate_median': float(df['winrate'].median()),
            'winrate_q25': float(df['winrate'].quantile(0.25)),
            'winrate_q75': float(df['winrate'].quantile(0.75)),
            'drawrate_mean': float(df['drawrate'].mean()),
            'drawrate_std': float(df['drawrate'].std()),
            'drawrate_min': float(df['drawrate'].min()),
            'drawrate_max': float(df['drawrate'].max()),
            'drawrate_median': float(df['drawrate'].median()),
            'drawrate_q25': float(df['drawrate'].quantile(0.25)),
            'drawrate_q75': float(df['drawrate'].quantile(0.75)),
        }

    if 'score' in df.columns:
        stats['score'] = {
            'mean': float(df['score'].mean()),
            'std': float(df['score'].std()),
            'min': float(df['score'].min()),
            'max': float(df['score'].max()),
            'median': float(df['score'].median()),
            'q25': float(df['score'].quantile(0.25)),
            'q75': float(df['score'].quantile(0.75)),
        }

    # --- Variant component value counts ---
    comp_cols = [
        'variant_select',
        'variant_simulation',
        'variant_backprop',
        'variant_finalmove',
    ]
    stats['variant_components'] = {}
    for comp in comp_cols:
        if comp in df.columns:
            vc = df[comp].value_counts().to_dict()
            stats['variant_components'][comp] = {str(k): int(v) for k, v in vc.items()}

    # --- Game analysis ---
    if 'game_numPlayers' in df.columns:
        game_cols = [c for c in df.columns if c.startswith('game_')]
        stats['game_features'] = {
            'n_game_feature_cols': len(game_cols),
            'game_feature_cols': game_cols,
        }

    # --- moveTime analysis ---
    if 'moveTime' in df.columns:
        stats['moveTime'] = {
            'mean': float(df['moveTime'].mean()),
            'std': float(df['moveTime'].std()),
            'min': float(df['moveTime'].min()),
            'max': float(df['moveTime'].max()),
            'median': float(df['moveTime'].median()),
            'unique_values': sorted([float(v) for v in df['moveTime'].unique().tolist()]),
        }
        # Correlation with winrate
        if 'winrate' in df.columns:
            corr = df[['moveTime', 'winrate']].corr().iloc[0, 1]
            stats['moveTime']['correlation_with_winrate'] = float(corr)

    # --- missingness ---
    null_counts = df.isnull().sum()
    if null_counts.sum() > 0:
        stats['missing_data'] = {
            col: int(count) 
            for col, count in null_counts[null_counts > 0].items()
        }
    else:
        stats['missing_data'] = {}

    return stats


def main():
    parser = argparse.ArgumentParser(description='Analyze MCTS training datasets')
    parser.add_argument(
        '--dataset',
        help='Path to a specific dataset CSV',
    )
    parser.add_argument(
        '--label',
        choices=['all', 'notimeout'],
        default='all',
        help='Which dataset to analyze',
    )
    parser.add_argument(
        '--results-dir',
        help='If set, re-parse this SLURM results dir and save raw dataset_raw.csv before analysis',
    )
    parser.add_argument(
        '--raw-only',
        action='store_true',
        help='When used with --results-dir, analyze the freshly-built raw dataset_raw.csv',
    )
    parser.add_argument(
        '--plot-top-n',
        type=int,
        default=12,
        help='Number of methods per component to include in method-wise winrate plots (default 12)',
    )
    args = parser.parse_args()

    if args.results_dir:
        results_dir = os.path.abspath(args.results_dir)
        if not os.path.isdir(results_dir):
            raise SystemExit(f"Results directory not found: {results_dir}")
        df_raw = build_raw_dataset(results_dir)
        df_raw.to_csv(DATASET_RAW, index=False)
        print(f"Raw dataset saved to: {DATASET_RAW} ({len(df_raw)} rows)")

    if args.dataset:
        dataset_path = args.dataset
    elif args.raw_only:
        dataset_path = DATASET_RAW
    else:
        if args.label == 'all':
            dataset_path = DATASET_ALL
        else:
            dataset_path = DATASET_NOTIMEOUT

    dataset_path = os.path.abspath(dataset_path)

    if not os.path.isfile(dataset_path):
        raise SystemExit(f"Dataset not found: {dataset_path}")

    print(f"Loading dataset: {dataset_path}")
    df = pd.read_csv(dataset_path)

    print(f"Dataset shape: {df.shape[0]} rows × {df.shape[1]} columns")
    print()

    stats = analyze_dataset(df, label=args.label)

    # Pretty-print stats
    print(f"{'=' * 70}")
    print(f"  DATASET ANALYSIS  [{args.label}]")
    print(f"{'=' * 70}\n")

    print(f"Basics:")
    print(f"  Rows: {stats['basics']['n_rows']}")
    if stats['basics']['n_samples_with_timeout'] is not None:
        print(f"  Samples with timeout: {stats['basics']['n_samples_with_timeout']}")
        print(f"  Total timeout games: {stats['basics']['total_timeouts']}")

    if 'raw_job_diagnostics' in stats:
        raw = stats['raw_job_diagnostics']
        print(f"\nRaw job diagnostics:")
        print(f"  Complete jobs: {raw['complete_jobs']} ({raw['complete_pct']:.1f}%)")
        print(f"  Incomplete jobs: {raw['incomplete_jobs']} ({raw['incomplete_pct']:.1f}%)")
        if 'jobs_with_nonempty_err' in raw:
            print(f"  Jobs with non-empty .err: {raw['jobs_with_nonempty_err']}")
        if 'reason_counts' in raw:
            print(f"  Reasons:")
            for reason, count in raw['reason_counts'].items():
                pct = 100.0 * count / len(df) if len(df) else 0.0
                print(f"    {reason:<28} {count:>5} ({pct:>5.1f}%)")

    if 'winrate_drawrate' in stats:
        wd = stats['winrate_drawrate']
        print(f"\nWinrate distribution:")
        print(f"  Mean: {wd['winrate_mean']:.4f}  Std: {wd['winrate_std']:.4f}")
        print(f"  Min: {wd['winrate_min']:.4f}  Median: {wd['winrate_median']:.4f}  Max: {wd['winrate_max']:.4f}")
        print(f"  Q25-Q75: {wd['winrate_q25']:.4f} - {wd['winrate_q75']:.4f}")

        print(f"\nDrawrate distribution:")
        print(f"  Mean: {wd['drawrate_mean']:.4f}  Std: {wd['drawrate_std']:.4f}")
        print(f"  Min: {wd['drawrate_min']:.4f}  Median: {wd['drawrate_median']:.4f}  Max: {wd['drawrate_max']:.4f}")
        print(f"  Q25-Q75: {wd['drawrate_q25']:.4f} - {wd['drawrate_q75']:.4f}")

    if 'score' in stats:
        s = stats['score']
        print(f"\nScore distribution:")
        print(f"  Mean: {s['mean']:.4f}  Std: {s['std']:.4f}")
        print(f"  Min: {s['min']:.4f}  Median: {s['median']:.4f}  Max: {s['max']:.4f}")
        print(f"  Q25-Q75: {s['q25']:.4f} - {s['q75']:.4f}")

    if 'variant_components' in stats:
        print(f"\nVariant component value counts:")
        for comp, counts in stats['variant_components'].items():
            print(f"  {comp}: {len(counts)} unique values")
            for val, cnt in sorted(counts.items(), key=lambda x: -x[1])[:5]:
                print(f"    {val:<30} {cnt:>5}")

    if 'moveTime' in stats:
        mt = stats['moveTime']
        print(f"\nmoveTime distribution:")
        print(f"  Mean: {mt['mean']:.4f}  Std: {mt['std']:.4f}")
        print(f"  Min: {mt['min']:.4f}  Median: {mt['median']:.4f}  Max: {mt['max']:.4f}")
        print(f"  Unique values: {sorted(mt['unique_values'])}")
        if 'correlation_with_winrate' in mt:
            print(f"  Correlation with winrate: {mt['correlation_with_winrate']:.4f}")

    if stats['missing_data']:
        print(f"\nMissing data:")
        for col, count in stats['missing_data'].items():
            pct = 100 * count / len(df)
            print(f"  {col}: {count} ({pct:.1f}%)")
    else:
        print(f"\nMissing data: None")

    print(f"\n{'=' * 70}\n")

    # Plot winrate distributions for functioning methods (datasets with winrate).
    plot_outputs = plot_winrate_distributions(df, args.label, top_n=max(1, args.plot_top_n))
    if plot_outputs:
        print("Saved winrate distribution plots:")
        for key, path in plot_outputs.items():
            print(f"  {key}: {path}")
        print()

    # Save JSON report
    report_path = os.path.join(HERE, f'dataset_analysis_{args.label}.json')
    with open(report_path, 'w', encoding='utf-8') as fh:
        json.dump(stats, fh, indent=2)
    print(f"Analysis saved to: {report_path}")


if __name__ == '__main__':
    main()
