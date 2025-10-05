package mcts.selection;

import game.Game;
import mcts.MCTSVariations.Node;



/**
 * Policy for tree traversal and expansion.
 * Combines selection and expansion (may need to be separated in future)
 */
public interface SelectionPolicy
{
    /**
     * Traverse the tree and return a leaf node to simulate from.
     * This combines both selection (choosing which child to descend to)
     * and expansion (adding new nodes to the tree).
     *
     * @param root The root node to start traversal from
     * @param game The game being played
     * @return A leaf node from which to run a simulation
     */
    Node selectLeaf(Node root, Game game);

    /**
     * @return The friendly name of this selection policy
     */
    String getName();
}
