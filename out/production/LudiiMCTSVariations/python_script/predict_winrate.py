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
predict_score(game_name, select, simulation, backprop, finalmove, label) -> float
    Predicts the score for a (game, variant) pair looked up by game name.

predict_best_variant(game_name, label, top_k) -> dict
    Exhaustively evaluates all variant combinations for a game.

predict_score_from_features(game_features, select, simulation, backprop, finalmove, label) -> float
    Same as predict_score but accepts a dict of game features instead of a name.

predict_best_variant_from_features(game_features, label, top_k) -> dict
    Same as predict_best_variant but accepts a dict of game features.
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

    ``game_row`` can be a pd.Series from game_properties.csv or a dict-like
    object mapping column names (without the 'game\\_' prefix) to values.
    """
    x_vals: List[float] = []
    for feat in feature_names:
        if feat.startswith('game_'):
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


def _game_features_to_series(game_features: Dict[str, float]) -> pd.Series:
    """Convert a user-supplied game-features dict to a Series usable by _build_feature_vector.

    Keys may be supplied with or without the 'game\\_' prefix — both are accepted.
    """
    cleaned: Dict[str, float] = {}
    for k, v in game_features.items():
        key = k[len('game_'):] if k.startswith('game_') else k
        cleaned[key] = v
    return pd.Series(cleaned)


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

    Returns np.ndarray of shape (n_samples,) with score values clipped to [0, 1].
    """
    raw = pipeline.predict(x)
    if multi_output and raw.ndim == 2 and raw.shape[1] >= 2:
        wr = np.clip(raw[:, 0], 0.0, 1.0)
        dr = np.clip(raw[:, 1], 0.0, 1.0)
        scores = np.clip(wr + 0.5 * dr, 0.0, 1.0)
    else:
        scores = np.clip(raw.ravel(), 0.0, 1.0)
    return scores


def _load_model_artefacts(label: str):
    """Load and return (pipeline, feature_names, multi_output) for the given label."""
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
    return pipeline, feature_names, multi_output


def _load_catalogue(label: str) -> Dict[str, List[str]]:
    """Load and return the variant catalogue for the given label."""
    paths = _model_paths(label)
    if not os.path.isfile(paths['catalogue']):
        raise FileNotFoundError(
            f"Variant catalogue for label='{label}' not found. "
            "Run `python train_winrate.py` first."
        )
    with open(paths['catalogue'], 'r', encoding='utf-8') as fh:
        return json.load(fh)


def _variant_dict(select: str, simulation: str, backprop: str, finalmove: str) -> Dict[str, str]:
    """Build a variant-by-component dict from the four component strings."""
    return {
        'variant_select':     select,
        'variant_simulation': simulation,
        'variant_backprop':   backprop,
        'variant_finalmove':  finalmove,
    }


# ---------------------------------------------------------------------------
# Public API — game name based
# ---------------------------------------------------------------------------

def predict_score(
    game_name: str,
    select: str,
    simulation: str,
    backprop: str,
    finalmove: str,
    label: str = 'all',
) -> float:
    """Return the predicted score for a (game, variant) pair.

    Parameters
    ----------
    game_name : str
        Game name as it appears in game_properties.csv (partial match supported).
    select, simulation, backprop, finalmove : str
        The four MCTS variant components, e.g. 'UCB1', 'MAST', 'MonteCarlo', 'Robust'.
    label : str
        Which trained model to use: 'all' (default) or 'notimeout'.

    Returns
    -------
    float   Predicted score clipped to [0, 1].
    """
    pipeline, feature_names, multi_output = _load_model_artefacts(label)
    games_df = _load_game_properties()
    game_row = _get_game_row(game_name, games_df)
    vbc = _variant_dict(select, simulation, backprop, finalmove)
    x = _build_feature_vector(game_row, vbc, feature_names).reshape(1, -1)
    return float(_predict_score_from_pipeline(pipeline, x, multi_output)[0])


def predict_best_variant(
    game_name: str,
    label: str = 'all',
    top_k: int = 5,
) -> Dict:
    """Find the best MCTS variant for a game by exhaustive search over the catalogue.

    Returns
    -------
    dict with keys 'game', 'label', 'best_variant' (dict with 4 components),
    'best_score', 'top_k' (list of dicts), 'n_evaluated'.
    """
    pipeline, feature_names, multi_output = _load_model_artefacts(label)
    catalogue = _load_catalogue(label)
    games_df = _load_game_properties()
    game_row = _get_game_row(game_name, games_df)
    resolved_name = str(game_row.get('game', game_name))

    return _exhaustive_search(
        game_row, resolved_name, pipeline, feature_names, multi_output,
        catalogue, label, top_k,
    )


# ---------------------------------------------------------------------------
# Public API — game features based (no game name lookup)
# ---------------------------------------------------------------------------

def predict_score_from_features(
    game_features: Dict[str, float],
    select: str,
    simulation: str,
    backprop: str,
    finalmove: str,
    label: str = 'all',
) -> float:
    """Predict score from raw game feature values (no game name lookup).

    Parameters
    ----------
    game_features : dict
        Mapping of game property names to numeric values.  Keys can use
        either raw names ('numCells') or prefixed names ('game_numCells').
        Missing features will be treated as NaN.
    select, simulation, backprop, finalmove : str
        The four MCTS variant components.
    label : str
        Which trained model to use.

    Returns
    -------
    float   Predicted score clipped to [0, 1].
    """
    pipeline, feature_names, multi_output = _load_model_artefacts(label)
    game_row = _game_features_to_series(game_features)
    vbc = _variant_dict(select, simulation, backprop, finalmove)
    x = _build_feature_vector(game_row, vbc, feature_names).reshape(1, -1)
    return float(_predict_score_from_pipeline(pipeline, x, multi_output)[0])


def predict_best_variant_from_features(
    game_features: Dict[str, float],
    label: str = 'all',
    top_k: int = 5,
) -> Dict:
    """Find the best MCTS variant for a set of game features by exhaustive search.

    Parameters
    ----------
    game_features : dict
        Mapping of game property names to numeric values (see predict_score_from_features).
    label : str
        Which trained model to use.
    top_k : int
        Number of top combinations to return.

    Returns
    -------
    dict with keys 'game', 'label', 'best_variant', 'best_score', 'top_k', 'n_evaluated'.
    """
    pipeline, feature_names, multi_output = _load_model_artefacts(label)
    catalogue = _load_catalogue(label)
    game_row = _game_features_to_series(game_features)

    return _exhaustive_search(
        game_row, '(custom features)', pipeline, feature_names, multi_output,
        catalogue, label, top_k,
    )


# ---------------------------------------------------------------------------
# Shared exhaustive search
# ---------------------------------------------------------------------------

def _exhaustive_search(
    game_row,
    game_display_name: str,
    pipeline,
    feature_names: List[str],
    multi_output: bool,
    catalogue: Dict[str, List[str]],
    label: str,
    top_k: int,
) -> Dict:
    """Score every variant combo and return the top-k."""
    selects     = catalogue.get('variant_select',     [])
    simulations = catalogue.get('variant_simulation', [])
    backprops   = catalogue.get('variant_backprop',   [])
    finalmoves  = catalogue.get('variant_finalmove',  [])

    all_combos: List[Tuple[str, str, str, str]] = list(
        itertools.product(selects, simulations, backprops, finalmoves)
    )
    rows: List[np.ndarray] = []
    for sel, sim, bp, fm in all_combos:
        vbc = _variant_dict(sel, sim, bp, fm)
        rows.append(_build_feature_vector(game_row, vbc, feature_names))

    X_all = np.vstack(rows)
    preds = _predict_score_from_pipeline(pipeline, X_all, multi_output)

    order = np.argsort(preds)[::-1]
    ranked = []
    for i in order[:top_k]:
        sel, sim, bp, fm = all_combos[i]
        ranked.append({
            'select': sel, 'simulation': sim,
            'backprop': bp, 'finalmove': fm,
            'score': float(preds[i]),
        })

    best = all_combos[order[0]]
    return {
        'game':         game_display_name,
        'label':        label,
        'best_variant': {
            'select': best[0], 'simulation': best[1],
            'backprop': best[2], 'finalmove': best[3],
        },
        'best_score':   float(preds[order[0]]),
        'top_k':        ranked,
        'n_evaluated':  len(all_combos),
    }


# ---------------------------------------------------------------------------
# Entry point
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
