package mcts.selection;

import game.Game;
import mcts.MCTSVariations.Node;
import other.context.Context;
import other.move.Move;

import java.util.concurrent.ThreadLocalRandom;

/**
 * UCB1-Tuned Selection - enhancement of UCB1 that uses variance to tune bounds more finely.
 * Replaces standard exploration term with variance-based bound.
 *
 * Reference: Section 5.1.1 of MCTS Survey
 */
public class UCB1TunedSelection implements SelectionPolicy {
    String friendlyName = "UCB1 Tuned";

    @Override
    public Node selectLeaf(Node current, Game game) {
        // Traverse tree
        while (true) {
            if (current.context.trial().over()) {
                break;
            }

            current = select(current);

            if (current.visitCount == 0) {
                break;
            }
        }
        return current;
    }

    private Node select(final Node current) {
        if (!current.unexpandedMoves.isEmpty()) {
            final Move move = current.unexpandedMoves.remove(
                    ThreadLocalRandom.current().nextInt(current.unexpandedMoves.size()));

            final Context context = new Context(current.context);
            context.game().apply(context, move);

            return new Node(current, move, context);
        }

        // Use UCB1-Tuned formula
        Node bestChild = null;
        double bestValue = Double.NEGATIVE_INFINITY;
        final double parentLn = Math.log(Math.max(1, current.visitCount));
        int numBestFound = 0;

        final int mover = current.context.state().mover();

        for (Node child : current.children) {
            final double exploit = child.scoreSums[mover] / child.visitCount;

            // Calculate variance term V(s)
            final double variance = calculateVariance(child, mover);

            // UCB1-Tuned exploration term
            final double explore = Math.sqrt(
                    (parentLn / child.visitCount) * Math.min(0.25, variance)
            );

            final double ucb1TunedValue = exploit + explore;

            if (ucb1TunedValue > bestValue) {
                bestValue = ucb1TunedValue;
                bestChild = child;
                numBestFound = 1;
            } else if (ucb1TunedValue == bestValue &&
                    ThreadLocalRandom.current().nextInt() % ++numBestFound == 0) {
                bestChild = child;
            }
        }

        return bestChild;
    }

    /**
     * Calculate variance term for UCB1-Tuned.
     * Note: This is a simplified version. Full implementation would need to track
     * sum of squared rewards per node.
     */
    private double calculateVariance(Node node, int player) {
        if (node.visitCount <= 1) {
            return 0.25; // Maximum variance for [0,1] rewards
        }

        // Simplified variance calculation
        // Proper implementation would track Σ(reward²) separately
        double mean = node.scoreSums[player] / node.visitCount;
        double variance = mean * (1.0 - mean); // Approximation for [0,1] rewards

        // Add correction term
        variance += Math.sqrt(2.0 * Math.log(node.visitCount) / node.visitCount);

        return variance;
    }

    @Override
    public String getName() {
        return this.friendlyName;
    }
}