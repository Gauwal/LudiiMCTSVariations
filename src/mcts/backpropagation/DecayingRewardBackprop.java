package mcts.backpropagation;

import game.Game;
import mcts.MCTSVariations.Node;

/**
 * Decaying Reward Backpropagation.
 * Multiplies reward by decay factor at each level to weight early wins more heavily.
 *
 * Reference: Section 6.2.3 of MCTS Survey
 */
public class DecayingRewardBackprop implements BackpropagationPolicy {
    private final double decayFactor;
    private String friendlyName;

    /**
     * Constructor with custom decay factor
     * @param decayFactor The decay constant (0 < γ ≤ 1)
     */
    public DecayingRewardBackprop(double decayFactor) {
        if (decayFactor <= 0.0 || decayFactor > 1.0) {
            throw new IllegalArgumentException("Decay factor must be in (0, 1]");
        }
        this.decayFactor = decayFactor;
        this.friendlyName = "Decaying Reward (γ=" + decayFactor + ")";
    }

    /**
     * Default constructor with typical decay value
     */
    public DecayingRewardBackprop() {
        this(0.95); // Typical value from literature
    }

    @Override
    public void backpropagate(Node leaf, double[] utilities, Game game) {
        Node current = leaf;
        double currentDecay = 1.0;

        while (current != null) {
            current.visitCount += 1;

            // Apply decayed rewards
            for (int p = 1; p <= game.players().count(); ++p) {
                current.scoreSums[p] += utilities[p] * currentDecay;
            }

            // Decay for next level
            currentDecay *= decayFactor;
            current = current.parent;
        }
    }

    @Override
    public String getName() {
        return this.friendlyName;
    }
}