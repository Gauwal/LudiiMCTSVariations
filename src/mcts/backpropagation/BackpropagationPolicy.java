package mcts.backpropagation;

import game.Game;
import mcts.MCTSVariations.Node;

/**
 * Policy for backpropagating simulation results through the tree.
 */
public interface BackpropagationPolicy
{
    /**
     * Update node statistics from the leaf up to the root based on simulation results.
     *
     * @param leaf The leaf node where the simulation started
     * @param utilities The utilities obtained from the simulation for all players
     * @param game The game being played
     */
    void backpropagate(Node leaf, double[] utilities, Game game);

    /**
     * @return The friendly name of this backpropagation policy
     */
    String getName();
}