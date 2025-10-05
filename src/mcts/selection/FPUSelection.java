package mcts.selection;

import game.Game;
import mcts.MCTSVariations.Node;
import other.context.Context;
import other.move.Move;

import java.util.concurrent.ThreadLocalRandom;

/**
 * First Play Urgency (FPU) Selection.
 * Assigns a fixed urgency value to unvisited nodes to encourage early exploitation.
 *
 * Reference: Section 5.2.1 of MCTS Survey
 */
public class FPUSelection implements SelectionPolicy {
    private final double fpuValue;
    String friendlyName;

    /**
     * Constructor with custom FPU value
     * @param fpuValue The fixed value assigned to unvisited nodes (typically 0.0 to 1.0)
     */
    public FPUSelection(double fpuValue) {
        this.fpuValue = fpuValue;
        this.friendlyName = "FPU (value=" + fpuValue + ")";
    }

    /**
     * Default constructor - uses optimistic FPU value
     */
    public FPUSelection() {
        this(0.5); // Moderate urgency
    }

    @Override
    public Node selectLeaf(Node current, Game game) {
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
        // Check for unexpanded moves
        if (!current.unexpandedMoves.isEmpty()) {
            // Instead of random selection, we could prioritize based on FPU
            // But for expansion, we still expand randomly
            final Move move = current.unexpandedMoves.remove(
                    ThreadLocalRandom.current().nextInt(current.unexpandedMoves.size()));

            final Context context = new Context(current.context);
            context.game().apply(context, move);

            return new Node(current, move, context);
        }

        // Select using UCB1 with FPU for unvisited children
        Node bestChild = null;
        double bestValue = Double.NEGATIVE_INFINITY;
        final double twoParentLog = 2.0 * Math.log(Math.max(1, current.visitCount));
        int numBestFound = 0;

        final int mover = current.context.state().mover();

        for (Node child : current.children) {
            double value;

            if (child.visitCount == 0) {
                // Assign FPU value to unvisited nodes
                value = fpuValue;
            } else {
                // Standard UCB1 for visited nodes
                final double exploit = child.scoreSums[mover] / child.visitCount;
                final double explore = Math.sqrt(twoParentLog / child.visitCount);
                value = exploit + explore;
            }

            if (value > bestValue) {
                bestValue = value;
                bestChild = child;
                numBestFound = 1;
            } else if (value == bestValue &&
                    ThreadLocalRandom.current().nextInt() % ++numBestFound == 0) {
                bestChild = child;
            }
        }

        return bestChild;
    }

    @Override
    public String getName() {
        return this.friendlyName;
    }
}