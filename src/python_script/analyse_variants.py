"""Analyse MCTS variant effectiveness across games.

Two main analyses:

1. **Games with no good method** — For each game (or custom game features),
   are there *any* MCTS variants that achieve a reasonable score?  If the
   best predicted score across all variant combos is below a threshold,
   the game is flagged as "no good method available".

2. **Globally weak methods** — For each individual variant component value
   (e.g. selection = 'UCB1'), check whether it ever appears among the
   top-k variants for any game.  Components that *never* rank in the top-k
   for any game are flagged as "globally weak".

Both analyses use the trained model's predictions (exhaustive search over
the variant catalogue for every game in game_properties.csv).

Usage:
    python analyse_variants.py                     # uses defaults
    python analyse_variants.py --label notimeout   # use notimeout model
    python analyse_variants.py --top-k 3 --threshold 0.3
"""

import argparse
import itertools
import json
import os
from collections import defaultdict
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from predict_winrate import (
    _load_model_artefacts,
    _load_catalogue,
    _load_game_properties,
    _build_feature_vector,
    _predict_score_from_pipeline,
    _variant_dict,
)

HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# Core: score every variant for every game
# ---------------------------------------------------------------------------

def _score_all_games(label: str) -> Tuple[pd.DataFrame, List[str], List[Tuple]]:
    """Build a (n_games × n_variants) score matrix.

    Returns
    -------
    score_df   : DataFrame with games as rows, variant combos as columns
    game_names : list of game names (row labels)
    all_combos : list of (select, simulation, backprop, finalmove) tuples (column labels)
    """
    pipeline, feature_names, multi_output = _load_model_artefacts(label)
    catalogue = _load_catalogue(label)
    games_df = _load_game_properties()

    selects     = catalogue.get('variant_select',     [])
    simulations = catalogue.get('variant_simulation', [])
    backprops   = catalogue.get('variant_backprop',   [])
    finalmoves  = catalogue.get('variant_finalmove',  [])

    all_combos: List[Tuple[str, str, str, str]] = list(
        itertools.product(selects, simulations, backprops, finalmoves)
    )

    game_names: List[str] = games_df['game'].tolist()
    all_scores = np.zeros((len(game_names), len(all_combos)))

    for gi, game_name in enumerate(game_names):
        game_row = games_df[games_df['game'] == game_name].iloc[0]
        rows = []
        for sel, sim, bp, fm in all_combos:
            vbc = _variant_dict(sel, sim, bp, fm)
            rows.append(_build_feature_vector(game_row, vbc, feature_names))
        X = np.vstack(rows)
        all_scores[gi, :] = _predict_score_from_pipeline(pipeline, X, multi_output)

    combo_labels = [
        f'{c[0]} | {c[1]} | {c[2]} | {c[3]}' for c in all_combos
    ]
    score_df = pd.DataFrame(all_scores, index=game_names, columns=combo_labels)
    return score_df, game_names, all_combos


# ---------------------------------------------------------------------------
# Analysis 1: games with no good method
# ---------------------------------------------------------------------------

def analyse_games_no_good_method(
    score_df: pd.DataFrame,
    threshold: float = 0.35,
) -> pd.DataFrame:
    """Find games where the best variant score is below the threshold.

    Returns a DataFrame with columns: game, best_score, best_variant, worst_score.
    """
    results = []
    for game in score_df.index:
        row = score_df.loc[game]
        best_idx = row.values.argmax()
        best_score = float(row.values[best_idx])
        best_var = row.index[best_idx]
        worst_score = float(row.values.min())
        spread = best_score - worst_score
        if best_score < threshold:
            results.append({
                'game': game,
                'best_score': best_score,
                'best_variant': best_var,
                'worst_score': worst_score,
                'spread': spread,
            })
    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values('best_score', ascending=True).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Analysis 2: globally weak variant components
# ---------------------------------------------------------------------------

def analyse_globally_weak_components(
    score_df: pd.DataFrame,
    all_combos: List[Tuple[str, str, str, str]],
    top_k: int = 3,
) -> Dict[str, List[Dict]]:
    """For each variant component value, check how often it appears in the top-k.

    Returns a dict mapping component name -> list of dicts for values that
    NEVER appear in any game's top-k.
    """
    combo_labels = list(score_df.columns)
    comp_names = ['select', 'simulation', 'backprop', 'finalmove']

    # Count how many games each component value appears in the top-k for
    comp_topk_count: Dict[str, Dict[str, int]] = {
        c: defaultdict(int) for c in comp_names
    }
    comp_all_values: Dict[str, set] = {c: set() for c in comp_names}

    for ci, comp in enumerate(comp_names):
        for combo in all_combos:
            comp_all_values[comp].add(combo[ci])

    for game in score_df.index:
        row = score_df.loc[game].values
        top_indices = np.argsort(row)[::-1][:top_k]
        for idx in top_indices:
            combo = all_combos[idx]
            for ci, comp in enumerate(comp_names):
                comp_topk_count[comp][combo[ci]] += 1

    weak: Dict[str, List[Dict]] = {}
    for comp in comp_names:
        weak_values = []
        for val in sorted(comp_all_values[comp]):
            count = comp_topk_count[comp].get(val, 0)
            if count == 0:
                weak_values.append({'value': val, 'top_k_appearances': 0})
        if weak_values:
            weak[comp] = weak_values

    return weak


# ---------------------------------------------------------------------------
# Analysis 3: full component ranking
# ---------------------------------------------------------------------------

def analyse_component_rankings(
    score_df: pd.DataFrame,
    all_combos: List[Tuple[str, str, str, str]],
    top_k: int = 3,
) -> Dict[str, pd.DataFrame]:
    """Rank every component value by how often it appears in the top-k across all games.

    Returns a dict mapping component name -> DataFrame with columns:
    value, top_k_count, top_k_pct, avg_score_when_used.
    """
    comp_names = ['select', 'simulation', 'backprop', 'finalmove']
    n_games = len(score_df)

    comp_topk_count: Dict[str, Dict[str, int]] = {c: defaultdict(int) for c in comp_names}
    comp_score_sums: Dict[str, Dict[str, float]] = {c: defaultdict(float) for c in comp_names}
    comp_score_counts: Dict[str, Dict[str, int]] = {c: defaultdict(int) for c in comp_names}
    comp_all_values: Dict[str, set] = {c: set() for c in comp_names}

    for ci, comp in enumerate(comp_names):
        for combo in all_combos:
            comp_all_values[comp].add(combo[ci])

    # Accumulate average score across all games for each component value
    for game in score_df.index:
        row = score_df.loc[game].values
        top_indices = np.argsort(row)[::-1][:top_k]
        for idx in top_indices:
            combo = all_combos[idx]
            for ci, comp in enumerate(comp_names):
                comp_topk_count[comp][combo[ci]] += 1

        # Average score per component value (across all combos for this game)
        for vi, combo in enumerate(all_combos):
            for ci, comp in enumerate(comp_names):
                comp_score_sums[comp][combo[ci]] += row[vi]
                comp_score_counts[comp][combo[ci]] += 1

    result = {}
    for comp in comp_names:
        rows = []
        for val in sorted(comp_all_values[comp]):
            count = comp_topk_count[comp].get(val, 0)
            total = comp_score_counts[comp].get(val, 1)
            avg = comp_score_sums[comp].get(val, 0.0) / total if total > 0 else 0.0
            rows.append({
                'value': val,
                'top_k_count': count,
                'top_k_pct': count / n_games * 100 if n_games > 0 else 0,
                'avg_score': avg,
            })
        df = pd.DataFrame(rows).sort_values('top_k_count', ascending=False).reset_index(drop=True)
        result[comp] = df
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Analyse MCTS variant effectiveness')
    parser.add_argument('--label', default='all', help='Model label: all (default) or notimeout')
    parser.add_argument('--top-k', type=int, default=3, help='Top-k for ranking (default 3)')
    parser.add_argument('--threshold', type=float, default=0.35,
                        help='Score threshold below which a game is flagged as having no good method')
    args = parser.parse_args()

    print(f"Building score matrix for all games (label={args.label})...")
    score_df, game_names, all_combos = _score_all_games(args.label)
    print(f"  {len(game_names)} games × {len(all_combos)} variant combinations\n")

    # --- Analysis 1: games with no good method ---
    print(f"{'=' * 70}")
    print(f"  GAMES WITH NO GOOD METHOD  (best score < {args.threshold})")
    print(f"{'=' * 70}")
    no_good = analyse_games_no_good_method(score_df, threshold=args.threshold)
    if no_good.empty:
        print(f"  All games have at least one variant scoring >= {args.threshold}")
    else:
        print(f"  {len(no_good)} / {len(game_names)} games have no variant scoring >= {args.threshold}\n")
        print(f"  {'Game':<30s} {'Best':>6s} {'Worst':>6s} {'Spread':>6s}  Best variant")
        print(f"  {'-'*30} {'-'*6} {'-'*6} {'-'*6}  {'-'*40}")
        for _, r in no_good.iterrows():
            print(f"  {r['game']:<30s} {r['best_score']:6.3f} {r['worst_score']:6.3f} "
                  f"{r['spread']:6.3f}  {r['best_variant']}")
    print()

    # --- Analysis 2: globally weak components ---
    print(f"{'=' * 70}")
    print(f"  GLOBALLY WEAK COMPONENTS  (never in top-{args.top_k} for any game)")
    print(f"{'=' * 70}")
    weak = analyse_globally_weak_components(score_df, all_combos, top_k=args.top_k)
    if not weak:
        print(f"  Every component value appears in the top-{args.top_k} for at least one game.")
    else:
        for comp, values in weak.items():
            val_list = ', '.join(v['value'] for v in values)
            print(f"  {comp:<12s}: {val_list}")
    print()

    # --- Analysis 3: full component ranking ---
    print(f"{'=' * 70}")
    print(f"  COMPONENT RANKINGS  (by top-{args.top_k} appearances across {len(game_names)} games)")
    print(f"{'=' * 70}")
    rankings = analyse_component_rankings(score_df, all_combos, top_k=args.top_k)
    for comp, df in rankings.items():
        print(f"\n  [{comp}]")
        print(f"  {'Value':<25s} {'Top-k count':>11s} {'Top-k %':>8s} {'Avg score':>10s}")
        print(f"  {'-'*25} {'-'*11} {'-'*8} {'-'*10}")
        for _, r in df.iterrows():
            print(f"  {r['value']:<25s} {r['top_k_count']:11.0f} {r['top_k_pct']:7.1f}% {r['avg_score']:10.4f}")
    print()

    # --- Summary stats ---
    print(f"{'=' * 70}")
    print(f"  SCORE DISTRIBUTION ACROSS ALL GAMES")
    print(f"{'=' * 70}")
    best_per_game = score_df.max(axis=1)
    worst_per_game = score_df.min(axis=1)
    mean_per_game = score_df.mean(axis=1)
    print(f"  Best score per game  : mean={best_per_game.mean():.3f}  "
          f"min={best_per_game.min():.3f}  max={best_per_game.max():.3f}")
    print(f"  Worst score per game : mean={worst_per_game.mean():.3f}  "
          f"min={worst_per_game.min():.3f}  max={worst_per_game.max():.3f}")
    print(f"  Mean score per game  : mean={mean_per_game.mean():.3f}  "
          f"min={mean_per_game.min():.3f}  max={mean_per_game.max():.3f}")
    print(f"  Avg spread (best-worst): {(best_per_game - worst_per_game).mean():.3f}")
    print()


if __name__ == '__main__':
    main()
