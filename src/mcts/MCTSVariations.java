package mcts;

import game.Game;
import mcts.backpropagation.*;
import mcts.selection.*;
import other.AI;
import other.context.Context;
import other.move.Move;
import search.mcts.MCTS;
import search.mcts.backpropagation.*;
import search.mcts.finalmoveselection.*;
import search.mcts.playout.*;
import search.mcts.selection.*;

import java.util.Locale;

/**
 * Wrapper around Ludii's built-in MCTS implementation that exposes a string-based
 * configuration mirroring the earlier custom policies.
 */
public class MCTSVariations extends AI
{
    /** Our player index */
    protected int player = -1;

    /** Delegated Ludii MCTS implementation */
    private final MCTS mcts;

    /** Labels used for the friendly name */
    private final String selectionLabel;
    private final String playoutLabel;
    private final String backpropLabel;

    /**
     * Constructor (name of selection, simulation, backpropagation policies)
     */
    public MCTSVariations(final String selection, final String simulation, final String backpropagation, final String finalMoveSelect)
    {
        final StrategyChoice<SelectionStrategy> selectionChoice = buildSelectionStrategy(selection);
        final StrategyChoice<PlayoutStrategy> playoutChoice = buildPlayoutStrategy(simulation);
        final StrategyChoice<BackpropagationStrategy> backpropChoice = buildBackpropStrategy(backpropagation);
        final FinalMoveSelectionStrategy finalMoveSelection = buildFinalMoveSelection(finalMoveSelect);

        this.mcts = new MCTS(
                selectionChoice.strategy,
                playoutChoice.strategy,
                backpropChoice.strategy,
                finalMoveSelection
        );

        this.mcts.setTreeReuse(false);

        this.selectionLabel = selectionChoice.label;
        this.playoutLabel = playoutChoice.label;
        this.backpropLabel = backpropChoice.label;

        this.friendlyName = String.format("MCTS [%s | %s | %s]",
                selectionLabel, playoutLabel, backpropLabel);
    }

    @Override
    public Move selectAction(
            final Game game,
            final Context context,
            final double maxSeconds,
            final int maxIterations,
            final int maxDepth
    )
    {
        return mcts.selectAction(game, context, maxSeconds, maxIterations, maxDepth);
    }

    @Override
    public void initAI(final Game game, final int playerID)
    {
        this.player = playerID;
        mcts.initAI(game, playerID);
    }

    @Override
    public void closeAI()
    {
        mcts.closeAI();
    }

    @Override
    public boolean supportsGame(final Game game)
    {
        return mcts.supportsGame(game);
    }

    private static StrategyChoice<SelectionStrategy> buildSelectionStrategy(final String name)
    {
        final String normalized = normalize(name);

        if ("ag0".equals(normalized) || "ag0 selection".equals(normalized))
            return new StrategyChoice<>(new AG0Selection(), "AG0Selection");

        if ("exit".equals(normalized) || "exit selection".equals(normalized))
            return new StrategyChoice<>(new ExItSelection(0.5), "ExItSelection");

        if ("mcbrave".equals(normalized))
            return new StrategyChoice<>(new McBRAVE(), "McBRAVE");

        if ("mcgrave".equals(normalized))
            return new StrategyChoice<>(new McGRAVE(), "McGRAVE");

        if ("noisy ag0".equals(normalized) || "noisy ag0selection".equals(normalized))
            return new StrategyChoice<>(new NoisyAG0Selection(), "NoisyAG0Selection");

        if ("progressive bias".equals(normalized))
            return new StrategyChoice<>(new ProgressiveBias(), "ProgressiveBias");

        if ("progressive history".equals(normalized))
            return new StrategyChoice<>(new ProgressiveHistory(), "ProgressiveHistory");

        if ("ucb1 grave".equals(normalized) || "ucb1grave".equals(normalized))
            return new StrategyChoice<>(new UCB1GRAVE(), "UCB1GRAVE");

        if ("ucb1 tuned".equals(normalized) || "ucb1tuned".equals(normalized))
            return new StrategyChoice<>(new UCB1Tuned(), "UCB1Tuned");

        if ("progressivewidening".equals(normalized) || "progressive widening".equals(normalized))
            return new StrategyChoice<>(new ProgressiveWidening(), "Progressive Widening");

        if ("implicitminimax".equals(normalized) || "implicit minimax".equals(normalized))
            return new StrategyChoice<>(new ImplicitMinimaxSelection(), "Implicit Minimax");

        if ("alphabeta".equals(normalized) || "alpha beta".equals(normalized) || "alpha-beta".equals(normalized))
            return new StrategyChoice<>(new AlphaBetaSelection(), "Alpha-Beta");

        // Fallback
        return new StrategyChoice<>(new UCB1(), "UCB1");
    }

    private static StrategyChoice<PlayoutStrategy> buildPlayoutStrategy(final String name)
    {
        final String normalized = normalize(name);

        if ("heuristic".equals(normalized) || "heuristic playout".equals(normalized))
            return new StrategyChoice<>(new HeuristicPlayout(), "HeuristicPlayout");

        if ("heuristic samping".equals(normalized) || "heuristic samping playout".equals(normalized))
            return new StrategyChoice<>(new HeuristicSampingPlayout(), "HeuristicSampingPlayout");

        if ("mast".equals(normalized))
            return new StrategyChoice<>(new MAST(), "MAST");

        if ("nst".equals(normalized))
            return new StrategyChoice<>(new NST(), "NST");

        if ("playouths".equals(normalized) || "hs playout".equals(normalized))
            return new StrategyChoice<>(new PlayoutHS(), "PlayoutHS");

        if ("lgr".equals(normalized) || "last good reply".equals(normalized))
            return new StrategyChoice<>(new PlayoutHS(), "Last Good Reply");

        // fallback
        return new StrategyChoice<>(new RandomPlayout(), "RandomPlayout");
    }


    private static StrategyChoice<BackpropagationStrategy> buildBackpropStrategy(final String name)
    {
        final String normalized = normalize(name);

        if ("heuristic".equals(normalized))
            return new StrategyChoice<>(new HeuristicBackprop(), "HeuristicBackprop");

        if ("alphago".equals(normalized))
            return new StrategyChoice<>(new AlphaGoBackprop(), "AlphaGoBackprop");

        if ("qualitative".equals(normalized) || "qualitative bonus".equals(normalized))
            return new StrategyChoice<>(new QualitativeBonus(), "QualitativeBonus");

        if ("scorebounded".equals(normalized) || "score bounded".equals(normalized))
            return new StrategyChoice<>(new ScoreBoundedBackprop(), "ScoreBounded");

        if ("implicitminimax".equals(normalized) || "implicit minimax".equals(normalized))
            return new StrategyChoice<>(new ImplicitMinimaxBackprop(), "ImplicitMinimax");

        //  fall back to Monte Carlo backpropagation
        return new StrategyChoice<>(new MonteCarloBackprop(), "MonteCarloBackprop");
    }

    private static FinalMoveSelectionStrategy buildFinalMoveSelection(final String name)
    {
        final String normalized = normalize(name);

        if ("max avg".equals(normalized) || "maxavgscore".equals(normalized))
            return new MaxAvgScore();

        if ("proportional exp".equals(normalized) || "proportionalexpvisitcount".equals(normalized))
            return new ProportionalExpVisitCount(0.5);

        if ("robust".equals(normalized) || "robustchild".equals(normalized))
            return new RobustChild();

        return new RobustChild(); // fallback
    }


    private static String normalize(final String value)
    {
        if (value == null)
            return "";
        return value.trim().toLowerCase(Locale.ROOT);
    }

    /**
     * Small helper to pair strategies with their human-readable labels.
     */
    private static final class StrategyChoice<T>
    {
        final T strategy;
        final String label;

        StrategyChoice(final T strategy, final String label)
        {
            this.strategy = strategy;
            this.label = label;
        }
    }
}

