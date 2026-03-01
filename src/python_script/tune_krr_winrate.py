"""Hyperparameter tuning for Kernel Ridge Regression predicting winrate.

- Loads dataset `krr_dataset.csv` created by earlier script
- Splits 90/10, runs GridSearchCV on training fold
- Evaluates on test set and saves scatter plot of true vs predicted
- Saves best model, scaler, feature names, and metrics
- Exposes `predict_winrate(game_name, variant)` function for single predictions
"""
import os
import re
import json
from typing import List, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.kernel_ridge import KernelRidge
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import joblib

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET_CSV = os.path.join(HERE, 'krr_dataset.csv')
GAME_PROPS = os.path.join(os.path.abspath(os.path.join(HERE, '..', '..')), 'game_properties.csv')
OUT_MODEL = os.path.join(HERE, 'krr_kcv_model.joblib')
OUT_SCALER = os.path.join(HERE, 'krr_kcv_scaler.joblib')
OUT_FEATURES = os.path.join(HERE, 'krr_feature_names.json')
OUT_METRICS = os.path.join(HERE, 'krr_kcv_metrics.json')
OUT_PLOT = os.path.join(HERE, 'krr_test_predictions.png')

NAME_NORMALIZE_RE = re.compile(r'[^a-z0-9]')

def normalize_name(s: str) -> str:
    if not isinstance(s, str):
        return ''
    return NAME_NORMALIZE_RE.sub('', s.lower())


def load_dataset(path: str) -> pd.DataFrame:
    if not os.path.isfile(path):
        raise FileNotFoundError(f'Dataset not found: {path}')
    return pd.read_csv(path)


def build_feature_matrix(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, List[str], pd.DataFrame]:
    # numeric game_ columns (game properties)
    num_cols = [c for c in df.columns if c.startswith('game_')]
    X_num = df[num_cols].astype(float).fillna(0).values

    # variant components: one-hot each of the four parts
    comp_cols = ['variant_select', 'variant_simulation', 'variant_backprop', 'variant_finalmove']
    token_list_all: List[str] = []
    token_matrices = []
    for comp in comp_cols:
        if comp in df.columns:
            tokens = df[comp].fillna('').astype(str)
            unique = sorted([t for t in tokens.unique() if t])
            token_list_all.extend([f"{comp}={t}" for t in unique])
            mat = np.zeros((len(df), len(unique)), dtype=float)
            for i, v in enumerate(tokens):
                if v and v in unique:
                    mat[i, unique.index(v)] = 1.0
            token_matrices.append(mat)
    X_tokens = np.hstack(token_matrices) if token_matrices else np.zeros((len(df), 0))

    X = np.hstack([X_num, X_tokens])
    y = df['winrate'].values.astype(float)
    feature_names = num_cols + token_list_all
    return X, y, feature_names, df


def tune_and_save(X: np.ndarray, y: np.ndarray, feature_names: List[str]):
    # 90/10 split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.1, random_state=42)

    pipe = Pipeline([
        ('scaler', StandardScaler()),
        ('krr', KernelRidge())
    ])

    param_grid = {
        'krr__kernel': ['rbf', 'linear', 'polynomial'],
        'krr__alpha': [0.1, 1.0, 10.0],
        'krr__gamma': [0.01, 0.1, 1.0],
        'krr__degree': [2, 3]
    }

    gs = GridSearchCV(pipe, param_grid, cv=5, scoring='neg_mean_squared_error', n_jobs=-1, verbose=0)
    gs.fit(X_train, y_train)

    best = gs.best_estimator_
    # evaluate on test set
    y_pred = best.predict(X_test)
    metrics = {
        'best_params': gs.best_params_,
        'mse': float(mean_squared_error(y_test, y_pred)),
        'mae': float(mean_absolute_error(y_test, y_pred)),
        'r2': float(r2_score(y_test, y_pred)),
        'n_test': int(len(y_test))
    }

    # save model (pipeline includes scaler)
    joblib.dump(best, OUT_MODEL)

    # save feature names
    with open(OUT_FEATURES, 'w', encoding='utf-8') as fh:
        json.dump(feature_names, fh, indent=2)

    # save metrics
    with open(OUT_METRICS, 'w', encoding='utf-8') as fh:
        json.dump(metrics, fh, indent=2)

    # plot true vs pred
    plt.figure(figsize=(6, 6))
    plt.scatter(y_test, y_pred, alpha=0.6)
    plt.plot([0, 1], [0, 1], 'r--')
    plt.xlabel('True winrate')
    plt.ylabel('Predicted winrate')
    plt.title('KRR: True vs Predicted (test set)')
    plt.xlim(0, 1)
    plt.ylim(0, 1)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(OUT_PLOT)
    plt.close()

    return metrics


def predict_winrate(game_name: str, variant: str) -> float:
    """Return predicted winrate for a given game name and variant string.
    Variant tokens should be delimited by `|` as in the dataset.
    """
    # load artifacts
    if not os.path.isfile(OUT_MODEL) or not os.path.isfile(OUT_FEATURES):
        raise FileNotFoundError('Model or feature names not found. Run tuner first.')
    model = joblib.load(OUT_MODEL)
    with open(OUT_FEATURES, 'r', encoding='utf-8') as fh:
        feature_names = json.load(fh)

    # load game properties
    games_df = pd.read_csv(GAME_PROPS)
    games_df['_norm'] = games_df['game'].apply(normalize_name)
    norm_map = dict(zip(games_df['_norm'], games_df['game']))

    norm = normalize_name(game_name)
    mapped = norm_map.get(norm)
    if mapped is None:
        # try contains/startswith
        for n, g in norm_map.items():
            if n == norm or n.startswith(norm) or norm.startswith(n) or n.find(norm) >= 0 or norm.find(n) >= 0:
                mapped = g
                break
    if mapped is None:
        raise ValueError(f'Game "{game_name}" not found in game properties')

    props = games_df[games_df['game'] == mapped].iloc[0]
    # build numeric part
    num_part = []
    for col in feature_names:
        if col.startswith('game_'):
            propname = col[len('game_'):]
            val = props.get(propname, 0)
            try:
                num_part.append(float(val))
            except Exception:
                num_part.append(0.0)

    # build token part
    token_part = []
    # tokens are feature_names after numeric ones
    token_names = [fn for fn in feature_names if not fn.startswith('game_')]
    parts = [t.strip() for t in variant.split('|')]
    while len(parts) < 4:
        parts.append('')
    variant_by_comp = {
        'variant_select': parts[0],
        'variant_simulation': parts[1],
        'variant_backprop': parts[2],
        'variant_finalmove': parts[3],
    }
    raw_token_set = {p for p in parts if p}
    for feature in token_names:
        if '=' in feature:
            comp, val = feature.split('=', 1)
            token_part.append(1.0 if variant_by_comp.get(comp, '') == val else 0.0)
        else:
            # compatibility with any older artifacts that stored plain token names
            token_part.append(1.0 if feature in raw_token_set else 0.0)

    x = np.array(num_part + token_part).reshape(1, -1)
    # guard against NaN/Inf in the constructed feature vector
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    pred = model.predict(x)[0]
    # clip to [0,1]
    return float(np.clip(pred, 0.0, 1.0))


def main():
    print('Loading dataset:', DATASET_CSV)
    df = load_dataset(DATASET_CSV)
    X, y, feature_names, _ = build_feature_matrix(df)
    print('Dataset rows, features:', X.shape)
    metrics = tune_and_save(X, y, feature_names)
    print('Tuning complete. Metrics:')
    print(json.dumps(metrics, indent=2))


if __name__ == '__main__':
    main()
