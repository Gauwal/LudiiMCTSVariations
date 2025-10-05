package mcts.simulation;

import game.Game;
import other.context.Context;

/**
 * Policy for running simulations (playouts) from a given state.
 */
public interface SimulationPolicy
{
    /**
     * Run a simulation from the given context to a terminal state.
     *
     * @param context The game state to simulate from
     * @param game The game being played
     * @return Array of utilities for all players (values typically in [-1.0, 1.0])
     */
    double[] runSimulation(Context context, Game game);

    /**
     * @return The friendly name of this simulation policy
     */
    String getName();
}