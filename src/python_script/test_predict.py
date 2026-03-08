from predict_winrate import predict_winrate, predict_best_variant

# Single prediction with the 'all' model (default)
print("all model:      ", predict_winrate('La Liebre Perseguida', 'UCB1 | Random | MonteCarlo | Robust'))
# Single prediction with the 'notimeout' model
print("notimeout model:", predict_winrate('La Liebre Perseguida', 'UCB1 | Random | MonteCarlo | Robust', label='notimeout'))

# Find the best variant combination for a game
result = predict_best_variant('La Liebre Perseguida', top_k=5)
print(f"\nBest variant for '{result['game']}' ({result['n_evaluated']} evaluated):")
print(f"  {result['best_variant']}  → predicted win rate: {result['best_winrate']:.4f}")
print("\nTop-5:")
for variant_str, wr in result['top_k']:
    print(f"  {wr:.4f}  {variant_str}")

