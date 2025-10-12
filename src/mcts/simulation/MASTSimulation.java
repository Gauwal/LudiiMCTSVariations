package mcts.simulation;

import game.Game;
import main.collections.FastArrayList;
import other.context.Context;
import other.move.Move;

import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ThreadLocalRandom;

/**
 * Move-Average Sampling Technique (MAST) Simulation
 *
 * Biases simulation moves based on their historical success rates.
 * Reference: Section 6.1.4 of MCTS Survey
 */
public class MASTSimulation implements SimulationPolicy {
    private final Map<String, MASTStats> actionStats = new HashMap<>();
    private final double explorationFactor;
    private final String friendlyName;

    private static class MASTStats {
        double totalScore = 0.0;
        int visitCount = 0;

        double getAverage() {
            return visitCount == 0 ? 0.0 : totalScore / visitCount;
        }
    }

    public MASTSimulation() {
        this(0.1);
    }

    public MASTSimulation(double explorationFactor) {
        this.explorationFactor = explorationFactor;
        this.friendlyName = "MAST (ε=" + explorationFactor + ")";
    }

    @Override
    public double[] runSimulation(Context context, Game game) {
        Context contextEnd = new Context(context);

        // Track moves made during simulation for later updating
        java.util.List<Move> simulationMoves = new java.util.ArrayList<>();

        // Run simulation with MAST-biased move selection
        while (!contextEnd.trial().over()) {
            final FastArrayList<Move> legalMoves = game.moves(contextEnd).moves();
            final Move selectedMove = selectMoveMAST(legalMoves, contextEnd.state().mover());

            game.apply(contextEnd, selectedMove);
            simulationMoves.add(selectedMove);
        }

        // Get final utilities
        final double[] utilities = other.RankUtils.utilities(contextEnd);

        // Update MAST statistics with simulation results
        updateMASTStats(simulationMoves, utilities);

        return utilities;
    }

    /**
     * Select move using MAST: combines exploitation (historical success)
     * with exploration (randomness)
     */
    private Move selectMoveMAST(FastArrayList<Move> legalMoves, int mover) {
        // With probability ε, choose randomly for exploration
        if (ThreadLocalRandom.current().nextDouble() < explorationFactor) {
            return legalMoves.get(ThreadLocalRandom.current().nextInt(legalMoves.size()));
        }

        // Otherwise, choose based on MAST statistics
        Move bestMove = null;
        double bestScore = Double.NEGATIVE_INFINITY;
        int numBestFound = 0;

        for (Move move : legalMoves) {
            final String moveKey = getMoveKey(move);
            final MASTStats stats = actionStats.get(moveKey);
            final double score = (stats == null) ? 0.0 : stats.getAverage();

            if (score > bestScore) {
                bestScore = score;
                bestMove = move;
                numBestFound = 1;
            } else if (score == bestScore &&
                    ThreadLocalRandom.current().nextInt() % ++numBestFound == 0) {
                bestMove = move; // Random tie-break
            }
        }

        return bestMove != null ? bestMove :
                legalMoves.get(ThreadLocalRandom.current().nextInt(legalMoves.size()));
    }

    private void updateMASTStats(java.util.List<Move> moves, double[] utilities) {
        for (Move move : moves) {
            final String moveKey = getMoveKey(move);
            final int mover = move.mover();
            final double reward = utilities[mover];

            actionStats.computeIfAbsent(moveKey, k -> new MASTStats())
                    .totalScore += reward;
            actionStats.get(moveKey).visitCount += 1;
        }
    }

    private String getMoveKey(Move move) {
        // Use string representation as key
        return move.toString();
    }

    @Override
    public String getName() {
        return friendlyName;
    }
}