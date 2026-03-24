"""Analyze whether dataset size is sufficient using learning curves.

This script estimates how validation error changes as training size grows.
It helps answer: "Do we still benefit from more tests?"

Outputs (written to --out-dir):
  - learning_curve_metrics.csv
  - learning_curve_summary.json
  - learning_curve_mse.png

Example:
  python analyze_data_sufficiency.py --dataset path/to/dataset_all.csv --out-dir path/to/out
"""

import argparse
import json
import os
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold, ShuffleSplit, learning_curve
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from train_winrate import build_feature_matrix

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATASET = os.path.join(HERE, 'dataset_all.csv')


def _build_models(random_state: int) -> Dict[str, Pipeline]:
    """Create a compact set of models for sufficiency analysis."""
    return {
        'DummyMean': Pipeline([
            ('imputer', SimpleImputer(strategy='constant', fill_value=0.0)),
            ('model', DummyRegressor(strategy='mean')),
        ]),
        'Ridge': Pipeline([
            ('imputer', SimpleImputer(strategy='constant', fill_value=0.0)),
            ('scaler', StandardScaler()),
            ('model', Ridge(alpha=10.0)),
        ]),
        'RandomForest': Pipeline([
            ('imputer', SimpleImputer(strategy='constant', fill_value=0.0)),
            ('model', RandomForestRegressor(
                n_estimators=200,
                max_depth=None,
                min_samples_leaf=1,
                max_features=0.5,
                n_jobs=1,
                random_state=random_state,
            )),
        ]),
        'HistGradientBoosting': Pipeline([
            ('model', HistGradientBoostingRegressor(
                max_iter=200,
                learning_rate=0.05,
                max_depth=5,
                l2_regularization=1.0,
                random_state=random_state,
            )),
        ]),
    }


def _build_groups_from_game_features(df: pd.DataFrame) -> Optional[np.ndarray]:
    """Build groups from game_* feature signatures to reduce leakage risk.

    If no game_* columns exist, returns None.
    """
    game_cols = sorted(c for c in df.columns if c.startswith('game_'))
    if not game_cols:
        return None

    gdf = df[game_cols].copy()
    for c in game_cols:
        gdf[c] = gdf[c].astype(str)
    signatures = gdf.apply(lambda row: '|'.join(row.values.tolist()), axis=1)
    return signatures.values


def _learning_curve_for_model(
    name: str,
    estimator: Pipeline,
    X: np.ndarray,
    y: np.ndarray,
    train_sizes: np.ndarray,
    cv,
    groups: Optional[np.ndarray],
) -> pd.DataFrame:
    """Compute learning-curve metrics for one model."""
    # MSE (returned as negative by sklearn scoring)
    sizes_abs, train_mse_neg, val_mse_neg = learning_curve(
        estimator=estimator,
        X=X,
        y=y,
        groups=groups,
        train_sizes=train_sizes,
        cv=cv,
        scoring='neg_mean_squared_error',
        n_jobs=-1,
        shuffle=True,
        random_state=42,
    )

    # R^2
    _, _, val_r2 = learning_curve(
        estimator=estimator,
        X=X,
        y=y,
        groups=groups,
        train_sizes=train_sizes,
        cv=cv,
        scoring='r2',
        n_jobs=-1,
        shuffle=True,
        random_state=42,
    )

    train_mse = -train_mse_neg
    val_mse = -val_mse_neg

    rows: List[Dict[str, float]] = []
    for i, n in enumerate(sizes_abs):
        rows.append({
            'model': name,
            'train_size_abs': int(n),
            'train_size_frac': float(n) / float(X.shape[0]),
            'train_mse_mean': float(train_mse[i].mean()),
            'train_mse_std': float(train_mse[i].std()),
            'val_mse_mean': float(val_mse[i].mean()),
            'val_mse_std': float(val_mse[i].std()),
            'val_r2_mean': float(val_r2[i].mean()),
            'val_r2_std': float(val_r2[i].std()),
        })

    return pd.DataFrame(rows)


def _improvement_pct(start: float, end: float) -> float:
    if start <= 0:
        return 0.0
    return (start - end) / start * 100.0


def _summarize_sufficiency(metrics_df: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    """Summarize whether each model appears data-limited."""
    summary: Dict[str, Dict[str, float]] = {}

    for model in sorted(metrics_df['model'].unique()):
        mdf = metrics_df[metrics_df['model'] == model].sort_values('train_size_abs')
        first = float(mdf.iloc[0]['val_mse_mean'])
        last = float(mdf.iloc[-1]['val_mse_mean'])
        gain_total = _improvement_pct(first, last)

        if len(mdf) >= 3:
            prev = float(mdf.iloc[-3]['val_mse_mean'])
        else:
            prev = first
        gain_recent = _improvement_pct(prev, last)

        trend_down = last < prev
        likely_data_limited = bool(gain_recent > 2.0 and trend_down)

        summary[model] = {
            'val_mse_first': first,
            'val_mse_last': last,
            'val_mse_gain_total_pct': gain_total,
            'val_mse_gain_recent_pct': gain_recent,
            'val_r2_last': float(mdf.iloc[-1]['val_r2_mean']),
            'likely_data_limited': likely_data_limited,
        }

    return summary


def _plot_learning_curves(metrics_df: pd.DataFrame, out_path: str) -> None:
    """Plot validation MSE learning curves for all models."""
    fig, ax = plt.subplots(1, 1, figsize=(9, 6))

    for model in sorted(metrics_df['model'].unique()):
        mdf = metrics_df[metrics_df['model'] == model].sort_values('train_size_abs')
        x = mdf['train_size_abs'].values
        y = mdf['val_mse_mean'].values
        e = mdf['val_mse_std'].values
        ax.plot(x, y, marker='o', linewidth=1.8, label=model)
        ax.fill_between(x, y - e, y + e, alpha=0.15)

    ax.set_title('Learning Curve (Validation MSE vs Training Size)')
    ax.set_xlabel('Training samples used')
    ax.set_ylabel('Validation MSE (lower is better)')
    ax.grid(True, alpha=0.25)
    ax.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=170)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description='Analyze dataset sufficiency with learning curves')
    parser.add_argument('--dataset', default=DEFAULT_DATASET, help='Path to dataset CSV (default: dataset_all.csv)')
    parser.add_argument('--out-dir', default=None, help='Directory for output artefacts')
    parser.add_argument('--n-splits', type=int, default=5, help='CV splits for ShuffleSplit (default: 5)')
    parser.add_argument('--test-size', type=float, default=0.2, help='Validation fraction per split (default: 0.2)')
    parser.add_argument('--random-state', type=int, default=42, help='Random seed')
    parser.add_argument(
        '--train-fracs',
        default='0.1,0.2,0.4,0.6,0.8,1.0',
        help='Comma-separated training fractions, e.g. 0.1,0.2,0.4,0.6,0.8,1.0',
    )
    parser.add_argument(
        '--group-by-game-features',
        action='store_true',
        help='Use GroupKFold by game_* feature signature to reduce game leakage across folds',
    )
    args = parser.parse_args()

    dataset_path = os.path.abspath(args.dataset)
    if not os.path.isfile(dataset_path):
        raise SystemExit(f'Dataset not found: {dataset_path}')

    out_dir = os.path.abspath(args.out_dir) if args.out_dir else HERE
    os.makedirs(out_dir, exist_ok=True)

    fracs = np.array([float(x.strip()) for x in args.train_fracs.split(',') if x.strip()], dtype=float)
    fracs = np.clip(fracs, 0.05, 1.0)
    fracs = np.unique(fracs)

    print(f'Loading dataset: {dataset_path}')
    df = pd.read_csv(dataset_path)
    print(f'Dataset rows: {len(df)}')

    X, targets, _, _ = build_feature_matrix(df)
    y = targets['score']
    n = X.shape[0]
    print(f'Usable rows (non-null score): {n}')

    if n < 100:
        raise SystemExit('Not enough usable rows for a stable learning-curve analysis (need at least 100).')

    if args.group_by_game_features:
        groups = _build_groups_from_game_features(df.dropna(subset=['score']).copy())
        if groups is None:
            print('No game_* columns found; falling back to ShuffleSplit CV.')
            cv = ShuffleSplit(n_splits=args.n_splits, test_size=args.test_size, random_state=args.random_state)
            groups = None
            cv_mode = 'ShuffleSplit'
        else:
            # Use up to 5 folds while respecting number of unique groups.
            n_groups = len(np.unique(groups))
            n_splits = max(2, min(5, n_groups))
            cv = GroupKFold(n_splits=n_splits)
            cv_mode = f'GroupKFold(n_splits={n_splits})'
    else:
        groups = None
        cv = ShuffleSplit(n_splits=args.n_splits, test_size=args.test_size, random_state=args.random_state)
        cv_mode = f'ShuffleSplit(n_splits={args.n_splits}, test_size={args.test_size})'

    print(f'CV mode: {cv_mode}')
    print(f'Train fractions: {fracs.tolist()}')

    models = _build_models(args.random_state)
    all_rows: List[pd.DataFrame] = []

    for name, estimator in models.items():
        print(f'Running learning curve for: {name}')
        mdf = _learning_curve_for_model(
            name=name,
            estimator=estimator,
            X=X,
            y=y,
            train_sizes=fracs,
            cv=cv,
            groups=groups,
        )
        all_rows.append(mdf)

    metrics_df = pd.concat(all_rows, ignore_index=True)
    summary = _summarize_sufficiency(metrics_df)

    metrics_csv = os.path.join(out_dir, 'learning_curve_metrics.csv')
    summary_json = os.path.join(out_dir, 'learning_curve_summary.json')
    plot_png = os.path.join(out_dir, 'learning_curve_mse.png')

    metrics_df.to_csv(metrics_csv, index=False)
    with open(summary_json, 'w', encoding='utf-8') as fh:
        json.dump(
            {
                'dataset': dataset_path,
                'n_rows': int(n),
                'cv_mode': cv_mode,
                'train_fracs': [float(x) for x in fracs.tolist()],
                'models': summary,
                'interpretation': {
                    'likely_data_limited_rule': (
                        'A model is flagged likely_data_limited when validation MSE '
                        'improves by >2% from the third-last to last train-size point.'
                    )
                },
            },
            fh,
            indent=2,
        )

    _plot_learning_curves(metrics_df, plot_png)

    print('\nSaved:')
    print(f'  {metrics_csv}')
    print(f'  {summary_json}')
    print(f'  {plot_png}')

    print('\nQuick summary:')
    for model, info in summary.items():
        tag = 'data-limited' if info['likely_data_limited'] else 'near-plateau'
        print(
            f"  {model:<20} val_mse={info['val_mse_last']:.5f} "
            f"recent_gain={info['val_mse_gain_recent_pct']:.2f}%  {tag}"
        )


if __name__ == '__main__':
    main()
