"""Inference helpers for the trained MCTS variant prediction models.

Run `python train_winrate.py` to (re)train and tune all models.

The primary prediction target is **score** defined as
``(wins + 0.5 * effective_draws) / effective_total``, where timeout games
are excluded from both draws and the total.

If the best saved model is a multi-output model (predicting winrate and
drawrate simultaneously), the score is derived as
``predicted_winrate + 0.5 * predicted_drawrate``.

Exposed API
-----------
predict_score(game_name, variant, label='all') -> float
    Predicts the score for a single (game, variant) pair.

predict_best_variant(game_name, label='all', top_k=5) -> dict
    Exhaustively evaluates all variant combinations seen during training
    and returns the top-k ranked by predicted score.
"""

import itertools
import json
import os
import re
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import joblib

HERE = os.path.dirname(os.path.abspath(__file__))
GAME_PROPS = os.path.join(os.path.abspath(os.path.join(HERE, '..', '..')), 'game_properties.csv')

VARIANT_COMP_COLS = [
    'variant_select',
    'variant_simulation',
    'variant_backprop',
    'variant_finalmove',
]

_NAME_RE = re.compile(r'[^a-z0-9]')


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def normalize_name(s: str) -> str:
    """Normalise a game name to lowercase alphanumeric for fuzzy matching."""
    if not isinstance(s, str):
        return ''
    return _NAME_RE.sub('', s.lower())


def _model_paths(label: str = 'all') -> dict:
    """Return a dict of file paths for all artefacts of the given dataset label."""
    return {
        'model':     os.path.join(HERE, f'best_model_{label}.joblib'),
        'features':  os.path.join(HERE, f'features_{label}.json'),
        'catalogue': os.path.join(HERE, f'variant_catalogue_{label}.json'),
        'info':      os.path.join(HERE, f'best_model_info_{label}.json'),
    }


def _load_game_properties() -> pd.DataFrame:
    """Load game_properties.csv and attach a normalised-name column for fuzzy matching."""
    if not os.path.isfile(GAME_PROPS):
        raise FileNotFoundError(f'game_properties.csv not found: {GAME_PROPS}')
    df = pd.read_csv(GAME_PROPS)
    df['_norm'] = df['game'].apply(normalize_name)
    return df


def _get_game_row(game_name: str, games_df: pd.DataFrame) -> pd.Series:
    """Return the game-properties row for the given game name.

    Performs an exact normalised match first, then falls back to prefix /
    substring matching.  Raises ValueError if no match is found.
    """
    norm = normalize_name(game_name)
    norm_map = dict(zip(games_df['_norm'], games_df['game']))
    mapped: Optional[str] = norm_map.get(norm)
    if mapped is None:
        for n, g in norm_map.items():
            if n.startswith(norm) or norm.startswith(n) or norm in n or n in norm:
                mapped = g
                break
    if mapped is None:
        raise ValueError(f'Game "{game_name}" not found in game_properties.csv')
    return games_df[games_df['game'] == mapped].iloc[0]


def _build_feature_vector(
    game_row: pd.Series,
    variant_by_comp: Dict[str, str],
    feature_names: List[str],
) -> np.ndarray:
    """Build a single-row feature vector aligned to the training feature order.

    Follows the same layout produced by build_feature_matrix() in
    train_winrate.py:
      - game property features first (with 'game_' prefix stripped to look up
        in game_properties.csv, which stores columns without that prefix)
      - one-hot variant indicator features next

    NaN is used for missing game values so that pipelines with a SimpleImputer
    step handle them correctly (and HistGBM pipelines handle them natively).
    """
    x_vals: List[float] = []
    for feat in feature_names:
        if feat.startswith('game_'):
            # Strip the 'game_' prefix: game_properties.csv columns have no prefix
            col = feat[len('game_'):]
            try:
                val = game_row.get(col, np.nan)
                x_vals.append(float(val) if val is not None else np.nan)
            except (TypeError, ValueError):
                x_vals.append(np.nan)
        elif '=' in feat:
            comp, val = feat.split('=', 1)
            x_vals.append(1.0 if variant_by_comp.get(comp, '') == val else 0.0)
        else:
            x_vals.append(np.nan)
    return np.array(x_vals, dtype=float)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _is_multi_output(label: str) -> bool:
    """Return True if the best model for the given label is a multi-output model."""
    paths = _model_paths(label)
    if os.path.isfile(paths['info']):
        with open(paths['info'], 'r', encoding='utf-8') as fh:
            info = json.load(fh)
        return info.get('multi_output', False)
    return False


def _predict_score_from_pipeline(pipeline, x: np.ndarray, multi_output: bool) -> np.ndarray:
    """Run prediction through the pipeline and return score values.

    Parameters
    ----------
    pipeline : fitted sklearn pipeline
    x : array of shape (n_samples, n_features)
    multi_output : bool
        If True, the pipeline predicts (winrate, drawrate) and score is
        derived as ``winrate + 0.5 * drawrate``.

    Returns
    -------
    np.ndarray of shape (n_samples,) with score values clipped to [0, 1].
    """
    raw = pipeline.predict(x)
    if multi_output and raw.ndim == 2 and raw.shape[1] >= 2:
        wr = np.clip(raw[:, 0], 0.0, 1.0)
        dr = np.clip(raw[:, 1], 0.0, 1.0)
        scores = np.clip(wr + 0.5 * dr, 0.0, 1.0)
    else:
        scores = np.clip(raw.ravel(), 0.0, 1.0)
    return scores


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def predict_score(
    game_name: str,
    variant: str,
    label: str = 'all',
    move_time: float = 0.5,
    max_moves: int = 1000,
) -> float:
    """Return the predicted score for a (game, variant) pair.

    Parameters
    ----------
    game_name : str
        Game name as it appears in game_properties.csv (partial match supported).
    variant : str
        Variant string with pipe-separated components, e.g.
        'UCB1 | MAST | MonteCarlo | Robust'.
    label : str
        Which trained model to use: 'all' (default) or 'notimeout'.
    move_time, max_moves : float / int
        Kept for backward compatibility; not used as model features.

    Returns
    -------
    float
        Predicted score clipped to [0, 1].
    """
    paths = _model_paths(label)
    if not os.path.isfile(paths['model']) or not os.path.isfile(paths['features']):
        raise FileNotFoundError(
            f"Model artefacts for label='{label}' not found. "
            "Run `python train_winrate.py` first."
        )
    pipeline = joblib.load(paths['model'])
    with open(paths['features'], 'r', encoding='utf-8') as fh:
        feature_names: List[str] = json.load(fh)

    multi_output = _is_multi_output(label)

    games_df = _load_game_properties()
    game_row = _get_game_row(game_name, games_df)

    v_parts = [p.strip() for p in variant.split('|')]
    while len(v_parts) < 4:
        v_parts.append('')
    variant_by_comp = dict(zip(VARIANT_COMP_COLS, v_parts))

    x = _build_feature_vector(game_row, variant_by_comp, feature_names).reshape(1, -1)
    return float(_predict_score_from_pipeline(pipeline, x, multi_output)[0])


# Backward-compatible alias
predict_winrate = predict_score


def predict_best_variant(
    game_name: str,
    label: str = 'all',
    top_k: int = 5,
    move_time: float = 0.5,
    max_moves: int = 1000,
) -> Dict:
    """Find the best MCTS variant configuration for a given game by exhaustive search.

    Loads the best trained model and the variant catalogue saved during training.
    Generates *all* combinations of (select × simulation × backprop × finalmove)
    from the catalogue, predicts scores in a single vectorised batch, and
    returns the top-k combinations ranked by predicted score (descending).

    Parameters
    ----------
    game_name : str
        Game name as it appears in game_properties.csv.
    label : str
        Which trained model to use: 'all' (default) or 'notimeout'.
    top_k : int
        Number of top combinations to include in the returned list (default 5).
    move_time, max_moves : float / int
        Kept for API consistency; not used as model features.

    Returns
    -------
    dict with keys
        'game'         : resolved game name
        'label'        : dataset label used
        'best_variant' : highest-ranked variant string, e.g. 'UCB1 | MAST | MonteCarlo | Robust'
        'best_score'   : predicted score for the best variant
        'top_k'        : list of (variant_str, predicted_score) tuples, best first
        'n_evaluated'  : total number of combinations evaluated
    """
    paths = _model_paths(label)
    missing = [k for k in ('model', 'features', 'catalogue') if not os.path.isfile(paths[k])]
    if missing:
        raise FileNotFoundError(
            f"Missing artefacts for label='{label}': {missing}. "
            "Run `python train_winrate.py` first."
        )

    pipeline = joblib.load(paths['model'])
    with open(paths['features'],  'r', encoding='utf-8') as fh:
        feature_names: List[str] = json.load(fh)
    with open(paths['catalogue'], 'r', encoding='utf-8') as fh:
        catalogue: Dict[str, List[str]] = json.load(fh)

    multi_output = _is_multi_output(label)

    games_df = _load_game_properties()
    game_row = _get_game_row(game_name, games_df)
    resolved_name = str(game_row.get('game', game_name))

    selects     = catalogue.get('variant_select',     [])
    simulations = catalogue.get('variant_simulation', [])
    backprops   = catalogue.get('variant_backprop',   [])
    finalmoves  = catalogue.get('variant_finalmove',  [])

    all_combos: List[Tuple[str, str, str, str]] = list(
        itertools.product(selects, simulations, backprops, finalmoves)
    )
    rows: List[np.ndarray] = []
    for sel, sim, bp, fm in all_combos:
        vbc = {
            'variant_select':     sel,
            'variant_simulation': sim,
            'variant_backprop':   bp,
            'variant_finalmove':  fm,
        }
        rows.append(_build_feature_vector(game_row, vbc, feature_names))

    X_all = np.vstack(rows)
    preds = _predict_score_from_pipeline(pipeline, X_all, multi_output)

    # Sort descending by predicted score
    order = np.argsort(preds)[::-1]
    ranked = [
        (f'{all_combos[i][0]} | {all_combos[i][1]} | {all_combos[i][2]} | {all_combos[i][3]}',
         float(preds[i]))
        for i in order
    ]

    return {
        'game':         resolved_name,
        'label':        label,
        'best_variant': ranked[0][0],
        'best_score':   ranked[0][1],
        'top_k':        ranked[:top_k],
        'n_evaluated':  len(all_combos),
    }


# ---------------------------------------------------------------------------
# Entry point — prints a summary of trained models
# ---------------------------------------------------------------------------

def main():
    """Print a summary of all existing trained models."""
    for label in ('all', 'notimeout'):
        p = _model_paths(label)
        if os.path.isfile(p['info']):
            with open(p['info'], 'r', encoding='utf-8') as fh:
                info = json.load(fh)
            mo_tag = ' (multi-output)' if info.get('multi_output') else ''
            print(f"\nDataset [{label}]:")
            print(f"  Best model : {info.get('best_model_name')}{mo_tag}  "
                  f"Score MSE={info.get('best_mse'):.5f}")
            print("  All models :")
            for name, m in info.get('all_models', {}).items():
                tag = ' MO' if m.get('multi_output') else ''
                print(f"    {name:<25} Score MSE={m['mse']:.5f}  R²={m['r2']:.5f}{tag}")
        elif os.path.isfile(p['model']):
            print(f"\nDataset [{label}]: model found but no info JSON (re-run training).")
        else:
            print(f"\nDataset [{label}]: no model found — run train_winrate.py.")


if __name__ == '__main__':
    main()
