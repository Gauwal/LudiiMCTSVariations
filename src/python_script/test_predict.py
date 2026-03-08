from predict_winrate import (
    predict_score,
    predict_best_variant,
    predict_score_from_features,
    predict_best_variant_from_features,
)

# --- Game-name based predictions (4 separate variant params) ---
print("=== predict_score (by game name) ===")
print("all model:      ", predict_score(
    'La Liebre Perseguida', 'UCB1', 'Random', 'MonteCarlo', 'Robust'))
print("notimeout model:", predict_score(
    'La Liebre Perseguida', 'UCB1', 'Random', 'MonteCarlo', 'Robust', label='notimeout'))

print("\n=== predict_best_variant (by game name) ===")
result = predict_best_variant('La Liebre Perseguida', top_k=5)
print(f"Best variant for '{result['game']}' ({result['n_evaluated']} evaluated):")
bv = result['best_variant']
print(f"  {bv['select']} | {bv['simulation']} | {bv['backprop']} | {bv['finalmove']}"
      f"  → score: {result['best_score']:.4f}")
print("\nTop-5:")
for entry in result['top_k']:
    print(f"  {entry['score']:.4f}  {entry['select']} | {entry['simulation']}"
          f" | {entry['backprop']} | {entry['finalmove']}")

# --- Feature-based predictions (no game name lookup) ---
print("\n=== predict_score_from_features (custom features) ===")
# Hypothetical 3-player board game on a 9×5 cell grid — this combination
# does not match any game in game_properties.csv.
# Features marked (*) are all-NaN in the training data, so they have no
# effect on the model; they are included here for completeness.
custom_features = {
    # board topology
    'numPlayers':        3.0,
    'numCells':         45.0,
    'numVertices':      60.0,
    'numEdges':         98.0,
    'numComponents':     4.0,
    'numPhases':         1.0,
    'numRows':           9.0,
    'numColumns':        5.0,
    'numCorners':        4.0,
    'numPlayableSites': 45.0,
    'avgNumDirections':  5.5,
    'avgNumOrthogonal':  3.4,
    'avgNumDiagonal':    2.1,
    # game flags
    'isStacking':        0.0,
    'isStochastic':      0.0,   # always 0 in training data
    'hasHiddenInfo':     0.0,
    'requiresTeams':     0.0,
    'hasTrack':          0.0,
    'hasCard':           0.0,   # always 0 in training data
    'hasHandDice':       0.0,   # always 0 in training data
    'isVertexGame':      0.0,
    'isEdgeGame':        0.0,
    'isCellGame':        1.0,
    'isDeductionPuzzle': 0.0,
    # (*) all-NaN columns — no signal, included for completeness
    'isSimultaneous':    0.0,
    'isAlternating':     1.0,
    'maxCount':          1.0,
    'maxLocalStates':    2.0,
    'stateSpaceLog':    25.0,
}
print("custom features:", predict_score_from_features(
    custom_features, 'UCB1', 'MAST', 'MonteCarlo', 'Robust'))

print("\n=== predict_best_variant_from_features (custom features) ===")
result2 = predict_best_variant_from_features(custom_features, top_k=3)
print(f"Best variant ({result2['n_evaluated']} evaluated):")
bv2 = result2['best_variant']
print(f"  {bv2['select']} | {bv2['simulation']} | {bv2['backprop']} | {bv2['finalmove']}"
      f"  → score: {result2['best_score']:.4f}")
print("\nTop-3:")
for entry in result2['top_k']:
    print(f"  {entry['score']:.4f}  {entry['select']} | {entry['simulation']}"
          f" | {entry['backprop']} | {entry['finalmove']}")


