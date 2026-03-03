from tune_krr_winrate import predict_winrate

# predict with 'all' model (default)
print("all model:      ", predict_winrate('La Liebre Perseguida', 'AG0 | Random | MonteCarlo | Robust'))
# predict with 'notimeout' model
print("notimeout model:", predict_winrate('La Liebre Perseguida', 'AG0 | Random | MonteCarlo | Robust', label='notimeout'))
