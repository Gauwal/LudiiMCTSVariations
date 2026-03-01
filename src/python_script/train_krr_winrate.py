"""Train Kernel Ridge Regression to predict win rate from game properties and variant tokens.

- Scans `slurm_jobs/results` for .out/.err pairs
- Skips jobs with errors (.err non-empty)
- Parses .out files for Game, Variant, and Completed line (wins/games)
- Joins with `game_properties.csv` on `game` name
- Encodes variant tokens, scales numeric features
- Trains Kernel Ridge Regression on a 90/10 split and reports MSE, MAE, R2
- Saves model and scaler to `src/python_script`
"""
import os
import re
import json
from typing import Dict, Any, List, Tuple

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.kernel_ridge import KernelRidge
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import joblib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
RESULTS_DIR = os.path.join(REPO_ROOT, 'slurm_jobs', 'results')
GAME_PROPS = os.path.join(REPO_ROOT, 'game_properties.csv')

MODEL_OUT = os.path.join(HERE, 'krr_winrate_model.joblib')
SCALER_OUT = os.path.join(HERE, 'krr_scaler.joblib')
DATASET_OUT = os.path.join(HERE, 'krr_dataset.csv')

COMPLETED_RE = re.compile(r'completed=(\d+)/(\d+),\s*wins=(\d+),\s*losses=(\d+),\s*draws=(\d+),\s*failures=(\d+),\s*avgMoves=([0-9.]+)')
GAME_RE = re.compile(r'^Game:\s*(.+)$', re.IGNORECASE)
VARIANT_RE = re.compile(r'^Variant:\s*(.+)$', re.IGNORECASE)
META_RE = re.compile(r'moveTime=([0-9.]+)|gamesPerMatchup=(\d+)|maxMoves=(\d+)|cpus=(\d+)|mem=([^,\s]+)')


def parse_out_file(path: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {'game': None, 'variant': None, 'wins': None, 'games': None, 'avgMoves': None}

    with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            gm = GAME_RE.match(line)
            if gm:
                data['game'] = gm.group(1).strip()
                continue
            vm = VARIANT_RE.match(line)
            if vm:
                data['variant'] = vm.group(1).strip()
                continue
            cm = COMPLETED_RE.search(line)
            if cm:
                completed = int(cm.group(1))
                total_expected = int(cm.group(2))
                wins = int(cm.group(3))
                avg_moves = float(cm.group(7))
                data['wins'] = wins
                data['games'] = completed
                data['avgMoves'] = avg_moves
                continue
    return data


def normalize_name(s: str) -> str:
    if not isinstance(s, str):
        return ''
    return re.sub(r'[^a-z0-9]', '', s.lower())


def build_dataset(results_dir: str, game_props_path: str) -> pd.DataFrame:
    # load game properties
    games_df = pd.read_csv(game_props_path)
    games_df['_norm'] = games_df['game'].apply(normalize_name)
    norm_to_game = dict(zip(games_df['_norm'], games_df['game']))

    files = os.listdir(results_dir)
    bases = {}
    for f in files:
        if f.endswith('.out') or f.endswith('.err'):
            base = f.rsplit('.', 1)[0]
            bases.setdefault(base, {})[f.rsplit('.', 1)[1]] = f

    rows: List[Dict[str, Any]] = []
    for base, parts in sorted(bases.items()):
        err_file = parts.get('err')
        out_file = parts.get('out')
        # skip if err exists and is non-empty
        if err_file:
            err_path = os.path.join(results_dir, err_file)
            try:
                if os.path.getsize(err_path) > 0:
                    continue
            except OSError:
                pass
        if not out_file:
            continue
        out_path = os.path.join(results_dir, out_file)
        parsed = parse_out_file(out_path)
        if not parsed['game'] or parsed['wins'] is None or parsed['games'] is None:
            continue
        # map game name to game_properties entry
        norm = normalize_name(parsed['game'])
        mapped_game = norm_to_game.get(norm)
        if mapped_game is None:
            # try fuzzy match: startswith or contains
            found = None
            for n, g in norm_to_game.items():
                if n == norm or n.startswith(norm) or norm.startswith(n) or n.find(norm) >= 0 or norm.find(n) >= 0:
                    found = g
                    break
            if found:
                mapped_game = found
            else:
                # skip if no mapping
                continue
        # collect game properties
        props = games_df[games_df['game'] == mapped_game].iloc[0].to_dict()

        # parse meta info from the out file (moveTime, gamesPerMatchup, maxMoves, cpus, mem)
        meta = {'moveTime': None, 'gamesPerMatchup': None, 'maxMoves': None, 'cpus': None, 'mem': None}
        try:
            with open(out_path, 'r', encoding='utf-8', errors='ignore') as fh:
                txt = fh.read()
                for m in META_RE.finditer(txt):
                    if m.group(1):
                        meta['moveTime'] = float(m.group(1))
                    if m.group(2):
                        meta['gamesPerMatchup'] = int(m.group(2))
                    if m.group(3):
                        meta['maxMoves'] = int(m.group(3))
                    if m.group(4):
                        meta['cpus'] = int(m.group(4))
                    if m.group(5):
                        meta['mem'] = m.group(5)
        except Exception:
            pass

        # split variant into four components: selection | simulation | backprop | finalmove
        v = parsed.get('variant') or ''
        parts = [p.strip() for p in v.split('|')]
        # pad to 4
        while len(parts) < 4:
            parts.append('')
        sel, sim, back, final = parts[:4]

        row = {
            'job_base': base,
            'game': mapped_game,
            'variant': parsed['variant'],
            'variant_select': sel,
            'variant_simulation': sim,
            'variant_backprop': back,
            'variant_finalmove': final,
            'wins': parsed['wins'],
            'games': parsed['games'],
            'winrate': parsed['wins'] / parsed['games'] if parsed['games'] > 0 else np.nan,
            'avgMoves': parsed.get('avgMoves'),
            'moveTime': meta.get('moveTime'),
            'gamesPerMatchup': meta.get('gamesPerMatchup'),
            'maxMoves': meta.get('maxMoves'),
            'cpus': meta.get('cpus'),
            'mem': meta.get('mem')
        }
        # attach numeric properties from game_properties with prefix
        for col, val in props.items():
            if col == 'game' or col == '_norm':
                continue
            row[f'game_{col}'] = val
        rows.append(row)

    df = pd.DataFrame(rows)
    return df


def prepare_features(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    # numeric game properties columns start with game_
    num_cols = [c for c in df.columns if c.startswith('game_')]
    X_num = df[num_cols].astype(float).fillna(0).values

    # variant tokens
    df['variant'] = df['variant'].fillna('')
    tokens = df['variant'].str.split('\s*\|\s*')
    # build token set
    token_set = set()
    for t in tokens:
        for tok in t:
            if tok:
                token_set.add(tok)
    token_list = sorted(token_set)
    X_tokens = np.zeros((len(df), len(token_list)), dtype=float)
    for i, toks in enumerate(tokens):
        for tok in toks:
            if tok and tok in token_list:
                X_tokens[i, token_list.index(tok)] = 1.0

    X = np.hstack([X_num, X_tokens])
    y = df['winrate'].values.astype(float)
    feature_names = num_cols + token_list
    return X, y, feature_names


def train_and_evaluate(X: np.ndarray, y: np.ndarray):
    # 90/10 split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.1, random_state=42)

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    model = KernelRidge(kernel='rbf', alpha=1.0)
    model.fit(X_train_s, y_train)

    y_pred = model.predict(X_test_s)
    mse = mean_squared_error(y_test, y_pred)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    return model, scaler, {'mse': float(mse), 'mae': float(mae), 'r2': float(r2), 'n_samples': len(y)}


def main():
    if not os.path.isdir(RESULTS_DIR):
        raise SystemExit(f"Results dir not found: {RESULTS_DIR}")
    if not os.path.isfile(GAME_PROPS):
        raise SystemExit(f"Game properties file not found: {GAME_PROPS}")

    df = build_dataset(RESULTS_DIR, GAME_PROPS)
    if df.empty:
        raise SystemExit("No usable data parsed from results")

    X, y, feature_names = prepare_features(df)

    model, scaler, metrics = train_and_evaluate(X, y)

    # save artifacts
    joblib.dump(model, MODEL_OUT)
    joblib.dump(scaler, SCALER_OUT)
    df.to_csv(DATASET_OUT, index=False)
    with open(os.path.join(HERE, 'training_metrics.json'), 'w') as fh:
        json.dump(metrics, fh, indent=2)

    print(f"Trained KRR model saved to: {MODEL_OUT}")
    print(f"Scaler saved to: {SCALER_OUT}")
    print(f"Dataset saved to: {DATASET_OUT} (rows={len(df)})")
    print(f"Metrics: {metrics}")


if __name__ == '__main__':
    main()
