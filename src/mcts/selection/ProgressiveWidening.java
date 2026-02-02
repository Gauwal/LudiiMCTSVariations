package mcts.selection;

import java.util.concurrent.ThreadLocalRandom;

import other.state.State;
import search.mcts.MCTS;
import search.mcts.nodes.BaseNode;
import search.mcts.selection.SelectionStrategy;

/**
 * Progressive Widening selection strategy.
 *
 * Gradually expands the number of children considered as the parent node
 * is visited more often. This prevents wasting search effort on evaluating
 * too many children early when visit counts are low.
 *
 * The maximum number of children to consider is: k * n^α
 * where n is the number of visits to the parent node,
 * k is a constant factor, and α controls the widening rate.
 *
 * Typical values: k = 1.0 to 2.0, α = 0.25 to 0.5
 *
 * @author Gauwain Savary-Kerneïs
 */
public class ProgressiveWidening implements SelectionStrategy
{

    //-------------------------------------------------------------------------

    /** Constant factor for widening formula (k) */
    protected double wideningConstant;

    /** Exponent for widening formula (α) */
    protected double wideningExponent;

    /** Exploration constant for UCB1 */
    protected double explorationConstant;

    //-------------------------------------------------------------------------

    /**
     * Constructor with default values:
     * k = 1.5, α = 0.5, exploration = sqrt(2)
     *
     * These defaults provide moderate widening suitable for games
     * with branching factors between 10-50.
     */
    public ProgressiveWidening()
    {
        this.wideningConstant = 1.5;
        this.wideningExponent = 0.5;
        this.explorationConstant = Math.sqrt(2.0);
    }

    /**
     * Constructor with custom parameters
     * @param wideningConstant (k) - scales the number of children
     * @param wideningExponent (α) - controls widening rate (0.25-0.5 typical)
     * @param explorationConstant - UCB1 exploration parameter
     */
    public ProgressiveWidening(
            final double wideningConstant,
            final double wideningExponent,
            final double explorationConstant)
    {
        this.wideningConstant = wideningConstant;
        this.wideningExponent = wideningExponent;
        this.explorationConstant = explorationConstant;
    }

    //-------------------------------------------------------------------------

    @Override
    public int select(final MCTS mcts, final BaseNode current)
    {
        int bestIdx = 0;
        double bestValue = Double.NEGATIVE_INFINITY;
        int numBestFound = 0;

        final int numChildren = current.numLegalMoves();
        final State state = current.contextRef().state();
        final int moverAgent = state.playerToAgent(state.mover());
        final double unvisitedValueEstimate =
                current.valueEstimateUnvisitedChildren(moverAgent);

        // Calculate how many children we allow to be active based on parent visits
        final int parentVisits = Math.max(1, current.numVisits());
        final int maxActiveChildren = Math.max(1, (int) Math.ceil(
                wideningConstant * Math.pow(parentVisits, wideningExponent)
        ));

        // Cap at total number of legal moves
        final int activeChildren = Math.min(maxActiveChildren, numChildren);

        final double parentLog = Math.log(Math.max(1, current.sumLegalChildVisits()));

        // Only consider children up to the widening threshold
        for (int i = 0; i < activeChildren; ++i)
        {
            final BaseNode child = current.childForNthLegalMove(i);
            final double exploit;
            final double explore;

            if (child == null)
            {
                // Unvisited child - prioritize exploration
                exploit = unvisitedValueEstimate;
                explore = Math.sqrt(parentLog);
            }
            else
            {
                // Visited child - use actual statistics
                exploit = child.exploitationScore(moverAgent);
                final int childVisits = Math.max(child.numVisits() + child.numVirtualVisits(), 1);
                explore = Math.sqrt(parentLog / childVisits);
            }

            final double ucb1Value = exploit + explorationConstant * explore;

            if (ucb1Value > bestValue)
            {
                bestValue = ucb1Value;
                bestIdx = i;
                numBestFound = 1;
            }
            else if
            (
                    ucb1Value == bestValue
                            &&
                            ThreadLocalRandom.current().nextInt() % ++numBestFound == 0
            )
            {
                bestIdx = i;
            }
        }

        return bestIdx;
    }

    //-------------------------------------------------------------------------

    @Override
    public int backpropFlags()
    {
        return 0;
    }

    @Override
    public int expansionFlags()
    {
        return 0;
    }

    @Override
    public void customise(final String[] inputs)
    {
        if (inputs.length > 1)
        {
            // We have more inputs than just the name of the strategy
            for (int i = 1; i < inputs.length; ++i)
            {
                final String input = inputs[i];

                if (input.startsWith("wideningconstant="))
                {
                    wideningConstant = Double.parseDouble(
                            input.substring("wideningconstant=".length()));
                }
                else if (input.startsWith("wideningexponent="))
                {
                    wideningExponent = Double.parseDouble(
                            input.substring("wideningexponent=".length()));
                }
                else if (input.startsWith("explorationconstant="))
                {
                    explorationConstant = Double.parseDouble(
                            input.substring("explorationconstant=".length()));
                }
                else
                {
                    System.err.println("ProgressiveWidening ignores unknown customisation: " + input);
                }
            }
        }
    }

    //-------------------------------------------------------------------------

}