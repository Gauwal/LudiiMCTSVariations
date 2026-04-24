import os
import sys
import copy
import random
import math
import numpy as np
import pandas as pd
import joblib
import json
import warnings
warnings.filterwarnings('ignore')
import matplotlib.pyplot as plt

# reproducible sampling
random.seed(0)
np.random.seed(0)

# Add original code path
repo_path = os.path.abspath('Best_Agent_Identification_GGP')
if repo_path not in sys.path:
    sys.path.insert(0, repo_path)

import BestAgentIdentification as bai


def get_predictions_ludii(original_results, model_folder):
    model_path = os.path.join(model_folder, 'best_model_ludii.joblib')
    features_path = os.path.join(model_folder, 'features_ludii.json')
    variant_catalogue_path = os.path.join(model_folder, 'variant_catalogue_ludii.json')

    model = joblib.load(model_path)
    with open(features_path, 'r') as f:
        features_list = json.load(f)
    with open(variant_catalogue_path, 'r') as f:
        variant_catalogue = json.load(f)

    # Load game properties (from workspace root)
    props_df = pd.read_csv('game_properties.csv')
    props_df['game_clean'] = props_df['game'].apply(lambda n: str(n).replace(' ', '_').replace("'", '').replace('.', ''))

    preds = {}
    rows = []
    mapping = []
    for game in original_results.keys():
        preds[game] = {}
        # find properties
        game_clean = str(game).replace(' ', '_').replace("'", '').replace('.', '')
        props = props_df[props_df['game_clean'] == game_clean]
        if props.empty:
            props = props_df[props_df['game'].str.replace(' ', '_') == game_clean]
        if props.empty:
            props_dict = {}
        else:
            props_dict = props.iloc[0].to_dict()

        for agent in original_results[game].keys():
            row = {}
            # Fill game_* features
            for feat in features_list:
                if feat.startswith('game_'):
                    key = feat[len('game_'):]
                    row[feat] = props_dict.get(key, 0)
                elif feat.startswith('variant_select='):
                    val = feat.split('=', 1)[1]
                    # exact match or substring match
                    match = 1 if (str(agent) == val or val in str(agent) or str(agent) in val) else 0
                    row[feat] = int(match)
                elif feat.startswith('variant_simulation=') or feat.startswith('variant_backprop=') or feat.startswith('variant_finalmove='):
                    # Ludii variants use None for these
                    val = feat.split('=', 1)[1]
                    row[feat] = 1 if val == 'None' else 0
                else:
                    # fallback
                    row[feat] = 0

            row['_game'] = game
            row['_agent'] = agent
            rows.append(row)

    if not rows:
        return preds

    X = pd.DataFrame(rows)
    # Keep copies of game/agent
    games_agents = X[['_game', '_agent']].copy()
    X = X[features_list]
    X = X.fillna(0)

    preds_arr = model.predict(X)
    # If multioutput, take first column
    if len(getattr(preds_arr, 'shape', ())) > 1 and preds_arr.shape[1] > 1:
        preds_arr = preds_arr[:, 0]

    for i, ga in games_agents.iterrows():
        g = ga['_game']
        a = ga['_agent']
        p = float(preds_arr[i])
        p = max(0.0, min(1.0, p))
        preds[g][a] = p

    return preds


def run_warm_start_rcp(original_results, true_win_rate, prior_samples, n, batch_size, alpha=0.05, confidence_bound='Wilson', progress_callback=None, progress_interval_batches=1):
    sample_results = copy.deepcopy(prior_samples)
    win_rate_regret = []
    win_rate_ape = []

    game = None
    agent = None
    scores = {}
    win_rate = {}
    counter = 0
    games = []

    total_batches = math.ceil(n / batch_size) if batch_size > 0 else 0

    for i in range(n):
        scores, win_rate = bai.calculatePossibleRegretChange(sample_results, game, agent, scores, win_rate, alpha, confidence_bound)
        game, agent = bai.findMaxScore(scores)
        # pull real data
        sample_results[game][agent].append(random.choice(original_results[game][agent]))
        counter += 1
        if counter == batch_size:
            win_rate_regret.append(bai.regret(win_rate, true_win_rate))
            win_rate_ape.append(bai.average_probability_error(win_rate, true_win_rate))
            counter = 0

            # Progress callback
            if progress_callback is not None:
                try:
                    current_batch = max(0, len(win_rate_regret) - 1)
                    if current_batch % max(1, progress_interval_batches) == 0:
                        pct = int((current_batch / total_batches) * 100) if total_batches > 0 else 100
                        last_reg = win_rate_regret[-1] if len(win_rate_regret) > 0 else None
                        last_ape = win_rate_ape[-1] if len(win_rate_ape) > 0 else None
                        progress_callback({'task': 'warmStart', 'batch': current_batch, 'total_batches': total_batches, 'percent': pct, 'regret': last_reg, 'ape': last_ape})
                except Exception:
                    pass
    return win_rate_regret, win_rate_ape


def main():
    # Load Ludii dataset using the original module (change cwd temporarily)
    old_cwd = os.getcwd()
    os.chdir(repo_path)
    full_results = bai.ludii_dataset_import()
    os.chdir(old_cwd)

    # Use all games (with >=2 agents), but keep only a fraction of trials per arm
    games = [g for g in full_results.keys() if len(full_results[g]) >= 2]
    print(f'Number of games selected: {len(games)}')

    # Fraction of trials to retain per arm (smaller-scale experiment)
    per_arm_fraction = 0.2
    original_results = {}
    for g in games:
        original_results[g] = {}
        for a in full_results[g].keys():
            orig_list = list(full_results[g][a])
            k = max(1, int(math.ceil(len(orig_list) * per_arm_fraction)))
            if k >= len(orig_list):
                sampled = orig_list.copy()
            else:
                sampled = random.sample(orig_list, k)
            original_results[g][a] = sampled

    true_win_rate = bai.average_results(original_results, None, {})

    n = 400
    batch_size = 40
    alpha = 0.05

    print('\nRunning baseline (cold start) RCP...')
    regret_none, ape_none = bai.regretChangePotential(original_results, true_win_rate, n, batch_size, alpha, 'Wilson', False)

    # Warm start using model predictions
    model_folder = os.path.join('outputs', 'training_results_luddi_raw_dataset_20260422_192655_20260422_203612')
    preds = get_predictions_ludii(original_results, model_folder)
    print('Predictions ready for warm start (sample):')
    for g in list(preds.keys())[:3]:
        print(' ', g, list(preds[g].items())[:3])

    pseudo_weight = 10
    priors = {}
    for g in original_results.keys():
        priors[g] = {}
        for a in original_results[g].keys():
            if g in preds and a in preds[g]:
                p = preds[g][a]
                arr = list(np.random.binomial(1, p, size=pseudo_weight).astype(float))
                if len(arr) == 0:
                    arr = [random.choice(original_results[g][a])]
                priors[g][a] = arr
            else:
                priors[g][a] = [random.choice(original_results[g][a])]

    print('\nRunning warm-start RCP (pseudo-weight=', pseudo_weight, ')...')
    regret_warm, ape_warm = run_warm_start_rcp(original_results, true_win_rate, priors, n, batch_size, alpha, 'Wilson')

    # Print and plot results
    print('\n--- RESULTS: SIMPLE REGRET (Lower is Better) ---')
    print(f"{'Pulls':>8} | {'Baseline':>12} | {'Warm Start':>12}")
    min_len = min(len(regret_none), len(regret_warm))
    for i in range(min_len):
        print(f"{(i+1)*batch_size:>8} | {regret_none[i]:12.4f} | {regret_warm[i]:12.4f}")

    # Plot Simple Regret
    x_axis = [(i+1)*batch_size for i in range(min_len)]
    plt.figure(figsize=(8, 5))
    plt.plot(x_axis, regret_none[:min_len], label='Baseline (Cold Start)', color='black', linestyle='--', marker='o')
    plt.plot(x_axis, regret_warm[:min_len], label='Warm Start', color='C1', marker='x')
    plt.title('Simple Regret over Pulls (Small-Scale)')
    plt.xlabel('Number of Pulls')
    plt.ylabel('Average Simple Regret')
    plt.legend()
    plt.tight_layout()
    regret_plot_path = os.path.join(old_cwd, 'small_scale_warm_start_regret.png')
    plt.savefig(regret_plot_path, dpi=200)
    print('Saved regret plot to', regret_plot_path)
    plt.close()

    print('\n--- RESULTS: APE (Lower is Better) ---')
    print(f"{'Pulls':>8} | {'Baseline':>12} | {'Warm Start':>12}")
    min_len2 = min(len(ape_none), len(ape_warm))
    for i in range(min_len2):
        print(f"{(i+1)*batch_size:>8} | {ape_none[i]:12.4f} | {ape_warm[i]:12.4f}")

    # Plot APE
    x_axis2 = [(i+1)*batch_size for i in range(min_len2)]
    plt.figure(figsize=(8, 5))
    plt.plot(x_axis2, ape_none[:min_len2], label='Baseline (Cold Start)', color='black', linestyle='--', marker='o')
    plt.plot(x_axis2, ape_warm[:min_len2], label='Warm Start', color='C1', marker='x')
    plt.title('Average Probability of Error (APE) over Pulls (Small-Scale)')
    plt.xlabel('Number of Pulls')
    plt.ylabel('Average Probability of Error')
    plt.legend()
    plt.tight_layout()
    ape_plot_path = os.path.join(old_cwd, 'small_scale_warm_start_ape.png')
    plt.savefig(ape_plot_path, dpi=200)
    print('Saved APE plot to', ape_plot_path)
    plt.close()


if __name__ == '__main__':
    main()
