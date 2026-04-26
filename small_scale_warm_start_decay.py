"""
Warm-Start RCP with Synthetic Data Decay

This module extends warm-start RCP with the ability to gradually decay/remove
synthetic samples over time. The decay mechanism prevents over-regularization
from inaccurate ML predictions.

Decay Modes:
  - 'none': Synthetic samples stay forever (baseline behavior)
  - 'exponential': Remove a percentage of remaining synthetic each batch
                   (e.g., decay_param=0.10 → remove 10% per batch, keep 90%)
  - 'linear': Remove a fixed integer count per batch per arm
  - 'fixed_duration': Keep all synthetic for N batches, then remove all at once
"""

import os
import sys
import copy
import random
import math
import numpy as np
from pathlib import Path

repo_path = os.path.abspath('Best_Agent_Identification_GGP')
if repo_path not in sys.path:
    sys.path.insert(0, repo_path)

import BestAgentIdentification as bai


def run_warm_start_rcp_with_decay(
    original_results,
    true_win_rate,
    prior_samples,
    n,
    batch_size,
    alpha=0.05,
    confidence_bound='Wilson',
    decay_mode='none',
    decay_param=0.0,
    progress_callback=None,
    progress_interval_batches=1
):
    """
    Run warm-start RCP with optional synthetic data decay.

    Parameters
    ----------
    original_results : dict
        {game: {agent: [outcomes]}}
    true_win_rate : dict
        {game: {agent: true_prob}}
    prior_samples : dict
        {game: {agent: [synthetic_samples]}} - initial prior samples
    n : int
        Total pulls to perform
    batch_size : int
        Pulls per batch
    alpha : float
        Confidence level
    confidence_bound : str
        Type of bound ('Wilson', etc.)
    decay_mode : str
        'none', 'exponential', 'linear', 'fixed_duration'
    decay_param : float
        - exponential: fraction to remove per batch (0.10 = remove 10% → keep 90%)
        - linear: integer count to remove per arm per batch
        - fixed_duration: number of batches to keep synthetic before removing all
    progress_callback : callable, optional
        Progress reporting function
    progress_interval_batches : int
        Report progress every N batches

    Returns
    -------
    tuple : (regret_list, ape_list, decay_stats)
        decay_stats tracks total synthetic sample counts over batches
    """

    # -----------------------------------------------------------------------
    # Initialise working dataset with synthetic priors
    # Each arm's list starts with synthetic samples followed (over time) by
    # real pulls.  We track how many synthetic entries remain at the FRONT of
    # each list so we can remove them correctly.
    # -----------------------------------------------------------------------
    sample_results = copy.deepcopy(prior_samples)

    # synthetic_counts[g][a] = number of synthetic samples currently present
    # (always integer; fractional accounting happens via a separate accumulator)
    synthetic_counts = {}
    for g in original_results:
        synthetic_counts[g] = {}
        for a in original_results[g]:
            synthetic_counts[g][a] = len(prior_samples[g][a])

    # For exponential decay we need a fractional accumulator so that small
    # decay rates still remove samples over many batches.
    frac_accumulator = {g: {a: 0.0 for a in original_results[g]} for g in original_results}

    decay_stats = {
        'mode': decay_mode,
        'param': decay_param,
        'synthetic_by_batch': [],   # total synthetic samples remaining after each batch
    }

    win_rate_regret = []
    win_rate_ape = []

    game = None
    agent = None
    scores = {}
    win_rate = {}
    counter = 0

    total_batches = math.ceil(n / batch_size) if batch_size > 0 else 0
    current_batch = 0

    for i in range(n):
        scores, win_rate = bai.calculatePossibleRegretChange(
            sample_results, game, agent, scores, win_rate, alpha, confidence_bound
        )
        game, agent = bai.findMaxScore(scores)

        # Pull one real data point
        sample_results[game][agent].append(random.choice(original_results[game][agent]))
        counter += 1

        if counter == batch_size:
            win_rate_regret.append(bai.regret(win_rate, true_win_rate))
            win_rate_ape.append(bai.average_probability_error(win_rate, true_win_rate))
            current_batch += 1
            counter = 0

            # -------------------------------------------------------------------
            # Apply decay: actually remove synthetic samples from sample_results
            # -------------------------------------------------------------------
            if decay_mode != 'none':
                for g in original_results:
                    for a in original_results[g]:
                        remaining = synthetic_counts[g][a]
                        if remaining <= 0:
                            continue

                        if decay_mode == 'exponential':
                            # Compute how many to remove this batch (with fractional carry)
                            to_remove_frac = remaining * decay_param + frac_accumulator[g][a]
                            to_remove_int = int(to_remove_frac)
                            frac_accumulator[g][a] = to_remove_frac - to_remove_int
                            actual_remove = min(to_remove_int, remaining)

                        elif decay_mode == 'linear':
                            actual_remove = min(int(decay_param), remaining)
                            frac_accumulator[g][a] = 0.0

                        elif decay_mode == 'fixed_duration':
                            # Remove all at once once we pass the cutoff batch
                            actual_remove = remaining if current_batch >= int(decay_param) else 0
                            frac_accumulator[g][a] = 0.0

                        else:
                            actual_remove = 0

                        # Never empty the list — bai.average_results divides by len()
                        actual_remove = min(actual_remove, max(0, len(sample_results[g][a]) - 1))

                        if actual_remove > 0:
                            # Synthetic samples are at the FRONT of the list
                            # (they were added first via copy.deepcopy(prior_samples))
                            del sample_results[g][a][:actual_remove]
                            synthetic_counts[g][a] -= actual_remove

                total_synthetic = sum(
                    synthetic_counts[g][a]
                    for g in synthetic_counts
                    for a in synthetic_counts[g]
                )
                decay_stats['synthetic_by_batch'].append(total_synthetic)

            # Progress callback
            if progress_callback is not None:
                try:
                    if current_batch % max(1, progress_interval_batches) == 0:
                        pct = int((current_batch / total_batches) * 100) if total_batches > 0 else 100
                        last_reg = win_rate_regret[-1] if win_rate_regret else None
                        last_ape = win_rate_ape[-1] if win_rate_ape else None
                        progress_callback({
                            'task': f'warmStart (decay={decay_mode})',
                            'batch': current_batch,
                            'total_batches': total_batches,
                            'percent': pct,
                            'regret': last_reg,
                            'ape': last_ape,
                        })
                except Exception:
                    pass

    return win_rate_regret, win_rate_ape, decay_stats


def run_warm_start_rcp(
    original_results,
    true_win_rate,
    prior_samples,
    n,
    batch_size,
    alpha=0.05,
    confidence_bound='Wilson',
    progress_callback=None,
    progress_interval_batches=1
):
    """
    Standard warm-start RCP without decay (backwards-compatible wrapper).
    """
    regret, ape, _ = run_warm_start_rcp_with_decay(
        original_results, true_win_rate, prior_samples, n, batch_size,
        alpha, confidence_bound,
        decay_mode='none', decay_param=0.0,
        progress_callback=progress_callback,
        progress_interval_batches=progress_interval_batches,
    )
    return regret, ape
