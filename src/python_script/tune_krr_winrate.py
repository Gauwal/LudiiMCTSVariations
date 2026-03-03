"""Inference helper for trained KRR models.

Hyperparameter tuning is now integrated into train_krr_winrate.py.
Run `python train_krr_winrate.py` to (re)train and tune both models.

This module exposes:
  predict_winrate(game_name, variant, label='all') -> float
    Returns the predicted win rate for a game/variant pair using the
    specified trained model ('all' or 'notimeout').
"""
import json
import os
import re
from typing import Optional

import numpy as np
import pandas as pd
import joblib

HERE = os.path.dirname(os.path.abspath(__file__))
GAME_PROPS = os.path.join(os.path.abspath(os.path.join(HERE, '..', '..')), 'game_properties.csv')

# Kept for backward-compat import (points to the 'all' model)
OUT_MODEL    = os.path.join(HERE, 'krr_model_all.joblib')
OUT_FEATURES = os.path.join(HERE, 'krr_features_all.json')
OUT_METRICS  = os.path.join(HERE, 'krr_metrics_all.json')
OUT_PLOT     = os.path.join(HERE, 'krr_plot_all.png')

NAME_NORMALIZE_RE = re.compile(r'[^a-z0-9]')

VARIANT_COMP_COLS = ['variant_select', 'variant_simulation',
                     'variant_backprop', 'variant_finalmove']
META_COLS = ['moveTime', 'maxMoves']


def normalize_name(s: str) -> str:
    if not isinstance(s, str):
        return ''
    return NAME_NORMALIZE_RE.sub('', s.lower())


def _model_paths(label: str = 'all') -> dict:
    return {
        'model':    os.path.join(HERE, f'krr_model_{label}.joblib'),
        'features': os.path.join(HERE, f'krr_features_{label}.json'),
        'metrics':  os.path.join(HERE, f'krr_metrics_{label}.json'),
    }


def predict_winrate(
    game_name: str,
    variant: str,
    label: str = 'all',
    move_time: float = 0.5,
    max_moves: int = 1000,
) -> float:
    """Return predicted win rate for a game/variant pair.

    Parameters
    ----------
    game_name : str
        Game name as it appears in game_properties.csv (partial match ok).
    variant : str
        Variant string with components separated by ' | ', e.g.
        'UCB1 | MAST | MonteCarlo | Robust'.
    label : str
        Which trained model to use: 'all' (default) or 'notimeout'.
    move_time : float
        Thinking time per move in seconds (used as a feature). Default 0.5.
    max_moves : int
        Maximum moves per game (used as a feature). Default 1000.
    """
    paths = _model_paths(label)
    if not os.path.isfile(paths['model']) or not os.path.isfile(paths['features']):
        raise FileNotFoundError(
            f"Model artefacts for label='{label}' not found. "
            "Run `python train_krr_winrate.py` first."
        )
    pipeline = joblib.load(paths['model'])
    with open(paths['features'], 'r', encoding='utf-8') as fh:
        feature_names = json.load(fh)

    # Load game properties
    if not os.path.isfile(GAME_PROPS):
        raise FileNotFoundError(f'game_properties.csv not found: {GAME_PROPS}')
    games_df = pd.read_csv(GAME_PROPS)
    games_df['_norm'] = games_df['game'].apply(normalize_name)
    norm_map = dict(zip(games_df['_norm'], games_df['game']))

    norm = normalize_name(game_name)
    mapped: Optional[str] = norm_map.get(norm)
    if mapped is None:
        for n, g in norm_map.items():
            if n.startswith(norm) or norm.startswith(n) or norm in n or n in norm:
                mapped = g
                break
    if mapped is None:
        raise ValueError(f'Game "{game_name}" not found in game_properties.csv')

    props = games_df[games_df['game'] == mapped].iloc[0]

    # Split variant into components
    v_parts = [p.strip() for p in variant.split('|')]
    while len(v_parts) < 4:
        v_parts.append('')
    variant_by_comp = {
        'variant_select':     v_parts[0],
        'variant_simulation': v_parts[1],
        'variant_backprop':   v_parts[2],
        'variant_finalmove':  v_parts[3],
    }

    # Build feature vector matching training order
    meta_values = {'moveTime': move_time, 'maxMoves': max_moves}
    x_vals = []
    for feat in feature_names:
        if feat.startswith('game_'):
            col = feat[len('game_'):]
            try:
                x_vals.append(float(props.get(col, 0)))
            except (TypeError, ValueError):
                x_vals.append(0.0)
        elif feat in META_COLS:
            x_vals.append(float(meta_values.get(feat, 0)))
        elif '=' in feat:
            comp, val = feat.split('=', 1)
            x_vals.append(1.0 if variant_by_comp.get(comp, '') == val else 0.0)
        else:
            x_vals.append(0.0)

    x = np.array(x_vals, dtype=float).reshape(1, -1)
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    pred = pipeline.predict(x)[0]
    return float(np.clip(pred, 0.0, 1.0))


def main():
    import json as _json
    print("Tuning is integrated into train_krr_winrate.py.")
    print("Run:  python train_krr_winrate.py")
    print()
    # Print metrics for any existing trained models
    for label in ('all', 'notimeout'):
        p = _model_paths(label)
        if os.path.isfile(p['metrics']):
            with open(p['metrics'], 'r', encoding='utf-8') as fh:
                m = _json.load(fh)
            print(f"Model [{label}]:")
            print(f"  best_params = {m.get('best_params')}")
            print(f"  MSE={m.get('mse'):.5f}  MAE={m.get('mae'):.5f}  R²={m.get('r2'):.5f}")
            print()


if __name__ == '__main__':
    main()
