package mcts.simulation;

import game.Game;
import main.collections.FastArrayList;
import other.context.Context;
import other.move.Move;

import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ThreadLocalRandom;

/**
 * Last Good Reply (LGR) Simulation
 *
 * Remembers successful replies to opponent moves and prefers them in simulations.
 * Reference: Section 6.1.8 of MCTS Survey
 */
public class LGRSimulation implements SimulationPolicy {
    private final Map<String, Map<String, LGRStats>> replyTable = new HashMap<>(); // [opponentMove][reply] -> stats
    private final String friendlyName = "LGR";

    private static class LGRStats {
        int successCount = 0;
        int totalCount = 0;

        double getSuccessRate() {
            return totalCount == 0 ? 0.0 : (double) successCount / totalCount;
        }
    }


    @Override
    public double[] runSimulation(Context context, Game game) {
        Context contextEnd = new Context(context);

        java.util.List<Move> moveSequence = new java.util.ArrayList<>();

        Move prevMove = null;

        // Run simulation
        while (!contextEnd.trial().over()) {
            final FastArrayList<Move> legalMoves = game.moves(contextEnd).moves();
            final Move selectedMove = selectMoveLGR(legalMoves, prevMove);

            game.apply(contextEnd, selectedMove);
            moveSequence.add(selectedMove);
            prevMove = selectedMove;
        }

        final double[] utilities = other.RankUtils.utilities(contextEnd);

        updateLGRTable(moveSequence, utilities);

        return utilities;
    }

    /**
     * Select move using LGR: prefer replies that were successful against opponent's last move
     */
    private Move selectMoveLGR(FastArrayList<Move> legalMoves, Move opponentMove) {
        if (opponentMove == null) {
            // No previous move context - choose randomly
            return legalMoves.get(ThreadLocalRandom.current().nextInt(legalMoves.size()));
        }

        final String opponentMoveKey = getMoveKey(opponentMove);
        final Map<String, LGRStats> replies = replyTable.get(opponentMoveKey);

        if (replies == null || replies.isEmpty()) {
            // No known replies - choose randomly
            return legalMoves.get(ThreadLocalRandom.current().nextInt(legalMoves.size()));
        }

        // Find the best known reply that is legal
        Move bestReply = null;
        double bestSuccessRate = -1.0;
        int numBestFound = 0;

        for (Move move : legalMoves) {
            final String moveKey = getMoveKey(move);
            final LGRStats stats = replies.get(moveKey);

            if (stats != null) {
                final double successRate = stats.getSuccessRate();

                if (successRate > bestSuccessRate) {
                    bestSuccessRate = successRate;
                    bestReply = move;
                    numBestFound = 1;
                } else if (successRate == bestSuccessRate &&
                        ThreadLocalRandom.current().nextInt() % ++numBestFound == 0) {
                    bestReply = move; // Random tie-break
                }
            }
        }

        return bestReply != null ? bestReply :
                legalMoves.get(ThreadLocalRandom.current().nextInt(legalMoves.size()));
    }

    private void updateLGRTable(java.util.List<Move> moveSequence, double[] utilities) {
        if (moveSequence.size() < 2) return;

        // Determine if the simulation was successful (win for the player)
        boolean[] isWin = new boolean[utilities.length];
        for (int i = 1; i < utilities.length; i++) {
            isWin[i] = (utilities[i] > 0.5); // Threshold for "win"
        }

        // Update replies for each move in context of previous opponent move
        for (int i = 1; i < moveSequence.size(); i++) {
            final Move opponentMove = moveSequence.get(i - 1);
            final Move replyMove = moveSequence.get(i);
            final int replyPlayer = replyMove.mover();

            final String opponentKey = getMoveKey(opponentMove);
            final String replyKey = getMoveKey(replyMove);

            final Map<String, LGRStats> replies =
                    replyTable.computeIfAbsent(opponentKey, k -> new HashMap<>());

            final LGRStats stats = replies.computeIfAbsent(replyKey, k -> new LGRStats());

            stats.totalCount++;
            if (isWin[replyPlayer]) {
                stats.successCount++;
            }
        }
    }

    private String getMoveKey(Move move) {
        return move.toString();
    }

    @Override
    public String getName() {
        return friendlyName;
    }
}