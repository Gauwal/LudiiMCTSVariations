package mcts.selection;

import java.util.concurrent.ThreadLocalRandom;

import other.state.State;
import search.mcts.MCTS;
import search.mcts.nodes.BaseNode;
import search.mcts.selection.SelectionStrategy;

/**
 * Implicit Minimax Selection strategy (Algorithm 3.5 from thesis).
 *
 * This selection strategy combines UCB1 with implicit minimax backups.
 * At each node, we maintain an optimistic value estimate that is the maximum
 * of all children's values, creating an implicit minimax tree within MCTS.
 *
 * The selection uses: Q^IM(s,a) + C * sqrt(ln(n_s) / n(s,a))
 * where Q^IM incorporates the implicit minimax value.
 *
 * Key features:
 * - Maintains v^τ (optimistic value) at each node as max over children
 * - Initializes new nodes with heuristic value v_0(s')
 * - Combines Monte Carlo averaging with minimax backup structure
 *
 * @author Gauwain Savary-Kerneïs
 */
public class ImplicitMinimaxSelection implements SelectionStrategy
{

    //-------------------------------------------------------------------------

    /** Exploration constant C */
    protected double explorationConstant;

    /** Weight for mixing Monte Carlo value with implicit minimax value (0-1) */
    protected double minimaxWeight;

    //-------------------------------------------------------------------------

    /**
     * Constructor with default values:
     * - exploration constant = sqrt(2)
     * - minimax weight = 0.5 (equal mix of MC and minimax)
     */
    public ImplicitMinimaxSelection()
    {
        this.explorationConstant = Math.sqrt(2.0);
        this.minimaxWeight = 0.5;
    }

    /**
     * Constructor with custom parameters
     * @param explorationConstant UCB1 exploration parameter C
     * @param minimaxWeight Weight for implicit minimax value (0 = pure MC, 1 = pure minimax)
     */
    public ImplicitMinimaxSelection(
            final double explorationConstant,
            final double minimaxWeight)
    {
        this.explorationConstant = explorationConstant;
        this.minimaxWeight = minimaxWeight;
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

        final double parentLog = Math.log(Math.max(1, current.sumLegalChildVisits()));

        // Compute the implicit minimax value: max over children's values
        // This is v^τ_s = max_{a ∈ A(s)} v^τ_{s,a} from Algorithm 3.5
        double implicitMinimaxValue = Double.NEGATIVE_INFINITY;
        for (int i = 0; i < numChildren; ++i)
        {
            final BaseNode child = current.childForNthLegalMove(i);
            if (child != null && child.numVisits() > 0)
            {
                final double childValue = child.exploitationScore(moverAgent);
                if (childValue > implicitMinimaxValue)
                {
                    implicitMinimaxValue = childValue;
                }
            }
        }
        // If no children visited yet, use the unvisited estimate
        if (implicitMinimaxValue == Double.NEGATIVE_INFINITY)
        {
            implicitMinimaxValue = unvisitedValueEstimate;
        }

        // Select using Q^IM + exploration term
        for (int i = 0; i < numChildren; ++i)
        {
            final BaseNode child = current.childForNthLegalMove(i);
            final double exploit;
            final double explore;

            if (child == null)
            {
                // Unvisited child - use initial value estimate v_0(s')
                // This corresponds to line 13 in Algorithm 3.5: v_{s'} ← v_0(s')
                exploit = unvisitedValueEstimate;
                explore = Math.sqrt(parentLog);
            }
            else
            {
                // Visited child - compute Q^IM as mix of MC value and implicit minimax
                // Q^IM(s,a) combines the Monte Carlo estimate with the minimax structure
                final double mcValue = child.exploitationScore(moverAgent);
                
                // Get the child's implicit minimax value (max of its children)
                double childMinimaxValue = getImplicitMinimaxValue(child, moverAgent);
                
                // Q^IM = (1 - w) * Q_MC + w * v^τ
                exploit = (1.0 - minimaxWeight) * mcValue + minimaxWeight * childMinimaxValue;
                
                final int childVisits = Math.max(child.numVisits() + child.numVirtualVisits(), 1);
                explore = Math.sqrt(parentLog / childVisits);
            }

            // UCB1-like formula: Q^IM(s,a) + C * sqrt(ln(n_s) / n(s,a))
            final double selectionValue = exploit + explorationConstant * explore;

            if (selectionValue > bestValue)
            {
                bestValue = selectionValue;
                bestIdx = i;
                numBestFound = 1;
            }
            else if
            (
                    selectionValue == bestValue
                            &&
                            ThreadLocalRandom.current().nextInt() % ++numBestFound == 0
            )
            {
                bestIdx = i;
            }
        }

        return bestIdx;
    }

    /**
     * Computes the implicit minimax value for a node.
     * This is v^τ_s = max_{a ∈ A(s)} v^τ_{s,a} from Algorithm 3.5, line 7 and 14.
     *
     * For a maximizing player, this is the maximum value among children.
     * For a minimizing player, this would be the minimum (but from the mover's
     * perspective, we always want the max of their values).
     *
     * @param node The node to compute the implicit minimax value for
     * @param moverAgent The agent index of the mover
     * @return The implicit minimax value
     */
    private double getImplicitMinimaxValue(final BaseNode node, final int moverAgent)
    {
        if (node == null || node.numVisits() == 0)
        {
            return 0.5; // Neutral estimate for unvisited nodes
        }

        final int numChildren = node.numLegalMoves();
        if (numChildren == 0)
        {
            // Terminal node - return its actual value
            return node.exploitationScore(moverAgent);
        }

        double maxChildValue = Double.NEGATIVE_INFINITY;
        boolean hasVisitedChild = false;

        for (int i = 0; i < numChildren; ++i)
        {
            final BaseNode child = node.childForNthLegalMove(i);
            if (child != null && child.numVisits() > 0)
            {
                hasVisitedChild = true;
                final double childValue = child.exploitationScore(moverAgent);
                if (childValue > maxChildValue)
                {
                    maxChildValue = childValue;
                }
            }
        }

        if (!hasVisitedChild)
        {
            // No visited children - use the node's own value
            return node.exploitationScore(moverAgent);
        }

        return maxChildValue;
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
        for (int i = 1; i < inputs.length; i++)
        {
            final String input = inputs[i];

            if (input.toLowerCase().startsWith("explorationconstant="))
            {
                explorationConstant = Double.parseDouble(
                        input.substring("explorationconstant=".length()));
            }
            else if (input.toLowerCase().startsWith("minimaxweight="))
            {
                minimaxWeight = Double.parseDouble(
                        input.substring("minimaxweight=".length()));
            }
        }
    }

    //-------------------------------------------------------------------------

    @Override
    public String toString()
    {
        return String.format("ImplicitMinimaxSelection[C=%.4f, w=%.4f]",
                explorationConstant, minimaxWeight);
    }

}
