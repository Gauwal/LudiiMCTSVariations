#!/usr/bin/env python3
"""
SLURM Sweep Experiment - Full Dataset, Single Method

Usage (baseline only):
    python main_sweep.py --method baseline --time-limit 3600 --seed 0 --output-dir ./results

Usage (single warm weight):
    python main_sweep.py --method warm:50 --time-limit 3600 --seed 0 --output-dir ./results

This script:
  1. Loads the full Ludii dataset (no subsampling)
  2. Runs a timing probe
  3. Executes either baseline RCP OR warm-start RCP for a single weight
  4. Computes predictor-only performance
  5. Generates regret and APE plots with predictor comparison line
  6. Saves JSON results and PNG plots
"""

import os
import sys
import time
import json
import random
import argparse
import math
from pathlib import Path
import traceback

import numpy as np
import matplotlib.pyplot as plt

sys.path.append(str(Path(__file__).resolve().parents[1]))

# Add repo paths
repo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Best_Agent_Identification_GGP'))
if repo_path not in sys.path:
    sys.path.insert(0, repo_path)

import BestAgentIdentification as bai
import small_scale_warm_start as ssw

# Default parameters
DEFAULT_BATCH_SIZE = 20
DEFAULT_ALPHA = 0.05
DEFAULT_CONFIDENCE_BOUND = 'Wilson'
DEFAULT_PER_ARM_FRACTION = 1.0  # Full dataset
# FIX: renamed from `weights` to `DEFAULT_WEIGHTS` to match usage throughout
DEFAULT_WEIGHTS = [5, 20, 50, 100, 200, 500]


def load_dataset():
    """Load full Ludii dataset."""
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
    """Use full dataset (no subsampling)."""
    original_results = {}
    for g in full_results.keys():
        if len(full_results[g]) < 2:
            continue
        original_results[g] = {}
        for a in full_results[g].keys():
            original_results[g][a] = list(full_results[g][a])
    return original_results


def get_model_folder():
    """Find the trained model folder."""
    model_dir = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..',
        'outputs', 'training_results_luddi_raw_dataset_20260422_192655_20260422_203612'
    ))
    if os.path.exists(model_dir):
        return model_dir
    return None


def compute_predictor_performance(original_results, true_win_rate, model_folder):
    """
    Compute single predictor regret/APE by selecting the predicted best arm per game.
    Returns (predictor_regret, predictor_ape) as single float values.
    """
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
            best_agent = agents[0]  # fallback

        true_best = max(true_win_rate[g].keys(), key=lambda x: true_win_rate[g][x])
        regret_val = true_win_rate[g][true_best] - true_win_rate[g][best_agent]
        pred_regrets.append(regret_val)
        pred_apes.append(1.0 if regret_val > 0 else 0.0)

    predictor_regret = float(np.mean(pred_regrets)) if pred_regrets else None
    predictor_ape = float(np.mean(pred_apes)) if pred_apes else None

    print(f'  Predictor-only: regret={predictor_regret:.6f}, ape={predictor_ape:.4f}')
    return predictor_regret, predictor_ape


def progress_printer(info):
    """Print progress updates."""
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
    Run experiment for a single method.

    method: str
        'baseline' or 'warm:<weight>' (e.g., 'warm:50')
    """
    print('\n' + '=' * 70)
    print('SLURM Sweep Experiment - Single Method')
    print('=' * 70)
    print(f'Method: {method}')
    print(f'Time limit: {time_limit}s, Seed: {seed}, Batch size: {batch_size}')
    print(f'Output directory: {output_dir}')
    print()

    os.makedirs(output_dir, exist_ok=True)

    # Load dataset
    full_results = load_dataset()
    original_results = build_full_dataset(full_results)
    print(f'Using {len(original_results)} games (full dataset, no subsampling)\n')

    # Compute true win rates
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

    # Budget calculation
    # FIX: was `len(weights)` (undefined); now correctly uses `len(DEFAULT_WEIGHTS)`
    total_pulls = max(batch_size * 2, int(time_limit / max(secs_per_pull, 1e-6)))
    per_method_n = max(batch_size * 2, int(total_pulls // (1 + len(DEFAULT_WEIGHTS))))
    print(f'Time budget: {time_limit}s → ~{total_pulls} total pulls')
    print(f'Per-method budget: {per_method_n} pulls (~{per_method_n * secs_per_pull:.1f}s)\n')

    # Get model folder
    model_folder = get_model_folder()

    # Compute predictor performance
    print('Computing predictor-only performance...')
    predictor_regret, predictor_ape = compute_predictor_performance(
        original_results, true_win_rate, model_folder
    )
    print()

    # Validate method argument
    is_baseline = (method == 'baseline')
    warm_weight = None

    if not is_baseline:
        if not method.startswith('warm:'):
            raise ValueError(f'Invalid method: {method}. Use "baseline" or "warm:<weight>"')
        try:
            warm_weight = int(method.split(':')[1])
        except (IndexError, ValueError):
            raise ValueError(f'Invalid method: {method}. Use "warm:<weight>" e.g. "warm:50"')

    # -----------------------------------------------------------------------
    # Run the chosen method
    # -----------------------------------------------------------------------

    if is_baseline:
        print('Running BASELINE (cold start)...')
        start_base = time.time()
        regret_base, ape_base = bai.regretChangePotential(
            original_results, true_win_rate, per_method_n, batch_size, alpha, confidence_bound,
            progress_callback=progress_printer
        )
        wall_time = time.time() - start_base
        print(f'Baseline finished: {len(regret_base)} points, {wall_time:.2f}s wall time')
        print(f'  Final: regret={regret_base[-1]:.6f}, ape={ape_base[-1]:.4f}\n')

        regret_results = regret_base
        ape_results = ape_base

    else:  # warm-start
        print(f'Running WARM-START (w={warm_weight})...')

        try:
            preds = ssw.get_predictions_ludii(original_results, model_folder) if model_folder else {}
        except Exception:
          traceback.print_exc()
          preds = {}

        # Build priors from predictions
        priors = {}
        for g in original_results.keys():
            priors[g] = {}
            for a in original_results[g].keys():
                p = None
                if g in preds and isinstance(preds[g], dict):
                    p = preds[g].get(a)

                if p is not None:
                    arr = list(np.random.binomial(1, p, size=warm_weight).astype(float))
                    if len(arr) == 0:
                        arr = [random.choice(original_results[g][a])]
                    priors[g][a] = arr
                else:
                    priors[g][a] = [random.choice(original_results[g][a])]

        start_w = time.time()
        regret_w, ape_w = ssw.run_warm_start_rcp(
            original_results, true_win_rate, priors, per_method_n, batch_size, alpha, confidence_bound,
            progress_callback=progress_printer
        )
        wall_time = time.time() - start_w
        print(f'Warm w={warm_weight} finished: {len(regret_w)} points, {wall_time:.2f}s wall time')
        print(f'  Final: regret={regret_w[-1]:.6f}, ape={ape_w[-1]:.4f}\n')

        regret_results = regret_w
        ape_results = ape_w

    # -----------------------------------------------------------------------
    # Save JSON results
    # -----------------------------------------------------------------------
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    method_str = method.replace(':', '_')
    json_filename = f'sweep_{method_str}_{seed}_{timestamp}.json'
    json_path = os.path.join(output_dir, json_filename)

    result_data = {
        'meta': {
            'method': method,
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
        result_data['warm'] = {str(warm_weight): {'regret': regret_results, 'ape': ape_results}}

    with open(json_path, 'w') as jf:
        json.dump(result_data, jf, indent=2)
    print(f'Saved JSON: {json_path}')

    # -----------------------------------------------------------------------
    # Generate plots
    # -----------------------------------------------------------------------
    print('\nGenerating plots...')
    plot_label = 'Baseline' if is_baseline else f'Warm w={warm_weight}'

    if len(regret_results) > 0:
        x = [(i + 1) * batch_size for i in range(len(regret_results))]
        plt.figure(figsize=(10, 6))
        plt.plot(x, regret_results, label=plot_label, color='blue', linewidth=2)
        if predictor_regret is not None:
            plt.hlines(predictor_regret, x[0], x[-1], colors='red', linestyles=':', linewidth=2.5,
                       label='Predictor (single)')
        plt.xlabel('Number of Pulls', fontsize=12)
        plt.ylabel('Simple Regret', fontsize=12)
        plt.title(f'Warm-Start RCP: {plot_label} - Regret (Full Dataset)', fontsize=13)
        plt.legend(loc='best', fontsize=10)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        regret_png = os.path.join(output_dir, f'sweep_{method_str}_{seed}_{timestamp}_regret.png')
        plt.savefig(regret_png, dpi=150)
        plt.close()
        print(f'Saved regret plot: {regret_png}')

    if len(ape_results) > 0:
        x_ape = [(i + 1) * batch_size for i in range(len(ape_results))]
        plt.figure(figsize=(10, 6))
        plt.plot(x_ape, ape_results, label=plot_label, color='blue', linewidth=2)
        if predictor_ape is not None:
            plt.hlines(predictor_ape, x_ape[0], x_ape[-1], colors='red', linestyles=':', linewidth=2.5,
                       label='Predictor (single)')
        plt.xlabel('Number of Pulls', fontsize=12)
        plt.ylabel('Accuracy per Game (APE)', fontsize=12)
        plt.title(f'Warm-Start RCP: {plot_label} - Accuracy (Full Dataset)', fontsize=13)
        plt.legend(loc='best', fontsize=10)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        ape_png = os.path.join(output_dir, f'sweep_{method_str}_{seed}_{timestamp}_ape.png')
        plt.savefig(ape_png, dpi=150)
        plt.close()
        print(f'Saved APE plot: {ape_png}')

    print('\n' + '=' * 70)
    print('EXPERIMENT COMPLETE')
    print('=' * 70)
    print(f'Results saved to: {output_dir}')
    print(f'JSON file: {json_filename}')


def main():
    parser = argparse.ArgumentParser(
        description='SLURM Sweep Experiment - Single Method'
    )
    parser.add_argument(
        '--method', type=str, required=True,
        help='Method to run: "baseline" or "warm:<weight>" e.g. "warm:50"'
    )
    parser.add_argument('--time-limit', type=float, default=3600,
                        help='Time limit in seconds (default: 3600)')
    parser.add_argument('--seed', type=int, default=0,
                        help='Random seed (default: 0)')
    parser.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE,
                        help=f'Batch size (default: {DEFAULT_BATCH_SIZE})')
    parser.add_argument('--output-dir', type=str, default='./results',
                        help='Output directory (default: ./results)')

    args = parser.parse_args()

    # Validate method
    valid_methods = ['baseline'] + [f'warm:{w}' for w in DEFAULT_WEIGHTS]
    if args.method not in valid_methods and not args.method.startswith('warm:'):
        parser.error(f'--method must be "baseline" or "warm:<weight>". Got: {args.method}')

    random.seed(args.seed)
    np.random.seed(args.seed)

    run_experiment(
        method=args.method,
        time_limit=args.time_limit,
        seed=args.seed,
        batch_size=args.batch_size,
        alpha=DEFAULT_ALPHA,
        confidence_bound=DEFAULT_CONFIDENCE_BOUND,
        output_dir=os.path.abspath(args.output_dir),
    )


if __name__ == '__main__':
    main()