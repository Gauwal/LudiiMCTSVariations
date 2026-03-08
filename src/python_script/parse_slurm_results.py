"""Parse SLURM .out and .err files and build model-ready datasets.

Outputs two CSVs in src/python_script/:
  dataset_all.csv        – all successfully completed jobs
  dataset_notimeout.csv  – same but with games that hit maxMoves excluded

Each row contains only:
  variant_select, variant_simulation, variant_backprop, variant_finalmove
  winrate, moveTime, maxMoves
  game_* features (from game_properties.csv)
"""
import os
import re
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
RESULTS_DIR = os.path.join(REPO_ROOT, 'slurm_jobs', 'results')
GAME_PROPS = os.path.join(REPO_ROOT, 'game_properties.csv')

DATASET_ALL_OUT = os.path.join(HERE, 'dataset_all.csv')
DATASET_NOTIMEOUT_OUT = os.path.join(HERE, 'dataset_notimeout.csv')

COMPLETED_RE = re.compile(
    r'completed=(\d+)/(\d+),\s*wins=(\d+),\s*losses=(\d+),\s*draws=(\d+),\s*'
    r'failures=(\d+),\s*avgMoves=([0-9.]+)'
)
GAME_RE = re.compile(r'^Game:\s*(.+)$', re.IGNORECASE)
VARIANT_RE = re.compile(r'^Variant:\s*(.+)$', re.IGNORECASE)
META_RE = re.compile(r'moveTime=([0-9.]+)|gamesPerMatchup=(\d+)|maxMoves=(\d+)')


def _normalize(s: str) -> str:
    if not isinstance(s, str):
        return ''
    return re.sub(r'[^a-z0-9]', '', s.lower())


def _parse_out_file(path: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        'game': None, 'variant': None,
        'wins': None, 'completed': None, 'total_expected': None,
        'losses': None, 'draws': None, 'failures': None, 'avgMoves': None,
        'moveTime': None, 'maxMoves': None,
    }
    with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            m = GAME_RE.match(line)
            if m:
                data['game'] = m.group(1).strip()
                continue
            m = VARIANT_RE.match(line)
            if m:
                data['variant'] = m.group(1).strip()
                continue
            m = COMPLETED_RE.search(line)
            if m:
                # groups: 1=completed, 2=total_expected, 3=wins, 4=losses, 5=draws, 6=failures, 7=avgMoves
                data['completed'] = int(m.group(1))
                data['total_expected'] = int(m.group(2))
                data['wins'] = int(m.group(3))
                data['losses'] = int(m.group(4))
                data['draws'] = int(m.group(5))
                data['failures'] = int(m.group(6))
                data['avgMoves'] = float(m.group(7))
                continue
            for m in META_RE.finditer(line):
                if m.group(1) is not None:
                    data['moveTime'] = float(m.group(1))
                if m.group(3) is not None:
                    data['maxMoves'] = int(m.group(3))
    return data


def _find_game(norm: str, norm_to_game: Dict[str, str]) -> Optional[str]:
    if norm in norm_to_game:
        return norm_to_game[norm]
    for n, g in norm_to_game.items():
        if n.startswith(norm) or norm.startswith(n) or norm in n or n in norm:
            return g
    return None


def build_datasets(results_dir: str, game_props_path: str):
    """Parse all SLURM results and return (df_all, df_notimeout)."""
    games_df = pd.read_csv(game_props_path)
    game_feature_cols = [c for c in games_df.columns if c != 'game']
    games_df['_norm'] = games_df['game'].apply(_normalize)
    norm_to_game = dict(zip(games_df['_norm'], games_df['game']))

    # collect .out / .err pairs
    bases: Dict[str, Dict[str, str]] = {}
    for fname in os.listdir(results_dir):
        if fname.endswith('.out') or fname.endswith('.err'):
            base, ext = fname.rsplit('.', 1)
            bases.setdefault(base, {})[ext] = fname

    rows: List[Dict[str, Any]] = []
    skipped_err = skipped_parse = skipped_game = 0

    for base, parts in sorted(bases.items()):
        # skip jobs with non-empty .err
        err_file = parts.get('err')
        if err_file:
            err_path = os.path.join(results_dir, err_file)
            try:
                if os.path.getsize(err_path) > 0:
                    skipped_err += 1
                    continue
            except OSError:
                pass

        out_file = parts.get('out')
        if not out_file:
            continue
        out_path = os.path.join(results_dir, out_file)

        parsed = _parse_out_file(out_path)
        if (not parsed['game'] or parsed.get('wins') is None or
            (parsed.get('total_expected') is None and parsed.get('completed') is None)):
            skipped_parse += 1
            continue

        mapped_game = _find_game(_normalize(parsed['game']), norm_to_game)
        if mapped_game is None:
            skipped_game += 1
            continue

        props = games_df[games_df['game'] == mapped_game].iloc[0]

        v = parsed.get('variant') or ''
        v_parts = [p.strip() for p in v.split('|')]
        while len(v_parts) < 4:
            v_parts.append('')
        sel, sim, back, final = v_parts[:4]

        # compute winrate for the 'all' dataset: wins / total_expected
        total_expected = parsed.get('total_expected')
        completed = parsed.get('completed')
        failures = parsed.get('failures') or 0
        wins = parsed.get('wins') or 0
        if total_expected and total_expected > 0:
            winrate_all = wins / float(total_expected)
        else:
            # fallback to completed if total_expected missing
            winrate_all = wins / float(completed) if completed and completed > 0 else np.nan
        avg_moves = parsed.get('avgMoves')
        move_time = parsed.get('moveTime')
        max_moves = parsed.get('maxMoves')

        row: Dict[str, Any] = {
            'variant_select': sel,
            'variant_simulation': sim,
            'variant_backprop': back,
            'variant_finalmove': final,
            # store the 'all' winrate by default; the no-timeout dataset will recompute
            'winrate': winrate_all,
            'moveTime': move_time,
            'maxMoves': max_moves,
            'avgMoves': avg_moves,   # kept internally for timeout filtering; dropped from final CSVs
            # keep parsed counts for later recomputation of no-timeout winrate
            'parsed_wins': wins,
            'parsed_completed': completed,
            'parsed_total_expected': total_expected,
            'parsed_failures': failures,
        }
        for col in game_feature_cols:
            row[f'game_{col}'] = props[col]

        rows.append(row)

    df_all = pd.DataFrame(rows)

    # determine timeout rows: avgMoves >= maxMoves
    timeout_mask = pd.Series([False] * len(df_all))
    if 'avgMoves' in df_all.columns and 'maxMoves' in df_all.columns:
        timeout_mask = df_all['avgMoves'] >= df_all['maxMoves'].fillna(float('inf'))

    export_cols = [c for c in df_all.columns if c != 'avgMoves']
    df_export_all = df_all[export_cols].copy()

    # Build no-timeout dataset: exclude timeouts and recompute winrate ignoring failures/timeouts
    df_nt = df_all[~timeout_mask].copy()
    # recompute winrate excluding failures (timeouts) using parsed totals
    if 'parsed_wins' in df_nt.columns and 'parsed_total_expected' in df_nt.columns and 'parsed_failures' in df_nt.columns:
        def _recalc_winrate(row):
            tot = row.get('parsed_total_expected')
            fail = row.get('parsed_failures') or 0
            w = row.get('parsed_wins') or 0
            denom = (tot if (tot is not None and tot > 0) else row.get('parsed_completed'))
            if denom is None or denom <= 0:
                return np.nan
            non_t = denom - fail
            if non_t <= 0:
                return np.nan
            return float(w) / float(non_t)

        df_nt['winrate'] = df_nt.apply(_recalc_winrate, axis=1)
        # drop rows where all games were timeouts (winrate became NaN)
        df_nt = df_nt[df_nt['winrate'].notna()]
    else:
        # if parsed totals not present, fallback: use same as all
        df_nt['winrate'] = df_nt['winrate']

    # drop internal avgMoves/parsed-only columns before export
    drop_cols = [c for c in ['avgMoves', 'parsed_wins', 'parsed_completed', 'parsed_total_expected', 'parsed_failures'] if c in df_export_all.columns]
    df_export_all = df_export_all.drop(columns=drop_cols, errors='ignore')
    # ensure notimeout export uses same exported columns (without parsed-only cols)
    df_notimeout = df_nt[export_cols].drop(columns=[c for c in drop_cols if c in export_cols], errors='ignore')

    print(f"Total rows parsed : {len(df_all)}")
    print(f"  Skipped (err)   : {skipped_err}")
    print(f"  Skipped (parse) : {skipped_parse}")
    print(f"  Skipped (game)  : {skipped_game}")
    print(f"  Timeout games   : {timeout_mask.sum()}")
    print(f"  All dataset     : {len(df_export_all)} rows")
    print(f"  No-timeout set  : {len(df_notimeout)} rows")

    return df_export_all, df_notimeout


def main():
    if not os.path.isdir(RESULTS_DIR):
        raise SystemExit(f"Results directory not found: {RESULTS_DIR}")
    if not os.path.isfile(GAME_PROPS):
        raise SystemExit(f"game_properties.csv not found: {GAME_PROPS}")

    df_all, df_notimeout = build_datasets(RESULTS_DIR, GAME_PROPS)

    df_all.to_csv(DATASET_ALL_OUT, index=False)
    df_notimeout.to_csv(DATASET_NOTIMEOUT_OUT, index=False)

    print(f"\nSaved: {DATASET_ALL_OUT}")
    print(f"Saved: {DATASET_NOTIMEOUT_OUT}")


if __name__ == '__main__':
    main()
