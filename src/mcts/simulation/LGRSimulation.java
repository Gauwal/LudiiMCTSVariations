package mcts.simulation;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ThreadLocalRandom;

import game.Game;
import main.collections.FastArrayList;
import other.context.Context;
import other.move.Move;
import other.playout.PlayoutMoveSelector;
import other.trial.Trial;
import playout_move_selectors.EpsilonGreedyWrapper;
import search.mcts.MCTS;
import search.mcts.playout.PlayoutStrategy;

/**
 * Last Good Reply (LGR) playout strategy.
 *
 * Remembers successful move replies: when opponent plays move X and we respond
 * with move Y leading to a good outcome, we store "X → Y" as a good reply.
 * Next time opponent plays X (anywhere in tree), we try Y first.
 *
 * Key advantages:
 * - Nearly zero computational overhead
 * - Captures local tactical patterns and micro-tactics
 * - Works especially well in capture-based games
 * - Strong improvement over random playouts
 *
 * Best suited for:
 * - Tactical deterministic games (Go variants, Breakthrough)
 * - Capture-based board games
 * - Games with strong local move interactions
 *
 * @author Gauwain Savary-Kerneïs
 */
public class LGRSimulation implements PlayoutStrategy
{

    //-------------------------------------------------------------------------

    /** Auto-end playouts in a draw if they take more turns than this */
    protected int playoutTurnLimit = -1;

    /** Epsilon for epsilon-greedy move selection */
    protected double epsilon = 0.0;

    /** Threshold score for updating LGR table (only update on good outcomes) */
    protected double updateThreshold = 0.5;

    /** Whether to use decay/forgetting for old LGR entries */
    protected boolean useDecay = false;

    /** Decay factor for forgetting old entries (lower = forget faster) */
    protected double decayFactor = 0.95;

    /** For every thread, an LGR-based PlayoutMoveSelector */
    protected ThreadLocal<LGRMoveSelector> moveSelector = ThreadLocal.withInitial(() -> new LGRMoveSelector(this));

    /** Global LGR table: maps opponent move hash to our best reply move */
    protected final ConcurrentHashMap<Long, LGREntry> lgrTable = new ConcurrentHashMap<>();

    //-------------------------------------------------------------------------

    /**
     * Constructor with default values:
     * - No playout limit
     * - No epsilon (pure greedy LGR)
     * - Update threshold 0.5 (only on wins)
     */
    public LGRSimulation()
    {
        this.playoutTurnLimit = -1;
        this.epsilon = 0.0;
        this.updateThreshold = 0.5;
        this.useDecay = false;
        this.decayFactor = 0.95;
    }

    /**
     * Constructor with custom parameters
     * @param playoutTurnLimit Maximum playout length (-1 for no limit)
     * @param epsilon Exploration rate for epsilon-greedy
     * @param updateThreshold Minimum score to update LGR table
     * @param useDecay Whether to decay old LGR entries
     */
    public LGRSimulation(
            final int playoutTurnLimit,
            final double epsilon,
            final double updateThreshold,
            final boolean useDecay)
    {
        this.playoutTurnLimit = playoutTurnLimit;
        this.epsilon = epsilon;
        this.updateThreshold = updateThreshold;
        this.useDecay = useDecay;
        this.decayFactor = 0.95;
    }

    //-------------------------------------------------------------------------

    @Override
    public Trial runPlayout(final MCTS mcts, final Context context)
    {
        final LGRMoveSelector lgr = moveSelector.get();
        lgr.mcts = mcts;
        lgr.moveSequence.clear();

        // Run playout with epsilon-greedy wrapper if epsilon > 0
        final Trial trial = context.game().playout(
                context,
                null,
                1.0,
                epsilon > 0.0 ? new EpsilonGreedyWrapper(lgr, epsilon) : lgr,
                -1,
                playoutTurnLimit,
                ThreadLocalRandom.current()
        );

        // Update LGR table based on playout outcome
        updateLGRTable(context, lgr.moveSequence);

        lgr.mcts = null;
        return trial;
    }

    /**
     * Update the LGR table with move pairs from this playout if outcome was good
     * @param context
     * @param moveSequence
     */
    private void updateLGRTable(
            final Context context,
            final List<Move> moveSequence)
    {
        if (moveSequence.size() < 2)
            return;

        // Get final utilities to see if we should update
        final double[] utilities = context.trial().ranking();

        // Apply decay to all existing entries if enabled
        if (useDecay)
        {
            for (final LGREntry entry : lgrTable.values())
            {
                entry.score *= decayFactor;
            }
        }

        // Update LGR for each move pair (opponent move -> our reply)
        for (int i = 1; i < moveSequence.size(); ++i)
        {
            final Move opponentMove = moveSequence.get(i - 1);
            final Move ourReply = moveSequence.get(i);

            // Check if outcome was good enough to store this reply
            final int ourPlayer = ourReply.mover();
            final double ourScore = utilities[context.state().playerToAgent(ourPlayer)];

            if (ourScore >= updateThreshold)
            {
                // Create hash for opponent move
                final long opponentMoveHash = computeMoveHash(opponentMove);

                // Get or create entry
                final LGREntry existing = lgrTable.get(opponentMoveHash);

                if (existing == null || ourScore > existing.score)
                {
                    // Store this as the new best reply
                    lgrTable.put(opponentMoveHash, new LGREntry(ourReply, ourScore));
                }
            }
        }
    }

    /**
     * Compute a hash for a move to use as LGR table key
     * @param move
     * @return Hash value
     */
    private long computeMoveHash(final Move move)
    {
        // Simple hash combining move properties
        long hash = 17;
        hash = 31 * hash + move.from();
        hash = 31 * hash + move.to();
        hash = 31 * hash + move.mover();

        // Include level info for stacking games
        if (move.levelFrom() != 0 || move.levelTo() != 0)
        {
            hash = 31 * hash + move.levelFrom();
            hash = 31 * hash + move.levelTo();
        }

        return hash;
    }

    /**
     * Look up the last good reply for an opponent move
     * @param opponentMove
     * @return The stored reply move, or null if none found
     */
    protected Move getLGRReply(final Move opponentMove)
    {
        final long hash = computeMoveHash(opponentMove);
        final LGREntry entry = lgrTable.get(hash);
        return entry != null ? entry.replyMove : null;
    }

    @Override
    public int backpropFlags()
    {
        return 0;
    }

    //-------------------------------------------------------------------------

    @Override
    public boolean playoutSupportsGame(final Game game)
    {
        if (game.isDeductionPuzzle())
            return (playoutTurnLimit > 0);
        else
            return true;
    }

    @Override
    public void customise(final String[] inputs)
    {
        for (int i = 1; i < inputs.length; ++i)
        {
            final String input = inputs[i];

            if (input.toLowerCase().startsWith("playoutturnlimit="))
            {
                playoutTurnLimit = Integer.parseInt(
                        input.substring("playoutturnlimit=".length())
                );
            }
            else if (input.toLowerCase().startsWith("epsilon="))
            {
                epsilon = Double.parseDouble(
                        input.substring("epsilon=".length())
                );
            }
            else if (input.toLowerCase().startsWith("updatethreshold="))
            {
                updateThreshold = Double.parseDouble(
                        input.substring("updatethreshold=".length())
                );
            }
            else if (input.toLowerCase().startsWith("usedecay="))
            {
                useDecay = Boolean.parseBoolean(
                        input.substring("usedecay=".length())
                );
            }
            else if (input.toLowerCase().startsWith("decayfactor="))
            {
                decayFactor = Double.parseDouble(
                        input.substring("decayfactor=".length())
                );
            }
        }
    }

    /**
     * @return The turn limit we use in playouts
     */
    public int playoutTurnLimit()
    {
        return playoutTurnLimit;
    }

    //-------------------------------------------------------------------------

    /**
     * Entry in the LGR table storing a reply move and its score
     */
    protected static class LGREntry
    {
        /** The reply move to make */
        public final Move replyMove;

        /** Score associated with this reply (for comparing which reply is best) */
        public double score;

        public LGREntry(final Move replyMove, final double score)
        {
            this.replyMove = replyMove;
            this.score = score;
        }
    }

    //-------------------------------------------------------------------------

    /**
     * Playout Move Selector for LGR.
     *
     * Checks if the opponent's last move has a stored "last good reply"
     * and tries that move first if available and legal.
     *
     * @author Gauwain Savary-Kerneïs
     */
    protected static class LGRMoveSelector extends PlayoutMoveSelector
    {
        /** Reference to parent LGRSimulation for accessing LGR table */
        protected final LGRSimulation parent;

        /** MCTS from which to get context */
        protected MCTS mcts = null;

        /** Track move sequence during playout for later LGR updates */
        protected final List<Move> moveSequence = new ArrayList<Move>();

        public LGRMoveSelector(final LGRSimulation parent)
        {
            this.parent = parent;
        }

        @Override
        public Move selectMove
                (
                        final Context context,
                        final FastArrayList<Move> maybeLegalMoves,
                        final int p,
                        final IsMoveReallyLegal isMoveReallyLegal
                )
        {
            // Get opponent's last move if available
            Move lastOpponentMove = null;
            if (context.trial().numMoves() > 0)
            {
                final Iterator<Move> moveIterator = context.trial().reverseMoveIterator();
                if (moveIterator.hasNext())
                {
                    final Move lastMove = moveIterator.next();
                    // Make sure it's actually opponent's move, not our own
                    if (lastMove.mover() != p)
                    {
                        lastOpponentMove = lastMove;
                    }
                }
            }

            // If we have an opponent move, check for a stored good reply
            if (lastOpponentMove != null)
            {
                final Move lgrReply = parent.getLGRReply(lastOpponentMove);

                if (lgrReply != null)
                {
                    // Check if this LGR reply is in our legal moves
                    for (int i = 0; i < maybeLegalMoves.size(); ++i)
                    {
                        final Move candidateMove = maybeLegalMoves.get(i);

                        // Check if this move matches our LGR reply
                        if (movesMatch(candidateMove, lgrReply))
                        {
                            if (isMoveReallyLegal.checkMove(candidateMove))
                            {
                                moveSequence.add(candidateMove);
                                return candidateMove;
                            }
                            // If LGR reply is not actually legal, fall through to random
                            break;
                        }
                    }
                }
            }

            // No LGR reply available, or LGR reply was illegal - fall back to random
            int numLegalMoves = maybeLegalMoves.size();

            while (numLegalMoves > 0)
            {
                final int r = ThreadLocalRandom.current().nextInt(numLegalMoves);
                --numLegalMoves;

                final Move move = maybeLegalMoves.get(r);

                if (isMoveReallyLegal.checkMove(move))
                {
                    moveSequence.add(move);
                    return move;
                }
                else
                {
                    // Swap with last element and reduce size
                    maybeLegalMoves.set(r, maybeLegalMoves.get(numLegalMoves));
                    maybeLegalMoves.set(numLegalMoves, move);
                }
            }

            // No legal moves
            return null;
        }

        /**
         * Check if two moves match (same from/to positions and basic properties)
         * @param move1
         * @param move2
         * @return true if moves match
         */
        private boolean movesMatch(final Move move1, final Move move2)
        {
            if (move1.from() != move2.from() || move1.to() != move2.to())
                return false;

            if (move1.mover() != move2.mover())
                return false;

            // Check levels for stacking games
            if (move1.levelFrom() != move2.levelFrom() || move1.levelTo() != move2.levelTo())
                return false;

            return true;
        }

    }

    //-------------------------------------------------------------------------

}