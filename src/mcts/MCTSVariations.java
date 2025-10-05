package mcts;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ThreadLocalRandom;

import experiments.fastGameLengths.TrialRecord;
import game.Game;
import main.collections.FastArrayList;
import other.AI;
import other.RankUtils;
import other.context.Context;
import other.move.Move;

import mcts.selection.*;
import mcts.backpropagation.*;
import mcts.simulation.*;

public class MCTSVariations extends AI
{

    //-------------------------------------------------------------------------

    /** Our player index */
    protected int player = -1;

    /** Strategy components */
    protected SelectionPolicy selectionPolicy;
    protected SimulationPolicy simulationPolicy;
    protected BackpropagationPolicy backpropPolicy;

    //-------------------------------------------------------------------------

    /**
     * Constructor (name of selection, simulation, backpropagation policies)
     */
    public MCTSVariations(String selection, String simulation, String backpropagation)
    {
        //Selection
        if (selection == "default" || selection=="UCB1"){this.selectionPolicy = new UCB1Selection();}
        if (selection == "flat" || selection=="flat UCB"){this.selectionPolicy = new FlatUCBSelection();}
        if (selection == "UCB1 tuned"){this.selectionPolicy = new UCB1TunedSelection();}
        if (selection == "FPU" || selection == "first play urgency"){this.selectionPolicy = new FPUSelection(0.5);}


        //Simulation
        if (simulation == "default" || simulation == "random"){this.simulationPolicy =  new RandomSimulation();}

        //Backpropagation
        if (backpropagation == "default" || backpropagation == "standard"){this.backpropPolicy = new StandardBackprop();}
        if (backpropagation == "decay" || backpropagation == "decayingReward"){this.backpropPolicy = new DecayingRewardBackprop(0.5);}



        this.friendlyName = "MCTS Variation - "
                + this.selectionPolicy.getName() + "+"
                + this.simulationPolicy.getName() + "+"
                + this.backpropPolicy.getName() + "+";

    }


    @Override
    public Move selectAction
            (
                    final Game game,
                    final Context context,
                    final double maxSeconds,
                    final int maxIterations,
                    final int maxDepth
            )
    {
        final Node root = new Node(null, null, context);

        final long stopTime = (maxSeconds > 0.0) ? System.currentTimeMillis() + (long) (maxSeconds * 1000L) : Long.MAX_VALUE;
        final int maxIts = (maxIterations >= 0) ? maxIterations : Integer.MAX_VALUE;

        int numIterations = 0;

        while
        (
                numIterations < maxIts &&
                        System.currentTimeMillis() < stopTime &&
                        !wantsInterrupt
        )
        {
            // Selection + Expansion phase
            Node leaf = selectionPolicy.selectLeaf(root, game);

            // Simulation phase
            double[] utilities = simulationPolicy.runSimulation(leaf.context, game);

            // Backpropagation phase
            backpropPolicy.backpropagate(leaf, utilities, game);

            ++numIterations;
        }

        // Return the move we wish to play
        return finalMoveSelection(root);
    }



    /**
     * Selects the move we wish to play using the "Robust Child" strategy
     * (meaning that we play the move leading to the child of the root node
     * with the highest visit count).
     *
     * @param rootNode
     * @return
     */
    public static Move finalMoveSelection(final MCTSVariations.Node rootNode)
    {
        MCTSVariations.Node bestChild = null;
        int bestVisitCount = Integer.MIN_VALUE;
        int numBestFound = 0;

        final int numChildren = rootNode.children.size();

        for (int i = 0; i < numChildren; ++i)
        {
            final MCTSVariations.Node child = rootNode.children.get(i);
            final int visitCount = child.visitCount;

            if (visitCount > bestVisitCount)
            {
                bestVisitCount = visitCount;
                bestChild = child;
                numBestFound = 1;
            }
            else if
            (
                    visitCount == bestVisitCount &&
                            ThreadLocalRandom.current().nextInt() % ++numBestFound == 0
            )
            {
                // this case implements random tie-breaking
                bestChild = child;
            }
        }

        return bestChild.moveFromParent;
    }

    @Override
    public void initAI(final Game game, final int playerID)
    {
        this.player = playerID;
    }

    @Override
    public boolean supportsGame(final Game game)
    {
        if (game.isStochasticGame())
            return false;

        if (!game.isAlternatingMoveGame())
            return false;

        return true;
    }


    //-------------------------------------------------------------------------

    /**
     * Inner class for nodes
     *
     * @author Dennis Soemers
     */
    public static class Node
    {
        /** Our parent node */
        public final Node parent;

        /** The move that led from parent to this node */
        public final Move moveFromParent;

        /** This objects contains the game state for this node (this is why we don't support stochastic games) */
        public final Context context;
        /** Visit count for this node */
        public int visitCount = 0;

        /** For every player, sum of utilities / scores backpropagated through this node */
        public final double[] scoreSums;

        /** Child nodes */
        public final List<MCTSVariations.Node> children = new ArrayList<MCTSVariations.Node>();

        /** List of moves for which we did not yet create a child node */
        public final FastArrayList<Move> unexpandedMoves;

        /**
         * Constructor
         *
         * @param parent
         * @param moveFromParent
         * @param context
         */
        public Node(final MCTSVariations.Node parent, final Move moveFromParent, final Context context)
        {
            this.parent = parent;
            this.moveFromParent = moveFromParent;
            this.context = context;
            final Game game = context.game();
            scoreSums = new double[game.players().count() + 1];

            // For simplicity, we just take ALL legal moves.
            // This means we do not support simultaneous-move games.
            unexpandedMoves = new FastArrayList<Move>(game.moves(context).moves());

            if (parent != null)
                parent.children.add(this);
        }

    }

    //-------------------------------------------------------------------------

}
