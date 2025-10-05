package mcts.selection;

import game.Game;
import other.context.Context;
import other.move.Move;

import java.util.concurrent.ThreadLocalRandom;

import mcts.MCTSVariations.Node;

public class UCB1Selection implements SelectionPolicy {
    String friendlyName = "UCB1";

    @Override
    public Node selectLeaf(Node current, Game game) {
        // Traverse tree
        while (true)
        {
            if (current.context.trial().over())
            {
                // We've reached a terminal state
                break;
            }

            current = select(current);

            if (current.visitCount == 0)
            {
                // We've expanded a new node, time for playout!
                break;
            }
        }
        return current;
    }

    private Node select(final Node current)
    {
        if (!current.unexpandedMoves.isEmpty())
        {
            // randomly select an unexpanded move
            final Move move = current.unexpandedMoves.remove(
                    ThreadLocalRandom.current().nextInt(current.unexpandedMoves.size()));

            // create a copy of context
            final Context context = new Context(current.context);

            // apply the move
            context.game().apply(context, move);

            // create new node and return it
            return new Node(current, move, context);
        }

        // use UCB1 equation to select from all children, with random tie-breaking
        Node bestChild = null;
        double bestValue = Double.NEGATIVE_INFINITY;
        final double twoParentLog = 2.0 * Math.log(Math.max(1, current.visitCount));
        int numBestFound = 0;

        final int numChildren = current.children.size();
        final int mover = current.context.state().mover();

        for (int i = 0; i < numChildren; ++i)
        {
            final Node child = current.children.get(i);
            final double exploit = child.scoreSums[mover] / child.visitCount;
            final double explore = Math.sqrt(twoParentLog / child.visitCount);

            final double ucb1Value = exploit + explore;

            if (ucb1Value > bestValue)
            {
                bestValue = ucb1Value;
                bestChild = child;
                numBestFound = 1;
            }
            else if (ucb1Value == bestValue &&
                    ThreadLocalRandom.current().nextInt() % ++numBestFound == 0)
            {
                // this case implements random tie-breaking
                bestChild = child;
            }
        }

        return bestChild;
    }

    @Override
    public String getName() {
        return friendlyName;
    }
}
