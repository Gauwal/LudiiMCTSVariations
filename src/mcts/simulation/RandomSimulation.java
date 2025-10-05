package mcts.simulation;

import java.util.concurrent.ThreadLocalRandom;

import game.Game;
import other.RankUtils;
import other.context.Context;

public class RandomSimulation implements SimulationPolicy {
    String friendlyName = "Random";

    @Override
    public double[] runSimulation(Context context, Game game) {

        Context contextEnd = context;

        if (!contextEnd.trial().over())
        {
            // Run a playout if we don't already have a terminal game state
            contextEnd = new Context(contextEnd);
            game.playout(
                    contextEnd,
                    null,
                    -1.0,
                    null,
                    0,
                    -1,
                    ThreadLocalRandom.current()
            );
        }

        // This computes utilities for all players at the end of the playout,
        // which will all be values in [-1.0, 1.0]
        return RankUtils.utilities(contextEnd);
    }

    @Override
    public String getName() {
        return friendlyName;
    }
}
