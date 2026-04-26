#!/usr/bin/env python3
"""
SLURM Sweep Experiment - Single Fractional Sample Warm Start

Instead of injecting w binary samples drawn from the ML prediction,
injects exactly ONE sample with value = the ML predicted probability.

This gives RCP a directional nudge (μ̂ starts near the prediction)
without narrowing the confidence interval (n=1 keeps CI very wide).
If the prediction is wrong, one real pull is enough to override it.

Usage:
    python main_sweep_fractional.py --method baseline --time-limit 3600 --seed 0
    python main_sweep_fractional.py --method warm --time-limit 3600 --seed 0
"""

import os
import sys
import time
import json
import random
import argparse
import traceback
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

sys.path.append(str(Path(__file__).resolve().parents[1]))

repo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Best_Agent_Identification_GGP'))
if repo_path not in sys.path:
    sys.path.insert(0, repo_path)

import BestAgentIdentification as bai
import small_scale_warm_start as ssw

DEFAULT_BATCH_SIZE = 20
DEFAULT_ALPHA = 0.05
DEFAULT_CONFIDENCE_BOUND = 'Wilson'
DEFAULT_WEIGHTS = [5, 20, 50, 100, 200, 500]


def load_dataset():
    old_cwd = os.getcwd()
    try:
        os.chdir(repo_path)
        print('Loading Ludii dataset...')
        full_results = bai.ludii_dataset_import()
        os.chdir(old_cwd)
        print(f'Loaded {len(full_results)} games')
        return full_results
    finally:
        os.chdir(old_cwd)


def build_full_dataset(full_results):
    original_results = {}
    for g in full_results.keys():
        if len(full_results[g]) < 2:
            continue
        original_results[g] = {}
        for a in full_results[g].keys():
            original_results[g][a] = list(full_results[g][a])
    return original_results


def get_model_folder():
    model_dir = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..',
        'outputs', 'training_results_luddi_raw_dataset_20260422_192655_20260422_203612'
    ))
    if os.path.exists(model_dir):
        return model_dir
    return None


def compute_predictor_performance(original_results, true_win_rate, model_folder):
    if model_folder is None:
        print('  (Model folder not found, skipping predictor performance)')
        return None, None
    try:
        preds = ssw.get_predictions_ludii(original_results, model_folder)
        total_pred = sum(
            len(preds[g]) if g in preds and isinstance(preds[g], dict) else 0
            for g in preds
        )
        print(f'  Predictions loaded: {total_pred} agent predictions')
    except Exception as e:
        print(f'  Predictions load failed: {e}')
        traceback.print_exc()
        return None, None

    pred_regrets = []
    pred_apes = []
    for g in original_results.keys():
        agents = list(original_results[g].keys())
        best_agent = None
        best_p = -1.0
        if g in preds and isinstance(preds[g], dict):
            for a in agents:
                p = preds[g].get(a, -1.0)
                if p > best_p:
                    best_p = p
                    best_agent = a
        if best_agent is None:
            best_agent = agents[0]
        true_best = max(true_win_rate[g].keys(), key=lambda x: true_win_rate[g][x])
        regret_val = true_win_rate[g][true_best] - true_win_rate[g][best_agent]
        pred_regrets.append(regret_val)
        pred_apes.append(1.0 if regret_val > 0 else 0.0)

    predictor_regret = float(np.mean(pred_regrets)) if pred_regrets else None
    predictor_ape = float(np.mean(pred_apes)) if pred_apes else None
    print(f'  Predictor-only: regret={predictor_regret:.6f}, ape={predictor_ape:.4f}')
    return predictor_regret, predictor_ape


def progress_printer(info):
    ts = time.strftime('%H:%M:%S')
    task = info.get('task', '?')
    batch = info.get('batch', '?')
    total = info.get('total_batches', '?')
    pct = info.get('percent', '?')
    reg = info.get('regret', float('nan'))
    ape = info.get('ape', float('nan'))
    print(f'[{ts}] {task} {pct}% ({batch}/{total}) regret={reg:.6f} ape={ape:.4f}')


def run_experiment(method, time_limit, seed, batch_size, alpha, confidence_bound, output_dir):
    """
    Run experiment.

    method: 'baseline' or 'warm'
      - baseline: cold start, no prior
      - warm: single fractional sample prior (value = ML predicted probability)
    """
    print('\n' + '=' * 80)
    print('SLURM Sweep Experiment - Single Fractional Sample Warm Start')
    print('=' * 80)
    print(f'Method:          {method}')
    print(f'Time limit:      {time_limit}s')
    print(f'Seed:            {seed}')
    print(f'Batch size:      {batch_size}')
    print(f'Output dir:      {output_dir}')
    print()

    os.makedirs(output_dir, exist_ok=True)

    full_results = load_dataset()
    original_results = build_full_dataset(full_results)
    print(f'Using {len(original_results)} games (full dataset)\n')

    true_win_rate = bai.average_results(original_results, None, {})

    # Timing probe
    trial_n = 100
    print(f'Running timing probe ({trial_n} pulls)...')
    start = time.time()
    bai.regretChangePotential(
        original_results, true_win_rate, trial_n, batch_size, alpha, confidence_bound,
        progress_callback=None
    )
    secs_per_pull = (time.time() - start) / max(1, trial_n)
    print(f'  Estimated secs/pull: {secs_per_pull:.6f}\n')

    total_pulls = max(batch_size * 2, int(time_limit / max(secs_per_pull, 1e-6)))
    per_method_n = max(batch_size * 2, int(total_pulls // (1 + len(DEFAULT_WEIGHTS))))
    print(f'Time budget: {time_limit}s → ~{total_pulls} total pulls')
    print(f'Per-method budget: {per_method_n} pulls (~{per_method_n * secs_per_pull:.1f}s)\n')

    model_folder = get_model_folder()

    print('Computing predictor-only performance...')
    predictor_regret, predictor_ape = compute_predictor_performance(
        original_results, true_win_rate, model_folder
    )
    print()

    is_baseline = (method == 'baseline')

    # -----------------------------------------------------------------------
    # Run
    # -----------------------------------------------------------------------

    if is_baseline:
        print('Running BASELINE (cold start)...')
        start_t = time.time()
        regret_results, ape_results = bai.regretChangePotential(
            original_results, true_win_rate, per_method_n, batch_size, alpha, confidence_bound,
            progress_callback=progress_printer
        )
        wall_time = time.time() - start_t
        print(f'Baseline finished: {len(regret_results)} points, {wall_time:.2f}s')
        print(f'  Final: regret={regret_results[-1]:.6f}, ape={ape_results[-1]:.4f}\n')

    else:  # fractional warm start
        print('Running FRACTIONAL WARM START (1 sample per arm = ML predicted probability)...')

        try:
            preds = ssw.get_predictions_ludii(original_results, model_folder) if model_folder else {}
        except Exception:
            traceback.print_exc()
            preds = {}

        # Build priors: ONE fractional sample per arm
        priors = {}
        for g in original_results.keys():
            priors[g] = {}
            for a in original_results[g].keys():
                p = None
                if g in preds and isinstance(preds[g], dict):
                    p = preds[g].get(a)

                if p is not None:
                    # KEY DIFFERENCE vs decay approach:
                    # inject exactly one sample with the raw predicted probability.
                    # n=1 → CI stays wide → RCP still explores freely.
                    # μ̂ starts at p → gives a gentle directional nudge.
                    priors[g][a] = [float(p)]
                else:
                    # No prediction available: fall back to one real result
                    priors[g][a] = [random.choice(original_results[g][a])]

        start_t = time.time()
        regret_results, ape_results = ssw.run_warm_start_rcp(
            original_results, true_win_rate, priors, per_method_n, batch_size, alpha,
            confidence_bound,
            progress_callback=progress_printer
        )
        wall_time = time.time() - start_t
        print(f'Fractional warm start finished: {len(regret_results)} points, {wall_time:.2f}s')
        print(f'  Final: regret={regret_results[-1]:.6f}, ape={ape_results[-1]:.4f}\n')

    # -----------------------------------------------------------------------
    # Save JSON
    # -----------------------------------------------------------------------
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    json_filename = f'sweep_fractional_{method}_{seed}_{timestamp}.json'
    json_path = os.path.join(output_dir, json_filename)

    result_data = {
        'meta': {
            'method': method,
            'prior_type': 'fractional_single_sample' if not is_baseline else 'none',
            'time_limit': time_limit,
            'seed': seed,
            'batch_size': batch_size,
            'num_games': len(original_results),
            'secs_per_pull': secs_per_pull,
            'per_method_n': per_method_n,
            'wall_time': wall_time,
        },
        'predictor': {
            'regret': predictor_regret,
            'ape': predictor_ape,
        },
    }

    if is_baseline:
        result_data['baseline'] = {'regret': regret_results, 'ape': ape_results}
    else:
        result_data['warm_fractional'] = {'regret': regret_results, 'ape': ape_results}

    with open(json_path, 'w') as f:
        json.dump(result_data, f, indent=2)
    print(f'Saved: {json_path}\n')

    # -----------------------------------------------------------------------
    # Plots
    # -----------------------------------------------------------------------
    print('Generating plots...')
    x_axis = [(i + 1) * batch_size for i in range(len(regret_results))]
    label = 'Baseline (cold start)' if is_baseline else 'Fractional warm start'
    color = 'black' if is_baseline else 'steelblue'

    for metric, values, ylabel in [
        ('regret', regret_results, 'Simple Regret'),
        ('ape',    ape_results,    'Avg. Probability of Error'),
    ]:
        ref_val = predictor_regret if metric == 'regret' else predictor_ape
        fig, ax = plt.subplots(figsize=(12, 7))
        ax.plot(x_axis, values, label=label, color=color, linewidth=2.5)
        if ref_val is not None:
            ax.axhline(y=ref_val, color='red', linestyle='--', linewidth=2,
                       label=f'Predictor only ({ref_val:.4f})')
        ax.set_xlabel('Number of Pulls', fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_title(f'{ylabel}: {label}', fontsize=13, fontweight='bold')
        ax.legend(loc='best', fontsize=11)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        png_path = json_path.replace('.json', f'_{metric}.png')
        plt.savefig(png_path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f'Saved: {png_path}')

    print('\n' + '=' * 80)
    print('Experiment complete!')
    print('=' * 80)


def main():
    parser = argparse.ArgumentParser(
        description='Single Fractional Sample Warm Start Sweep'
    )
    parser.add_argument('--method', type=str, default='baseline',
                        choices=['baseline', 'warm'],
                        help='"baseline" for cold start, "warm" for fractional prior')
    parser.add_argument('--time-limit', type=float, default=3600)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument('--output-dir', type=str, default='./results')

    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    run_experiment(
        method=args.method,
        time_limit=args.time_limit,
        seed=args.seed,
        batch_size=args.batch_size,
        alpha=DEFAULT_ALPHA,
        confidence_bound=DEFAULT_CONFIDENCE_BOUND,
        output_dir=args.output_dir,
    )


if __name__ == '__main__':
    main()
