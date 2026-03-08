"""Multi-model training script for MCTS variant win-rate prediction.

Trains and tunes four regression models (KernelRidge, Ridge,
HistGradientBoosting, RandomForest) on two datasets ('all' and 'notimeout').
Selects the best model by lowest test-set MSE and saves it as the primary
model for inference.

Key design decisions
--------------------
* Four models trained and compared; the winner is auto-selected.
* META columns (moveTime, maxMoves) excluded: constant across the dataset,
  add zero discriminative signal, and cause zero-variance issues in
  StandardScaler.
* NaN values in game-property features are preserved so HistGradientBoosting
  can exploit missingness natively; other pipelines prepend a SimpleImputer.
* KernelRidge hyper-parameter search uses two separate sub-grids (rbf /
  polynomial) so kernel-specific params (gamma, degree) are only varied
  where they actually apply.
* Matplotlib Agg backend set explicitly for headless cluster environments.

Data structure note
-------------------
The dataset has roughly one variant tested per game (~1 observation / game).
This means the model cannot learn within-game comparisons from the data; it
must generalise purely from game-property features.

Two structural limitations cap achievable R²:
  1. Label noise: each win rate is estimated from only 30 games
     (standard error ≈ 0.09), introducing irreducible noise.
  2. Zero-inflated targets: ~38 % of win rates are ≤ 0.05 (the tested
     variant simply loses against the baseline for that game), creating
     a heavily skewed distribution that is hard to fit.

The most important modelling improvement shipped here is *interaction features*:
  game_property_i  ×  variant_indicator_j
These let linear models learn "variant X works well when game has property Y",
a relationship that is entirely invisible to a purely additive feature set.

Output artefacts (in src/python_script/) per label {'all', 'notimeout'}:
  best_model_{label}.joblib                  best-performing trained pipeline
  best_model_info_{label}.json               which model won + all models' metrics
  features_{label}.json                      feature names used at training time
  variant_catalogue_{label}.json             valid variant-component values seen in training
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
    include_interactions: bool = True,
) -> Tuple[np.ndarray, np.ndarray, List[str], Dict[str, List[str]]]:
    """Build (X, y, feature_names, variant_catalogue) from a dataset DataFrame.

    Game property columns (starting with 'game_') are used as numeric features.
    NaN values are *preserved* in X_game so that pipelines can handle them
    appropriately (SimpleImputer for linear models; native handling for HGB).

    Variant component columns are one-hot encoded into binary indicator features.
    One block of indicators is emitted per component, in the order defined by
    VARIANT_COMP_COLS.

    When include_interactions=True (default), explicit pairwise interaction
    features game_i × variant_j are appended.  These let linear models (Ridge,
    KernelRidge) learn that "variant X performs well when game has property Y" —
    a relationship that is completely invisible to a purely additive feature set.
    NaN game values are treated as 0 when computing interactions (equivalent to
    the imputation done by SimpleImputer in each pipeline).
    Tree-based models (HGB, RF) already learn such interactions via splits, but
    having them explicitly in the feature matrix does not hurt.

    Returns
    -------
    X                : (n_samples, n_features) float array, NaN in game columns
    y                : (n_samples,) win-rate array
    feature_names    : list of column names matching X's columns
    variant_catalogue: {component: [sorted list of unique values seen in training]}
    """
    rows = df.dropna(subset=['winrate']).copy()

    # Game property numeric features — sorted for deterministic column order
    game_cols = sorted(c for c in rows.columns if c.startswith('game_'))
    X_game = rows[game_cols].astype(float).values  # NaN preserved for pipelines

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

    if include_interactions and X_game.shape[1] > 0 and X_tokens.shape[1] > 0:
        # Compute outer products: game_feat_i × variant_j for every (i, j) pair.
        # NaN game values are zeroed so the interaction is 0 rather than NaN.
        X_game_clean = np.nan_to_num(X_game, nan=0.0)
        n = X_game_clean.shape[0]
        # Broadcasting: (n, n_game, 1) * (n, 1, n_token) => (n, n_game, n_token)
        X_interact = (
            X_game_clean[:, :, np.newaxis] * X_tokens[:, np.newaxis, :]
        ).reshape(n, X_game_clean.shape[1] * X_tokens.shape[1])
        interaction_names = [
            f'{g}×{t}' for g in game_cols for t in token_names
        ]
        X = np.hstack([X_game, X_tokens, X_interact])
        feature_names = game_cols + token_names + interaction_names
    else:
        X = np.hstack([X_game, X_tokens])
        feature_names = game_cols + token_names

    y = rows['winrate'].values.astype(float)
    return X, y, feature_names, variant_catalogue


# ---------------------------------------------------------------------------
# Model definitions and hyper-parameter search grids
# ---------------------------------------------------------------------------

def _get_model_configs() -> Dict[str, Dict]:
    """Return a dict mapping each model name to its sklearn pipeline and param grid.

    Pipeline design rationale
    -------------------------
    KernelRidge / Ridge : need centering + scaling (zero-mean, unit-variance) and
                          cannot handle NaN natively, so a SimpleImputer is prepended.
    HistGBM             : supports NaN natively (uses missingness as a split criterion);
                          no scaling needed.
    RandomForest        : cannot handle NaN (imputer required) but does not need scaling.

    KernelRidge param grid uses a *list* of two sub-grids to avoid evaluating
    parameters that have no effect for a given kernel:
      - RBF kernel       : gamma controls bandwidth; degree is irrelevant.
      - Polynomial kernel: degree controls the polynomial order; gamma has a
                           different semantic role than in RBF.
    """
    _impute_scale = [
        ('imputer', SimpleImputer(strategy='constant', fill_value=0.0)),
        ('scaler', StandardScaler()),
    ]
    _impute_only = [
        ('imputer', SimpleImputer(strategy='constant', fill_value=0.0)),
    ]

    return {
        'KernelRidge': {
            'pipeline': Pipeline(_impute_scale + [('model', KernelRidge())]),
            # Two sub-grids keep gamma/degree valid only for the kernel that uses them
            # (avoids wasting CV fits on irrelevant param combinations)
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
        },
        'Ridge': {
            'pipeline': Pipeline(_impute_scale + [('model', Ridge())]),
            # Higher alpha values needed because interaction features greatly
            # increase the number of columns (~1400 with interactions vs ~76).
            'param_grid': {
                'model__alpha': [0.1, 1.0, 10.0, 100.0, 1000.0],
            },
        },
        'HistGradientBoosting': {
            # No imputer: HistGBM handles NaN natively
            'pipeline': Pipeline([
                ('model', HistGradientBoostingRegressor(random_state=42)),
            ]),
            'param_grid': {
                'model__max_iter':          [200, 500],
                'model__learning_rate':     [0.05, 0.1],
                'model__max_depth':         [3, 5, None],
                'model__l2_regularization': [0.0, 1.0],
            },
        },
        'RandomForest': {
            # n_jobs=1 in estimator; GridSearchCV's n_jobs=-1 parallelises CV folds
            'pipeline': Pipeline(_impute_only + [
                ('model', RandomForestRegressor(random_state=42, n_jobs=1)),
            ]),
            'param_grid': {
                'model__n_estimators':     [100, 200],
                'model__max_depth':        [5, 10, None],
                'model__min_samples_leaf': [1, 5],
                'model__max_features':     ['sqrt', 0.5],
            },
        },
    }


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------

def _plot_distribution(df: pd.DataFrame, label: str) -> None:
    """Save a histogram of the win-rate distribution to help diagnose data issues.

    Key things to look for:
    - Zero-inflation: a tall bar near 0 means many variants simply lose.
    - Spread: if most values cluster around the mean, fitting is harder.
    - Noise floor: with 30 games/matchup the label SE is ~0.09, so differences
      smaller than that are indistinguishable from noise.
    """
    path = os.path.join(HERE, f'plot_distribution_{label}.png')
    wr = df['winrate'].dropna()
    n_total = len(wr)
    n_zero = (wr <= 1e-9).sum()
    n_near_zero = (wr <= 0.05).sum()
    label_se = np.sqrt(wr * (1 - wr) / 30).mean()  # avg SE assuming 30 games

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(wr, bins=40, color='steelblue', edgecolor='white', linewidth=0.4)
    ax.axvline(wr.mean(), color='red', linestyle='--', linewidth=1.2,
               label=f'mean={wr.mean():.3f}')
    ax.set_xlabel('Win rate')
    ax.set_ylabel('Count')
    ax.set_title(
        f'Win-rate distribution [{label}]  (n={n_total})\n'
        f'{n_near_zero} samples (={100*n_near_zero/n_total:.0f}%) ≤ 0.05  |  '
        f'avg label SE ≈ {label_se:.3f}'
    )
    ax.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    print(f'  Distribution plot saved -> {path}')


def _plot_feature_importance(pipeline, model_name: str, feature_names: List[str],
                             label: str, top_n: int = 25) -> None:
    """Save a feature importance bar chart for tree-based models.

    Only applicable to RandomForest and HistGradientBoosting (which expose
    feature_importances_).  Silently skips other model types.

    Shows the top-n features by importance so it remains readable even when
    there are hundreds of interaction features.
    """
    try:
        model = pipeline.named_steps['model']
        importances = model.feature_importances_
    except AttributeError:
        return  # model does not expose feature importance (e.g. KernelRidge)

    path = os.path.join(HERE, f'plot_importance_{model_name}_{label}.png')
    indices = np.argsort(importances)[::-1][:top_n]
    names  = [feature_names[i] for i in indices]
    values = importances[indices]

    fig, ax = plt.subplots(figsize=(8, max(4, top_n * 0.3)))
    ax.barh(names[::-1], values[::-1], color='steelblue')
    ax.set_xlabel('Feature importance')
    ax.set_title(f'{model_name} [{label}] — top {top_n} features')
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    print(f'    Importance plot saved -> {path}')


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
    plt.xlabel('True win rate')
    plt.ylabel('Predicted win rate')
    plt.title(f'{model_name} [{label}]\nMSE={mse:.4f}  R²={r2:.4f}')
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
    axes[0].set_xlabel('Test MSE (lower is better)')
    axes[0].set_title(f'MSE [{label}]')
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

    For each model this function:
      1. Runs 5-fold GridSearchCV on the training split (90 % of data) to find
         the best hyper-parameters.
      2. Evaluates the winning estimator on the held-out test split (10 %).
      3. Saves a scatter plot of true vs predicted win rates.

    After all models are evaluated, the one with the lowest test MSE is selected
    as the *best model* and its pipeline is serialised to disk along with:
      - feature names used during training
      - variant catalogue (valid values per component, used by predict_best_variant)
      - a JSON info file recording which model was chosen and all models' metrics
      - a comparison bar chart

    Returns a dict mapping model_name -> metrics dict.
    """
    print(f"\n{'=' * 65}")
    print(f"  Dataset: [{label}]  ({len(df)} rows)")
    print(f"{'=' * 65}")

    # Diagnostic plot of target distribution (run once per dataset, before training)
    _plot_distribution(df, label)

    X, y, feature_names, variant_catalogue = build_feature_matrix(df)
    n_game = sum(1 for f in feature_names if f.startswith('game_'))
    n_variant = sum(1 for f in feature_names if '=' in f and '×' not in f)
    n_interact = sum(1 for f in feature_names if '×' in f)
    print(f"  Feature matrix: {X.shape[0]} samples × {X.shape[1]} features"
          f" ({n_game} game + {n_variant} variant one-hot + {n_interact} interactions)")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state
    )

    model_configs = _get_model_configs()
    all_metrics: Dict[str, Dict] = {}
    best_pipeline = None
    best_mse = float('inf')
    best_name = ''

    for model_name, cfg in model_configs.items():
        print(f"\n  [{model_name}] — GridSearchCV (5-fold, {len(X_train)} train samples)…")
        gs = GridSearchCV(
            cfg['pipeline'],
            cfg['param_grid'],
            cv=5,
            scoring='neg_mean_squared_error',
            n_jobs=-1,
            verbose=0,
            refit=True,
        )
        gs.fit(X_train, y_train)
        pipe = gs.best_estimator_
        print(f"    Best params : {gs.best_params_}")

        y_pred = pipe.predict(X_test)
        mse = float(mean_squared_error(y_test, y_pred))
        mae = float(mean_absolute_error(y_test, y_pred))
        r2  = float(r2_score(y_test, y_pred))
        print(f"    MSE={mse:.5f}  MAE={mae:.5f}  R²={r2:.5f}")

        _plot_scatter(y_test, y_pred, mse, r2, label, model_name)
        _plot_feature_importance(pipe, model_name, feature_names, label)

        all_metrics[model_name] = {
            'mse':         mse,
            'mae':         mae,
            'r2':          r2,
            'best_params': gs.best_params_,
            'n_train':     int(len(X_train)),
            'n_test':      int(len(X_test)),
        }

        if mse < best_mse:
            best_mse = mse
            best_name = model_name
            best_pipeline = pipe

    print(f"\n  ★ Best model: {best_name}  (MSE={best_mse:.5f})")

    _plot_comparison(all_metrics, label)

    # Persist the winning pipeline
    joblib.dump(best_pipeline, _model_out_path(label))
    print(f"  Best model saved -> {_model_out_path(label)}")

    # Save model info (which won + all metrics)
    info = {
        'label':           label,
        'best_model_name': best_name,
        'best_mse':        best_mse,
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
    print("  FINAL REPORT")
    print(f"{'=' * 65}")
    for label, metrics in all_results.items():
        print(f"\n  Dataset: {label}")
        print(f"  {'Model':<25} {'MSE':>8}  {'MAE':>8}  {'R²':>8}")
        print(f"  {'-' * 25} {'-' * 8}  {'-' * 8}  {'-' * 8}")
        best_mse = min(m['mse'] for m in metrics.values())
        for name, m in sorted(metrics.items(), key=lambda x: x[1]['mse']):
            marker = ' ★' if m['mse'] == best_mse else ''
            print(f"  {name:<25} {m['mse']:>8.5f}  {m['mae']:>8.5f}  {m['r2']:>8.5f}{marker}")
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

