"""Train tuned Kernel Ridge Regression models to predict win rate.

Workflow
--------
1. Calls parse_slurm_results.build_datasets() to produce two datasets:
     - krr_dataset_all.csv         (all completed jobs)
     - krr_dataset_notimeout.csv   (timeout games removed)
2. For EACH dataset, using a 90/10 train/test split:
   a. Runs GridSearchCV (5-fold CV) on the training fold to find best KRR
      hyperparameters.
   b. Evaluates the tuned model on the held-out test set.
   c. Saves the tuned pipeline (StandardScaler + KernelRidge), feature names,
      metrics (including best hyperparameters), and a true-vs-predicted scatter
      plot.
3. Prints a side-by-side hyperparameter report for both models.

Output artefacts (in src/python_script/):
  krr_model_all.joblib            tuned pipeline for 'all' dataset
  krr_features_all.json           feature names for 'all' model
  krr_metrics_all.json            metrics + best_params for 'all' model
  krr_plot_all.png                scatter for 'all' model
  krr_model_notimeout.joblib      tuned pipeline for 'no-timeout' dataset
  krr_features_notimeout.json     feature names for 'no-timeout' model
  krr_metrics_notimeout.json      metrics + best_params for 'no-timeout' model
  krr_plot_notimeout.png          scatter for 'no-timeout' model
"""
import json
import os
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import joblib
from sklearn.kernel_ridge import KernelRidge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from parse_slurm_results import build_datasets, RESULTS_DIR, GAME_PROPS

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Artefact path helpers
# ---------------------------------------------------------------------------
def _paths(label: str) -> Dict[str, str]:
    """Return output paths for a given model label ('all' or 'notimeout')."""
    return {
        'model':    os.path.join(HERE, f'krr_model_{label}.joblib'),
        'features': os.path.join(HERE, f'krr_features_{label}.json'),
        'metrics':  os.path.join(HERE, f'krr_metrics_{label}.json'),
        'plot':     os.path.join(HERE, f'krr_plot_{label}.png'),
    }


# ---------------------------------------------------------------------------
# Feature matrix builder
# ---------------------------------------------------------------------------
VARIANT_COMP_COLS = ['variant_select', 'variant_simulation',
                     'variant_backprop', 'variant_finalmove']
META_COLS = ['moveTime', 'maxMoves']


def build_feature_matrix(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """Return (X, y, feature_names) for a KRR-ready dataset DataFrame."""
    rows = df.dropna(subset=['winrate']).copy()

    # Game property columns  (numeric)
    game_cols = [c for c in rows.columns if c.startswith('game_')]
    X_game = rows[game_cols].astype(float).fillna(0).values

    # Meta columns: moveTime, maxMoves  (numeric)
    X_meta = rows[META_COLS].astype(float).fillna(0).values

    # Variant one-hot encoding  (one block per component)
    token_names: List[str] = []
    token_mats = []
    for comp in VARIANT_COMP_COLS:
        if comp not in rows.columns:
            continue
        vals = rows[comp].fillna('').astype(str)
        unique = sorted(v for v in vals.unique() if v)
        for u in unique:
            token_names.append(f'{comp}={u}')
        mat = np.zeros((len(rows), len(unique)), dtype=float)
        for i, v in enumerate(vals):
            if v in unique:
                mat[i, unique.index(v)] = 1.0
        token_mats.append(mat)

    X_tokens = np.hstack(token_mats) if token_mats else np.zeros((len(rows), 0))
    X = np.hstack([X_game, X_meta, X_tokens])
    y = rows['winrate'].values.astype(float)
    feature_names = game_cols + META_COLS + token_names

    return X, y, feature_names


# ---------------------------------------------------------------------------
# Tuning + evaluation
# ---------------------------------------------------------------------------
PARAM_GRID = {
    'krr__kernel': ['rbf', 'linear', 'polynomial'],
    'krr__alpha':  [0.1, 1.0, 10.0],
    'krr__gamma':  [0.01, 0.1, 1.0],
    'krr__degree': [2, 3],
}


def train_tuned_model(
    df: pd.DataFrame,
    label: str,
    test_size: float = 0.1,
    random_state: int = 42,
) -> Dict:
    """Build features, tune via GridSearchCV, evaluate on test set, save artefacts."""
    print(f"\n{'=' * 60}")
    print(f"  Training model: [{label}]  ({len(df)} rows)")
    print(f"{'=' * 60}")

    X, y, feature_names = build_feature_matrix(df)
    print(f"  Feature matrix : {X.shape[0]} samples × {X.shape[1]} features")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state
    )

    pipe = Pipeline([
        ('scaler', StandardScaler()),
        ('krr', KernelRidge()),
    ])

    print(f"  Running GridSearchCV (5-fold, {len(X_train)} train samples)…")
    gs = GridSearchCV(
        pipe, PARAM_GRID, cv=5,
        scoring='neg_mean_squared_error',
        n_jobs=-1, verbose=0,
    )
    gs.fit(X_train, y_train)
    best_pipeline = gs.best_estimator_
    print(f"  Best parameters found: {gs.best_params_}")

    y_pred = best_pipeline.predict(X_test)
    metrics = {
        'label':       label,
        'best_params': gs.best_params_,
        'n_train':     int(len(X_train)),
        'n_test':      int(len(X_test)),
        'mse':         float(mean_squared_error(y_test, y_pred)),
        'mae':         float(mean_absolute_error(y_test, y_pred)),
        'r2':          float(r2_score(y_test, y_pred)),
    }
    print(f"  Test MSE={metrics['mse']:.5f}  MAE={metrics['mae']:.5f}  R²={metrics['r2']:.5f}")

    p = _paths(label)

    # Save pipeline (includes scaler)
    joblib.dump(best_pipeline, p['model'])

    # Save feature names
    with open(p['features'], 'w', encoding='utf-8') as fh:
        json.dump(feature_names, fh, indent=2)

    # Save metrics
    with open(p['metrics'], 'w', encoding='utf-8') as fh:
        json.dump(metrics, fh, indent=2)

    # Scatter plot
    plt.figure(figsize=(6, 6))
    plt.scatter(y_test, y_pred, alpha=0.6, label='test samples')
    plt.plot([0, 1], [0, 1], 'r--', label='perfect prediction')
    plt.xlim(0, 1)
    plt.ylim(0, 1)
    plt.xlabel('True winrate')
    plt.ylabel('Predicted winrate')
    plt.title(f'KRR [{label}]: True vs Predicted (test set)\n'
              f'MSE={metrics["mse"]:.4f}  R²={metrics["r2"]:.4f}')
    plt.legend(fontsize=8)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(p['plot'], dpi=150)
    plt.close()
    print(f"  Plot saved  → {p['plot']}")

    return metrics


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def _print_report(metrics_list: List[Dict]) -> None:
    print(f"\n{'=' * 60}")
    print("  HYPERPARAMETER REPORT")
    print(f"{'=' * 60}")
    for m in metrics_list:
        lbl = m['label']
        bp  = m['best_params']
        print(f"\n  Model : {lbl}  (train={m['n_train']}, test={m['n_test']})")
        print(f"    kernel  = {bp.get('krr__kernel')}")
        print(f"    alpha   = {bp.get('krr__alpha')}")
        print(f"    gamma   = {bp.get('krr__gamma')}")
        print(f"    degree  = {bp.get('krr__degree')}")
        print(f"    MSE={m['mse']:.5f}  MAE={m['mae']:.5f}  R²={m['r2']:.5f}")
    print(f"\n{'=' * 60}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if not os.path.isdir(RESULTS_DIR):
        raise SystemExit(f"Results directory not found: {RESULTS_DIR}")
    if not os.path.isfile(GAME_PROPS):
        raise SystemExit(f"game_properties.csv not found: {GAME_PROPS}")

    print("Parsing SLURM results…")
    df_all, df_notimeout = build_datasets(RESULTS_DIR, GAME_PROPS)

    if df_all.empty:
        raise SystemExit("No usable data parsed from results.")

    # Save raw datasets so they can be inspected independently
    from parse_slurm_results import DATASET_ALL_OUT, DATASET_NOTIMEOUT_OUT
    df_all.to_csv(DATASET_ALL_OUT, index=False)
    df_notimeout.to_csv(DATASET_NOTIMEOUT_OUT, index=False)

    metrics_all       = train_tuned_model(df_all,       label='all')
    metrics_notimeout = train_tuned_model(df_notimeout, label='notimeout')

    _print_report([metrics_all, metrics_notimeout])


if __name__ == '__main__':
    main()

