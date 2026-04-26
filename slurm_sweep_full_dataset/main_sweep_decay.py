#!/usr/bin/env python3
"""
SLURM Sweep Experiment with Synthetic Data Decay

Tests warm-start RCP with exponential decay of synthetic samples.

Usage:
    # No decay (baseline behavior)
    python main_sweep_decay.py --method warm:50 --decay-mode none --time-limit 3600 --seed 0

    # Exponential decay at 10% per batch
    python main_sweep_decay.py --method warm:50 --decay-mode exponential --decay-param 0.10 --time-limit 3600 --seed 0

    # Linear decay: remove 2 samples per batch
    python main_sweep_decay.py --method warm:50 --decay-mode linear --decay-param 2 --time-limit 3600 --seed 0

    # Fixed duration: keep synthetic for 20 batches, then remove all
    python main_sweep_decay.py --method warm:50 --decay-mode fixed_duration --decay-param 20 --time-limit 3600 --seed 0
"""

import os
import sys
import time
import json
import random
import argparse
import math
import traceback
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

# FIX: was parents[0] (slurm_sweep_full_dataset/), must be parents[1] (project root)
sys.path.append(str(Path(__file__).resolve().parents[1]))

# FIX: was missing '..'; file lives in slurm_sweep_full_dataset/ so must go up one level
repo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Best_Agent_Identification_GGP'))
if repo_path not in sys.path:
    sys.path.insert(0, repo_path)

import BestAgentIdentification as bai
import small_scale_warm_start as ssw
import small_scale_warm_start_decay as ssd

DEFAULT_BATCH_SIZE = 20
DEFAULT_ALPHA = 0.05
DEFAULT_CONFIDENCE_BOUND = 'Wilson'
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
    # FIX: was missing '..'; must go up to project root first
    model_dir = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..',
        'outputs', 'training_results_luddi_raw_dataset_20260422_192655_20260422_203612'
    ))
    if os.path.exists(model_dir):
        return model_dir
    return None


def compute_predictor_performance(original_results, true_win_rate, model_folder):
    """Compute predictor-only performance."""
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
    """Print progress updates."""
    ts = time.strftime('%H:%M:%S')
    task = info.get('task', '?')
    batch = info.get('batch', '?')
    total = info.get('total_batches', '?')
    pct = info.get('percent', '?')
    reg = info.get('regret', float('nan'))
    ape = info.get('ape', float('nan'))
    print(f'[{ts}] {task} {pct}% ({batch}/{total}) regret={reg:.6f} ape={ape:.4f}')


def run_experiment(method, time_limit, seed, batch_size, alpha, confidence_bound,
                   decay_mode, decay_param, output_dir):
    """
    Run experiment with optional decay.

    method: str
        'baseline' or 'warm:<weight>'
    decay_mode: str
        'none', 'exponential', 'linear', 'fixed_duration'
    decay_param: float
        Decay parameter (interpretation depends on decay_mode)
    """
    print('\n' + '=' * 80)
    print('SLURM Sweep Experiment with Synthetic Data Decay')
    print('=' * 80)
    print(f'Method: {method}')
    print(f'Decay: {decay_mode} (param={decay_param})')
    print(f'Time limit: {time_limit}s, Seed: {seed}, Batch size: {batch_size}')
    print(f'Output directory: {output_dir}')
    print()

    os.makedirs(output_dir, exist_ok=True)

    # Load dataset
    full_results = load_dataset()
    original_results = build_full_dataset(full_results)
    print(f'Using {len(original_results)} games (full dataset)\n')

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

    # Validate method
    is_baseline = (method == 'baseline')
    warm_weight = None

    if not is_baseline:
        if not method.startswith('warm:'):
            raise ValueError(f'Invalid method: {method}')
        try:
            warm_weight = int(method.split(':')[1])
        except (IndexError, ValueError):
            raise ValueError(f'Invalid method: {method}')

    # -----------------------------------------------------------------------
    # Run the experiment
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
        decay_stats = None

    else:  # warm-start with decay
        print(f'Running WARM-START (w={warm_weight}, decay={decay_mode} param={decay_param})...')

        try:
            preds = ssw.get_predictions_ludii(original_results, model_folder) if model_folder else {}
        except Exception:
            traceback.print_exc()
            preds = {}

        # Build priors
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
        regret_w, ape_w, decay_stats = ssd.run_warm_start_rcp_with_decay(
            original_results, true_win_rate, priors, per_method_n, batch_size, alpha,
            confidence_bound,
            decay_mode=decay_mode,
            decay_param=decay_param,
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
    decay_str = f'_{decay_mode}_{decay_param}' if not is_baseline else ''
    json_filename = f'sweep_decay_{method_str}{decay_str}_{seed}_{timestamp}.json'
    json_path = os.path.join(output_dir, json_filename)

    result_data = {
        'meta': {
            'method': method,
            'decay_mode': decay_mode,
            'decay_param': decay_param if not is_baseline else None,
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
        result_data['decay_stats'] = decay_stats

    with open(json_path, 'w') as f:
        json.dump(result_data, f, indent=2)
    print(f'Saved: {json_path}\n')

    # -----------------------------------------------------------------------
    # Generate plots
    # -----------------------------------------------------------------------
    print('Generating plots...')

    x_axis = [(i + 1) * batch_size for i in range(len(regret_results))]

    # Regret plot
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.plot(x_axis, regret_results, label=f'{method} (decay={decay_mode})',
            color='steelblue', linewidth=2.5)
    if predictor_regret is not None:
        ax.axhline(y=predictor_regret, color='red', linestyle='--', linewidth=2,
                   label=f'Predictor only ({predictor_regret:.6f})')
    ax.set_xlabel('Number of Pulls', fontsize=12)
    ax.set_ylabel('Simple Regret', fontsize=12)
    title = f'Regret: {method} with {decay_mode} decay'
    if not is_baseline and decay_mode != 'none':
        title += f' (param={decay_param})'
    ax.set_title(title, fontsize=13, fontweight='bold')
    ax.legend(loc='best', fontsize=11)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    regret_png = json_path.replace('.json', '_regret.png')
    plt.savefig(regret_png, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'Saved: {regret_png}')

    # APE plot
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.plot(x_axis, ape_results, label=f'{method} (decay={decay_mode})',
            color='coral', linewidth=2.5)
    if predictor_ape is not None:
        ax.axhline(y=predictor_ape, color='red', linestyle='--', linewidth=2,
                   label=f'Predictor only ({predictor_ape:.4f})')
    ax.set_xlabel('Number of Pulls', fontsize=12)
    ax.set_ylabel('Avg. Probability of Error', fontsize=12)
    title = f'APE: {method} with {decay_mode} decay'
    if not is_baseline and decay_mode != 'none':
        title += f' (param={decay_param})'
    ax.set_title(title, fontsize=13, fontweight='bold')
    ax.legend(loc='best', fontsize=11)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    ape_png = json_path.replace('.json', '_ape.png')
    plt.savefig(ape_png, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'Saved: {ape_png}')

    print('\n' + '=' * 80)
    print('Experiment complete!')
    print('=' * 80)


def main():
    parser = argparse.ArgumentParser(description='SLURM Sweep with Synthetic Data Decay')
    parser.add_argument('--method', type=str, default='baseline',
                        help='baseline or warm:<weight>')
    parser.add_argument('--time-limit', type=float, default=3600,
                        help='Time limit in seconds')
    parser.add_argument('--seed', type=int, default=0,
                        help='Random seed')
    parser.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE,
                        help='Batch size')
    parser.add_argument('--alpha', type=float, default=DEFAULT_ALPHA,
                        help='Confidence level')
    parser.add_argument('--confidence-bound', type=str, default=DEFAULT_CONFIDENCE_BOUND,
                        help='Confidence bound type')
    parser.add_argument('--decay-mode', type=str, default='none',
                        choices=['none', 'exponential', 'linear', 'fixed_duration'],
                        help='Decay mode')
    parser.add_argument('--decay-param', type=float, default=0.0,
                        help='Decay parameter (interpretation depends on mode)')
    parser.add_argument('--output-dir', type=str, default='./results',
                        help='Output directory')

    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    run_experiment(
        method=args.method,
        time_limit=args.time_limit,
        seed=args.seed,
        batch_size=args.batch_size,
        alpha=args.alpha,
        confidence_bound=args.confidence_bound,
        decay_mode=args.decay_mode,
        decay_param=args.decay_param,
        output_dir=args.output_dir
    )


if __name__ == '__main__':
    main()
