package mcts.backpropagation;

import game.Game;
import mcts.MCTSVariations.Node;

public class StandardBackprop implements BackpropagationPolicy {
    String friendlyName = "Standard";

    @Override
    public void backpropagate(Node leaf, double[] utilities, Game game) {
        // Backpropagate utilities through the tree
        Node current = leaf;
        while (current != null)
        {
            current.visitCount += 1;
            for (int p = 1; p <= game.players().count(); ++p)
            {
                current.scoreSums[p] += utilities[p];
            }
            current = current.parent;
        }
    }

    @Override
    public String getName() {
        return friendlyName;
    }
}
