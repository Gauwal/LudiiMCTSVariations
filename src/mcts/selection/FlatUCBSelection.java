package mcts.selection;

import game.Game;
import mcts.MCTSVariations.Node;
import other.context.Context;
import other.move.Move;

import java.util.concurrent.ThreadLocalRandom;

/**
 * Flat UCB Selection - treats all leaf nodes as a single multi-armed bandit problem.
 * Does not build a deep tree; only expands from root and selects among root children using UCB1.
 *
 * Reference: Section 4.1 of MCTS Survey
 */
public class FlatUCBSelection implements SelectionPolicy {
    String friendlyName = "Flat UCB";

    @Override
    public Node selectLeaf(Node current, Game game) {
        // Flat UCB: only expand and select at root level

        if (current.context.trial().over()) {
            return current;
        }

        // If there are unexpanded moves at root, expand one
        if (!current.unexpandedMoves.isEmpty()) {
            final Move move = current.unexpandedMoves.remove(
                    ThreadLocalRandom.current().nextInt(current.unexpandedMoves.size()));

            final Context context = new Context(current.context);
            context.game().apply(context, move);

            return new Node(current, move, context);
        }

        // Select among root children using UCB1
        Node bestChild = selectBestChildUCB1(current);

        // Return the child directly - no further tree traversal
        return bestChild;
    }

    private Node selectBestChildUCB1(final Node parent) {
        Node bestChild = null;
        double bestValue = Double.NEGATIVE_INFINITY;
        final double twoParentLog = 2.0 * Math.log(Math.max(1, parent.visitCount));
        int numBestFound = 0;

        final int mover = parent.context.state().mover();

        for (Node child : parent.children) {
            final double exploit = child.scoreSums[mover] / child.visitCount;
            final double explore = Math.sqrt(twoParentLog / child.visitCount);
            final double ucb1Value = exploit + explore;

            if (ucb1Value > bestValue) {
                bestValue = ucb1Value;
                bestChild = child;
                numBestFound = 1;
            } else if (ucb1Value == bestValue &&
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