"""Parse SLURM .out and .err files and build model-ready datasets.

Timeout detection
-----------------
Each line matching "Game exceeded time limit" in a job's .err file counts
as one timed-out game within that job's 30-game matchup.  Timed-out games
were recorded as draws by the runner but are **not real draws**, so they are
excluded from all metrics:

  effective_total  = total - n_timeouts
  effective_draws  = draws - n_timeouts    (timeout games inflate draw count)
  winrate          = wins / effective_total
  drawrate         = effective_draws / effective_total
  score            = (wins + 0.5 * effective_draws) / effective_total

Outputs two CSVs in src/python_script/:
  dataset_all.csv        – all jobs with at least one non-timeout game
  dataset_notimeout.csv  – only jobs with zero timeouts

Each row contains:
  variant_select, variant_simulation, variant_backprop, variant_finalmove,
  winrate, drawrate, score, n_timeouts, moveTime, maxMoves,
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
DATASET_RAW_OUT = os.path.join(HERE, 'dataset_raw.csv')

COMPLETED_RE = re.compile(
    r'completed=(\d+)/(\d+),\s*wins=(\d+),\s*losses=(\d+),\s*draws=(\d+),\s*'
    r'failures=(\d+),\s*avgMoves=([0-9.]+)'
)
GAME_RE = re.compile(r'^Game:\s*(.+)$', re.IGNORECASE)
VARIANT_RE = re.compile(r'^Variant:\s*(.+)$', re.IGNORECASE)
META_RE = re.compile(r'moveTime=([0-9.]+)|gamesPerMatchup=(\d+)|maxMoves=(\d+)')
TIMEOUT_RE = re.compile(r'Game exceeded time limit', re.IGNORECASE)


def _normalize(s: str) -> str:
    if not isinstance(s, str):
        return ''
    return re.sub(r'[^a-z0-9]', '', s.lower())


def _parse_out_file(path: str) -> Dict[str, Any]:
    """Parse a single .out file and extract game name, variant, result counts, and meta.

    Robust against wrapped lines in SLURM output by using full-text regexes
    instead of strict line-local parsing for result counters.
    """
    data: Dict[str, Any] = {
        'game': None, 'variant': None,
        'wins': None, 'completed': None, 'total_expected': None,
        'losses': None, 'draws': None, 'failures': None, 'avgMoves': None,
        'moveTime': None, 'maxMoves': None,
    }
    with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
        text = fh.read()

    # Per-line anchors for headers
    m_game = re.search(r'(?im)^\s*Game:\s*(.+?)\s*$', text)
    if m_game:
        data['game'] = m_game.group(1).strip()

    m_variant = re.search(r'(?im)^\s*Variant:\s*(.+?)\s*$', text)
    if m_variant:
        data['variant'] = m_variant.group(1).strip()

    # Tolerant full-text parsing for result counters (supports wrapped lines)
    m_completed = re.search(r'completed\s*=\s*(\d+)\s*/\s*(\d+)', text, re.IGNORECASE)
    if m_completed:
        data['completed'] = int(m_completed.group(1))
        data['total_expected'] = int(m_completed.group(2))

    m_wins = re.search(r'wins\s*=\s*(\d+)', text, re.IGNORECASE)
    if m_wins:
        data['wins'] = int(m_wins.group(1))

    m_losses = re.search(r'losses\s*=\s*(\d+)', text, re.IGNORECASE)
    if m_losses:
        data['losses'] = int(m_losses.group(1))

    m_draws = re.search(r'draws\s*=\s*(\d+)', text, re.IGNORECASE)
    if m_draws:
        data['draws'] = int(m_draws.group(1))

    m_failures = re.search(r'failures\s*=\s*(\d+)', text, re.IGNORECASE)
    if m_failures:
        data['failures'] = int(m_failures.group(1))

    m_avg = re.search(r'avgMoves\s*=\s*([0-9.]+)', text, re.IGNORECASE)
    if m_avg:
        data['avgMoves'] = float(m_avg.group(1))

    for m in META_RE.finditer(text):
        if m.group(1) is not None:
            data['moveTime'] = float(m.group(1))
        if m.group(3) is not None:
            data['maxMoves'] = int(m.group(3))

    return data


def build_raw_dataset(results_dir: str) -> pd.DataFrame:
    """Parse all .out/.err pairs into a raw dataset with minimal processing.

    This keeps parseable and non-parseable jobs, and does not compute derived
    rates/scores. Useful for diagnostics.
    """
    bases: Dict[str, Dict[str, str]] = {}
    for fname in os.listdir(results_dir):
        if fname.endswith('.out') or fname.endswith('.err'):
            base, ext = fname.rsplit('.', 1)
            bases.setdefault(base, {})[ext] = fname

    rows: List[Dict[str, Any]] = []
    for base, parts in sorted(bases.items()):
        out_file = parts.get('out')
        err_file = parts.get('err')
        out_path = os.path.join(results_dir, out_file) if out_file else None
        err_path = os.path.join(results_dir, err_file) if err_file else None
        out_exists = bool(out_path and os.path.isfile(out_path))
        err_exists = bool(err_path and os.path.isfile(err_path))
        out_size = os.path.getsize(out_path) if out_exists else 0
        err_size = os.path.getsize(err_path) if err_exists else 0

        parsed: Dict[str, Any] = {
            'game': None,
            'variant': None,
            'wins': None,
            'losses': None,
            'draws': None,
            'failures': None,
            'completed': None,
            'total_expected': None,
            'avgMoves': None,
            'moveTime': None,
            'maxMoves': None,
        }
        if out_exists:
            parsed = _parse_out_file(out_path)

        n_timeouts = _count_timeouts_in_err(err_path) if err_path else 0
        has_game = bool(parsed.get('game'))
        has_variant = bool(parsed.get('variant'))
        has_wins = parsed.get('wins') is not None
        has_total = (parsed.get('total_expected') is not None or parsed.get('completed') is not None)
        parse_ok = bool(
            has_game and has_wins and has_total
        )

        if parse_ok:
            diagnostic_reason = 'complete'
        elif has_game and not has_wins and not has_total:
            diagnostic_reason = 'started_no_result_summary'
        elif not out_exists:
            diagnostic_reason = 'missing_out_file'
        elif out_size == 0:
            diagnostic_reason = 'empty_out_file'
        elif not has_game:
            diagnostic_reason = 'missing_game_header'
        elif not has_variant:
            diagnostic_reason = 'missing_variant_header'
        elif not has_wins and has_total:
            diagnostic_reason = 'missing_wins_only'
        elif has_wins and not has_total:
            diagnostic_reason = 'missing_total_only'
        else:
            diagnostic_reason = 'other_partial_parse'

        rows.append({
            'job': base,
            'out_file': out_file,
            'err_file': err_file,
            'out_exists': out_exists,
            'err_exists': err_exists,
            'out_size_bytes': out_size,
            'err_size_bytes': err_size,
            'parse_ok': parse_ok,
            'has_game': has_game,
            'has_variant': has_variant,
            'has_wins': has_wins,
            'has_total': has_total,
            'diagnostic_reason': diagnostic_reason,
            'n_timeouts': n_timeouts,
            **parsed,
        })

    return pd.DataFrame(rows)


def _count_timeouts_in_err(path: str) -> int:
    """Count 'Game exceeded time limit' lines in an .err file."""
    if not os.path.isfile(path):
        return 0
    try:
        if os.path.getsize(path) == 0:
            return 0
    except OSError:
        return 0
    count = 0
    with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
        for line in fh:
            if TIMEOUT_RE.search(line):
                count += 1
    return count


def _find_game(norm: str, norm_to_game: Dict[str, str]) -> Optional[str]:
    """Find the canonical game name from a normalised query string."""
    if norm in norm_to_game:
        return norm_to_game[norm]
    for n, g in norm_to_game.items():
        if n.startswith(norm) or norm.startswith(n) or norm in n or n in norm:
            return g
    return None


def build_datasets(results_dir: str, game_props_path: str):
    """Parse all SLURM results and return (df_all, df_notimeout).

    Timeout detection uses .err files: each 'Game exceeded time limit' line
    is one timed-out game.  Those games are excluded from win/draw/loss rates
    and from the score metric.
    """
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
    timeout_report: List[Dict[str, Any]] = []
    skipped_parse = skipped_game = skipped_all_timeout = 0
    skipped_incomplete = 0
    skipped_missing_game = skipped_missing_wins = skipped_missing_total = 0
    total_timeout_games = 0

    for base, parts in sorted(bases.items()):
        out_file = parts.get('out')
        if not out_file:
            continue
        out_path = os.path.join(results_dir, out_file)

        # Count timeouts from .err file
        err_file = parts.get('err')
        n_timeouts = 0
        if err_file:
            n_timeouts = _count_timeouts_in_err(
                os.path.join(results_dir, err_file)
            )

        parsed = _parse_out_file(out_path)
        missing_game = not parsed['game']
        missing_wins = parsed.get('wins') is None
        missing_total = (parsed.get('total_expected') is None and parsed.get('completed') is None)

        # Most common non-parse case: job started but did not print final summary yet.
        if (not missing_game) and missing_wins and missing_total:
            skipped_incomplete += 1
            continue

        if missing_game or missing_wins or missing_total:
            skipped_parse += 1
            if missing_game:
                skipped_missing_game += 1
            if missing_wins:
                skipped_missing_wins += 1
            if missing_total:
                skipped_missing_total += 1
            continue

        mapped_game = _find_game(_normalize(parsed['game']), norm_to_game)
        if mapped_game is None:
            skipped_game += 1
            continue

        total_expected = parsed.get('total_expected') or parsed.get('completed') or 0
        wins = parsed.get('wins') or 0
        losses = parsed.get('losses') or 0
        draws = parsed.get('draws') or 0

        # Clamp n_timeouts: can't exceed draws (timeouts are recorded as draws)
        n_timeouts = min(n_timeouts, draws)
        total_timeout_games += n_timeouts

        # Record timeout report
        if n_timeouts > 0:
            timeout_report.append({
                'job': base,
                'game': parsed['game'],
                'variant': parsed.get('variant', ''),
                'n_timeouts': n_timeouts,
                'total': total_expected,
                'wins': wins, 'losses': losses, 'draws': draws,
            })

        # Compute timeout-adjusted metrics
        effective_total = total_expected - n_timeouts
        if effective_total <= 0:
            skipped_all_timeout += 1
            continue
        effective_draws = draws - n_timeouts

        winrate = wins / float(effective_total)
        drawrate = effective_draws / float(effective_total)
        score = (wins + 0.5 * effective_draws) / float(effective_total)

        props = games_df[games_df['game'] == mapped_game].iloc[0]

        v = parsed.get('variant') or ''
        v_parts = [p.strip() for p in v.split('|')]
        while len(v_parts) < 4:
            v_parts.append('')
        sel, sim, back, final = v_parts[:4]

        row: Dict[str, Any] = {
            'variant_select': sel,
            'variant_simulation': sim,
            'variant_backprop': back,
            'variant_finalmove': final,
            'winrate': winrate,
            'drawrate': drawrate,
            'score': score,
            'n_timeouts': n_timeouts,
            'moveTime': parsed.get('moveTime'),
            'maxMoves': parsed.get('maxMoves'),
        }
        for col in game_feature_cols:
            row[f'game_{col}'] = props[col]

        rows.append(row)

    df_all = pd.DataFrame(rows)

    # Notimeout dataset: only jobs with zero timeouts
    df_notimeout = df_all[df_all['n_timeouts'] == 0].copy()

    # ---- Summary ----
    print(f"Total jobs parsed  : {len(df_all) + skipped_parse + skipped_incomplete + skipped_game + skipped_all_timeout}")
    print(f"  Skipped (parse)  : {skipped_parse}")
    if skipped_parse:
        print(f"    - missing game     : {skipped_missing_game}")
        print(f"    - missing wins     : {skipped_missing_wins}")
        print(f"    - missing total    : {skipped_missing_total}")
    print(f"  Skipped (incomplete): {skipped_incomplete}")
    print(f"  Skipped (game)   : {skipped_game}")
    print(f"  Skipped (all TO) : {skipped_all_timeout}  (all games timed out)")
    print(f"  All dataset      : {len(df_all)} rows")
    print(f"  No-timeout set   : {len(df_notimeout)} rows")
    print(f"  Jobs with TO     : {len(timeout_report)}")
    print(f"  Total TO games   : {total_timeout_games}")

    # ---- Timeout report ----
    if timeout_report:
        print(f"\n{'=' * 70}")
        print("  TIMEOUT REPORT")
        print(f"{'=' * 70}")
        print(f"  {'Game':<25s} {'Variant':<40s} {'TO':>3s} {'W':>3s} {'L':>3s} {'D':>3s} {'Tot':>3s}")
        print(f"  {'-'*25} {'-'*40} {'-'*3} {'-'*3} {'-'*3} {'-'*3} {'-'*3}")
        for r in sorted(timeout_report, key=lambda x: -x['n_timeouts']):
            print(f"  {r['game']:<25s} {r['variant']:<40s} "
                  f"{r['n_timeouts']:3d} {r['wins']:3d} {r['losses']:3d} "
                  f"{r['draws']:3d} {r['total']:3d}")
        print(f"{'=' * 70}")

    return df_all, df_notimeout


def main():
    if not os.path.isdir(RESULTS_DIR):
        raise SystemExit(f"Results directory not found: {RESULTS_DIR}")
    if not os.path.isfile(GAME_PROPS):
        raise SystemExit(f"game_properties.csv not found: {GAME_PROPS}")

    df_all, df_notimeout = build_datasets(RESULTS_DIR, GAME_PROPS)
    df_raw = build_raw_dataset(RESULTS_DIR)

    df_all.to_csv(DATASET_ALL_OUT, index=False)
    df_notimeout.to_csv(DATASET_NOTIMEOUT_OUT, index=False)
    df_raw.to_csv(DATASET_RAW_OUT, index=False)

    print(f"\nSaved: {DATASET_ALL_OUT}")
    print(f"Saved: {DATASET_NOTIMEOUT_OUT}")
    print(f"Saved: {DATASET_RAW_OUT}")


if __name__ == '__main__':
    main()
