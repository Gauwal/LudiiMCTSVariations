"""Multi-model training script for MCTS variant performance prediction.

Trains and tunes regression models on two datasets ('all' and 'notimeout').

Model groups
------------
**Single-target (score)** — KernelRidge, Ridge, HistGradientBoosting, RandomForest
  Predict ``score = (wins + 0.5 * draws) / effective_total`` directly.

**Multi-output (winrate + drawrate)** — Ridge_MO, HistGradientBoosting_MO,
  RandomForest_MO
  Predict ``winrate`` and ``drawrate`` simultaneously.  A derived score
  ``predicted_winrate + 0.5 * predicted_drawrate`` is used for comparison
  with the single-target models.

The best model across all groups (by lowest test-set MSE on the score target)
is saved as the primary model for inference.

Key design decisions
--------------------
* META columns (moveTime, maxMoves) excluded: constant across the dataset.
* NaN in game features preserved for HistGBM native handling; other pipelines
  use SimpleImputer.
* KernelRidge param grid uses two sub-grids (rbf / polynomial).
* Matplotlib Agg backend for headless environments.

Output artefacts per label {'all', 'notimeout'}:
  best_model_{label}.joblib                  best pipeline (single or multi-output)
  best_model_info_{label}.json               which model won + all metrics
  features_{label}.json                      feature names
  variant_catalogue_{label}.json             valid variant-component values
  plot_scatter_{model_name}_{label}.png      true-vs-predicted scatter per model
  plot_comparison_{label}.png                bar chart comparing all models
"""

import json
import os
from typing import Dict, List, Tuple

import matplotlib
matplotlib.use('Agg')  # non-interactive backend for headless environments
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.kernel_ridge import KernelRidge
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.multioutput import MultiOutputRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from parse_slurm_results import (
    build_datasets,
    RESULTS_DIR,
    GAME_PROPS,
    DATASET_ALL_OUT,
    DATASET_NOTIMEOUT_OUT,
)

HERE = os.path.dirname(os.path.abspath(__file__))

VARIANT_COMP_COLS = [
    'variant_select',
    'variant_simulation',
    'variant_backprop',
    'variant_finalmove',
]


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _model_out_path(label: str) -> str:
    """Return the path for the best-model pipeline joblib file."""
    return os.path.join(HERE, f'best_model_{label}.joblib')


def _info_out_path(label: str) -> str:
    """Return the path for the JSON file that records the best model and all models' metrics."""
    return os.path.join(HERE, f'best_model_info_{label}.json')


def _features_out_path(label: str) -> str:
    """Return the path for the JSON file listing the feature names used at training time."""
    return os.path.join(HERE, f'features_{label}.json')


def _catalogue_out_path(label: str) -> str:
    """Return the path for the JSON file listing the valid values per variant component."""
    return os.path.join(HERE, f'variant_catalogue_{label}.json')


def _scatter_out_path(label: str, model_name: str) -> str:
    """Return the path for the true-vs-predicted scatter plot of one model."""
    return os.path.join(HERE, f'plot_scatter_{model_name}_{label}.png')


def _comparison_out_path(label: str) -> str:
    """Return the path for the model-comparison bar chart."""
    return os.path.join(HERE, f'plot_comparison_{label}.png')


# ---------------------------------------------------------------------------
# Feature matrix builder
# ---------------------------------------------------------------------------

def build_feature_matrix(
    df: pd.DataFrame,
) -> Tuple[np.ndarray, Dict[str, np.ndarray], List[str], Dict[str, List[str]]]:
    """Build (X, targets, feature_names, variant_catalogue) from a dataset DataFrame.

    Game property columns (starting with 'game_') are used as numeric features.
    NaN values are *preserved* so that different pipeline steps can handle them
    appropriately (imputer for KRR / Ridge / RF; native handling for HGB).

    Variant component columns are one-hot encoded into binary indicator features.

    META columns (moveTime, maxMoves) are excluded (constant across dataset).

    Returns
    -------
    X                : (n_samples, n_features) float array, NaN where data is missing
    targets          : dict with keys 'score', 'winrate', 'drawrate' each → (n_samples,)
    feature_names    : list of column names matching X's columns
    variant_catalogue: {component: [sorted list of unique values seen in training]}
    """
    rows = df.dropna(subset=['score']).copy()

    # Game property numeric features — sorted for deterministic column order
    game_cols = sorted(c for c in rows.columns if c.startswith('game_'))
    X_game = rows[game_cols].astype(float).values  # NaN preserved intentionally

    # Variant one-hot encoding (one block per component)
    token_names: List[str] = []
    token_mats: List[np.ndarray] = []
    variant_catalogue: Dict[str, List[str]] = {}

    for comp in VARIANT_COMP_COLS:
        if comp not in rows.columns:
            continue
        vals = rows[comp].fillna('').astype(str)
        unique = sorted(v for v in vals.unique() if v)
        variant_catalogue[comp] = unique
        for u in unique:
            token_names.append(f'{comp}={u}')
        mat = np.zeros((len(rows), len(unique)), dtype=float)
        for i, v in enumerate(vals):
            if v in unique:
                mat[i, unique.index(v)] = 1.0
        token_mats.append(mat)

    X_tokens = np.hstack(token_mats) if token_mats else np.zeros((len(rows), 0))
    X = np.hstack([X_game, X_tokens])

    targets = {
        'score':    rows['score'].values.astype(float),
        'winrate':  rows['winrate'].values.astype(float),
        'drawrate': rows['drawrate'].values.astype(float),
    }
    feature_names = game_cols + token_names

    return X, targets, feature_names, variant_catalogue


# ---------------------------------------------------------------------------
# Model definitions and hyper-parameter search grids
# ---------------------------------------------------------------------------

def _get_model_configs() -> Dict[str, Dict]:
    """Return a dict mapping each model name to its pipeline, param grid, and target mode.

    Each config has:
      pipeline   : sklearn Pipeline
      param_grid : dict or list of dicts for GridSearchCV
      multi_output : bool — if True, target is (winrate, drawrate) 2-column array;
                     if False, target is the scalar 'score' column.

    Single-target models predict 'score' directly.
    Multi-output models predict (winrate, drawrate) and derive score for evaluation.
    """
    _impute_scale = [
        ('imputer', SimpleImputer(strategy='constant', fill_value=0.0)),
        ('scaler', StandardScaler()),
    ]
    _impute_only = [
        ('imputer', SimpleImputer(strategy='constant', fill_value=0.0)),
    ]

    configs = {
        # ---- Single-target: predict score ----
        'KernelRidge': {
            'pipeline': Pipeline(_impute_scale + [('model', KernelRidge())]),
            'param_grid': [
                {
                    'model__kernel': ['rbf'],
                    'model__alpha':  [0.01, 0.1, 1.0, 10.0],
                    'model__gamma':  [0.001, 0.01, 0.1, 1.0],
                },
                {
                    'model__kernel': ['polynomial'],
                    'model__alpha':  [0.01, 0.1, 1.0, 10.0],
                    'model__gamma':  [0.01, 0.1],
                    'model__degree': [2, 3],
                },
            ],
            'multi_output': False,
        },
        'Ridge': {
            'pipeline': Pipeline(_impute_scale + [('model', Ridge())]),
            'param_grid': {
                'model__alpha': [0.01, 0.1, 1.0, 10.0, 100.0],
            },
            'multi_output': False,
        },
        'HistGradientBoosting': {
            'pipeline': Pipeline([
                ('model', HistGradientBoostingRegressor(random_state=42)),
            ]),
            'param_grid': {
                'model__max_iter':          [200, 500],
                'model__learning_rate':     [0.05, 0.1],
                'model__max_depth':         [3, 5, None],
                'model__l2_regularization': [0.0, 1.0],
            },
            'multi_output': False,
        },
        'RandomForest': {
            'pipeline': Pipeline(_impute_only + [
                ('model', RandomForestRegressor(random_state=42, n_jobs=1)),
            ]),
            'param_grid': {
                'model__n_estimators':     [100, 200],
                'model__max_depth':        [5, 10, None],
                'model__min_samples_leaf': [1, 5],
                'model__max_features':     ['sqrt', 0.5],
            },
            'multi_output': False,
        },

        # ---- Multi-output: predict (winrate, drawrate) simultaneously ----
        'Ridge_MO': {
            'pipeline': Pipeline(_impute_scale + [('model', Ridge())]),
            'param_grid': {
                'model__alpha': [0.01, 0.1, 1.0, 10.0, 100.0],
            },
            'multi_output': True,
        },
        'HistGradientBoosting_MO': {
            'pipeline': Pipeline([
                ('model', MultiOutputRegressor(
                    HistGradientBoostingRegressor(random_state=42)
                )),
            ]),
            'param_grid': {
                'model__estimator__max_iter':          [200, 500],
                'model__estimator__learning_rate':     [0.05, 0.1],
                'model__estimator__max_depth':         [3, 5],
                'model__estimator__l2_regularization': [0.0, 1.0],
            },
            'multi_output': True,
        },
        'RandomForest_MO': {
            'pipeline': Pipeline(_impute_only + [
                ('model', RandomForestRegressor(random_state=42, n_jobs=1)),
            ]),
            'param_grid': {
                'model__n_estimators':     [100, 200],
                'model__max_depth':        [5, 10, None],
                'model__min_samples_leaf': [1, 5],
                'model__max_features':     ['sqrt', 0.5],
            },
            'multi_output': True,
        },
    }

    return configs


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------

def _plot_scatter(
    y_test: np.ndarray,
    y_pred: np.ndarray,
    mse: float,
    r2: float,
    label: str,
    model_name: str,
) -> None:
    """Save a true-vs-predicted scatter plot for one model on the held-out test set."""
    path = _scatter_out_path(label, model_name)
    plt.figure(figsize=(5, 5))
    plt.scatter(y_test, y_pred, alpha=0.5, s=20, label='test samples')
    plt.plot([0, 1], [0, 1], 'r--', linewidth=1, label='perfect prediction')
    plt.xlim(0, 1)
    plt.ylim(0, 1)
    plt.xlabel('True score')
    plt.ylabel('Predicted score')
    plt.title(f'{model_name} [{label}]\nMSE={mse:.4f}  R\u00b2={r2:.4f}')
    plt.legend(fontsize=7)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    print(f'    Scatter saved -> {path}')


def _plot_comparison(all_metrics: Dict[str, Dict], label: str) -> None:
    """Save a side-by-side horizontal bar chart comparing MSE and R² across all models."""
    path = _comparison_out_path(label)
    names = list(all_metrics.keys())
    mses = [all_metrics[n]['mse'] for n in names]
    r2s  = [all_metrics[n]['r2']  for n in names]

    fig, axes = plt.subplots(1, 2, figsize=(11, max(3, len(names) * 0.8 + 1)))

    # MSE — lower is better
    bars = axes[0].barh(names, mses, color='steelblue')
    axes[0].set_xlabel('Score MSE (lower is better)')
    axes[0].set_title(f'Score MSE [{label}]')
    for bar, v in zip(bars, mses):
        axes[0].text(v + max(mses) * 0.01, bar.get_y() + bar.get_height() / 2,
                     f'{v:.4f}', va='center', fontsize=8)

    # R² — higher is better
    bars = axes[1].barh(names, r2s, color='darkorange')
    axes[1].set_xlabel('Test R² (higher is better)')
    axes[1].set_title(f'R² [{label}]')
    for bar, v in zip(bars, r2s):
        axes[1].text(max(v, 0.0) + 0.01, bar.get_y() + bar.get_height() / 2,
                     f'{v:.4f}', va='center', fontsize=8)

    plt.suptitle(f'Model comparison — dataset: {label}', fontsize=11)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    print(f'  Comparison plot saved -> {path}')


# ---------------------------------------------------------------------------
# Main training and evaluation loop
# ---------------------------------------------------------------------------

def train_all_models(
    df: pd.DataFrame,
    label: str,
    test_size: float = 0.1,
    random_state: int = 42,
) -> Dict[str, Dict]:
    """Train, tune, and evaluate all configured models; save the best one.

    Single-target models predict 'score' directly.
    Multi-output models (suffix _MO) predict (winrate, drawrate); their
    score is derived as ``pred_winrate + 0.5 * pred_drawrate`` for comparison.

    The model with the lowest test MSE on the score target is saved as the
    best model.
    """
    print(f"\n{'=' * 65}")
    print(f"  Dataset: [{label}]  ({len(df)} rows)")
    print(f"{'=' * 65}")

    X, targets, feature_names, variant_catalogue = build_feature_matrix(df)
    y_score = targets['score']
    y_winrate = targets['winrate']
    y_drawrate = targets['drawrate']
    print(f"  Feature matrix: {X.shape[0]} samples × {X.shape[1]} features")

    # Single train/test split — same indices for all models
    indices = np.arange(X.shape[0])
    idx_train, idx_test = train_test_split(
        indices, test_size=test_size, random_state=random_state
    )
    X_train, X_test = X[idx_train], X[idx_test]

    model_configs = _get_model_configs()
    all_metrics: Dict[str, Dict] = {}
    best_pipeline = None
    best_mse = float('inf')
    best_name = ''
    best_is_multi = False

    for model_name, cfg in model_configs.items():
        is_multi = cfg.get('multi_output', False)
        mode_tag = '(MO: winrate+drawrate)' if is_multi else '(score)'

        if is_multi:
            y_train = np.column_stack([y_winrate[idx_train], y_drawrate[idx_train]])
            y_test_mo = np.column_stack([y_winrate[idx_test], y_drawrate[idx_test]])
        else:
            y_train_single = y_score[idx_train]

        print(f"\n  [{model_name}] {mode_tag} — GridSearchCV (5-fold, {len(idx_train)} train samples)…")
        gs = GridSearchCV(
            cfg['pipeline'],
            cfg['param_grid'],
            cv=5,
            scoring='neg_mean_squared_error',
            n_jobs=-1,
            verbose=0,
            refit=True,
        )

        if is_multi:
            gs.fit(X_train, y_train)
        else:
            gs.fit(X_train, y_train_single)

        pipe = gs.best_estimator_
        print(f"    Best params : {gs.best_params_}")

        # Evaluate on test set — always compute MSE / R² against score
        y_score_test = y_score[idx_test]

        if is_multi:
            pred_mo = pipe.predict(X_test)  # shape (n_test, 2)
            pred_wr = np.clip(pred_mo[:, 0], 0.0, 1.0)
            pred_dr = np.clip(pred_mo[:, 1], 0.0, 1.0)
            y_pred_score = np.clip(pred_wr + 0.5 * pred_dr, 0.0, 1.0)

            # Per-output metrics
            mse_wr = float(mean_squared_error(y_winrate[idx_test], pred_wr))
            r2_wr  = float(r2_score(y_winrate[idx_test], pred_wr))
            mse_dr = float(mean_squared_error(y_drawrate[idx_test], pred_dr))
            r2_dr  = float(r2_score(y_drawrate[idx_test], pred_dr))
            print(f"    Winrate  MSE={mse_wr:.5f}  R²={r2_wr:.5f}")
            print(f"    Drawrate MSE={mse_dr:.5f}  R²={r2_dr:.5f}")
        else:
            y_pred_score = np.clip(pipe.predict(X_test), 0.0, 1.0)

        mse = float(mean_squared_error(y_score_test, y_pred_score))
        mae = float(mean_absolute_error(y_score_test, y_pred_score))
        r2  = float(r2_score(y_score_test, y_pred_score))
        print(f"    Score    MSE={mse:.5f}  MAE={mae:.5f}  R²={r2:.5f}")

        _plot_scatter(y_score_test, y_pred_score, mse, r2, label, model_name)

        metrics_entry: Dict = {
            'mse':         mse,
            'mae':         mae,
            'r2':          r2,
            'best_params': {k: (str(v) if v is None else v) for k, v in gs.best_params_.items()},
            'n_train':     int(len(idx_train)),
            'n_test':      int(len(idx_test)),
            'multi_output': is_multi,
        }
        if is_multi:
            metrics_entry['mse_winrate']  = mse_wr
            metrics_entry['r2_winrate']   = r2_wr
            metrics_entry['mse_drawrate'] = mse_dr
            metrics_entry['r2_drawrate']  = r2_dr

        all_metrics[model_name] = metrics_entry

        if mse < best_mse:
            best_mse = mse
            best_name = model_name
            best_pipeline = pipe
            best_is_multi = is_multi

    print(f"\n  ★ Best model: {best_name}  (Score MSE={best_mse:.5f})")

    _plot_comparison(all_metrics, label)

    # Persist the winning pipeline
    joblib.dump(best_pipeline, _model_out_path(label))
    print(f"  Best model saved -> {_model_out_path(label)}")

    # Save model info (which won + all metrics)
    info = {
        'label':           label,
        'best_model_name': best_name,
        'best_mse':        best_mse,
        'multi_output':    best_is_multi,
        'all_models':      all_metrics,
    }
    with open(_info_out_path(label), 'w', encoding='utf-8') as fh:
        json.dump(info, fh, indent=2)

    # Save feature names (for inference)
    with open(_features_out_path(label), 'w', encoding='utf-8') as fh:
        json.dump(feature_names, fh, indent=2)

    # Save variant catalogue (for predict_best_variant)
    with open(_catalogue_out_path(label), 'w', encoding='utf-8') as fh:
        json.dump(variant_catalogue, fh, indent=2)

    return all_metrics


# ---------------------------------------------------------------------------
# Summary report
# ---------------------------------------------------------------------------

def _print_report(all_results: Dict[str, Dict[str, Dict]]) -> None:
    """Print a formatted table comparing all models across both dataset labels."""
    print(f"\n{'=' * 65}")
    print("  FINAL REPORT  (target = score = wins + 0.5·draws)")
    print(f"{'=' * 65}")
    for label, metrics in all_results.items():
        print(f"\n  Dataset: {label}")
        print(f"  {'Model':<25} {'Score MSE':>10}  {'MAE':>8}  {'R²':>8}  {'Type':>6}")
        print(f"  {'-' * 25} {'-' * 10}  {'-' * 8}  {'-' * 8}  {'-' * 6}")
        best_mse = min(m['mse'] for m in metrics.values())
        for name, m in sorted(metrics.items(), key=lambda x: x[1]['mse']):
            marker = ' ★' if m['mse'] == best_mse else ''
            mtype = 'MO' if m.get('multi_output') else 'score'
            print(f"  {name:<25} {m['mse']:>10.5f}  {m['mae']:>8.5f}  {m['r2']:>8.5f}  {mtype:>6}{marker}")
            if m.get('multi_output'):
                print(f"  {'':25}   wr R²={m['r2_winrate']:.4f}  dr R²={m['r2_drawrate']:.4f}")
    print(f"\n{'=' * 65}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Parse SLURM results, build datasets, train all models, save the best one."""
    if not os.path.isdir(RESULTS_DIR):
        raise SystemExit(f"Results directory not found: {RESULTS_DIR}")
    if not os.path.isfile(GAME_PROPS):
        raise SystemExit(f"game_properties.csv not found: {GAME_PROPS}")

    print("Parsing SLURM results…")
    df_all, df_notimeout = build_datasets(RESULTS_DIR, GAME_PROPS)

    if df_all.empty:
        raise SystemExit("No usable data parsed from results.")

    df_all.to_csv(DATASET_ALL_OUT, index=False)
    df_notimeout.to_csv(DATASET_NOTIMEOUT_OUT, index=False)
    print(f"Saved {DATASET_ALL_OUT}")
    print(f"Saved {DATASET_NOTIMEOUT_OUT}")

    all_results: Dict[str, Dict[str, Dict]] = {}
    all_results['all'] = train_all_models(df_all, label='all')

    if not df_notimeout.empty:
        all_results['notimeout'] = train_all_models(df_notimeout, label='notimeout')
    else:
        print("No-timeout dataset is empty — skipping.")

    _print_report(all_results)


if __name__ == '__main__':
    main()

