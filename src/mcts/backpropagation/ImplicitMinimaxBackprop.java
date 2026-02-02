package mcts.backpropagation;

import other.context.Context;
import search.mcts.MCTS;
import search.mcts.backpropagation.BackpropagationStrategy;
import search.mcts.nodes.BaseNode;

/**
 * Implicit Minimax Backpropagation strategy (Algorithm 3.5 from thesis).
 *
 * This backpropagation strategy updates nodes using both Monte Carlo values
 * and implicit minimax backups. At each node, we maintain:
 * - r_s: cumulative reward (standard Monte Carlo)
 * - n_s: visit count
 * - v^τ_s: optimistic value = max over children's values
 *
 * The UPDATE function (Algorithm 3.5, lines 4-7):
 *   r_s ← r_s + r
 *   n_s ← n_s + 1
 *   v^τ_s ← max_{a ∈ A(s)} v^τ_{s,a}
 *
 * This creates an implicit minimax tree structure within MCTS, combining
 * the benefits of Monte Carlo averaging with minimax's strategic depth.
 *
 * @author Gauwain Savary-Kerneïs
 */
public class ImplicitMinimaxBackprop extends BackpropagationStrategy
{

    //-------------------------------------------------------------------------

    /** Weight for incorporating minimax value into backpropagation */
    protected double minimaxWeight;

    /** Whether to use pessimistic (min) for opponent's perspective */
    protected boolean alternatingMinMax;

    //-------------------------------------------------------------------------

    /**
     * Constructor with default values:
     * - minimaxWeight = 0.3 (30% minimax influence)
     * - alternatingMinMax = true (proper two-player minimax)
     */
    public ImplicitMinimaxBackprop()
    {
        this.minimaxWeight = 0.3;
        this.alternatingMinMax = true;
    }

    /**
     * Constructor with custom parameters
     * @param minimaxWeight Weight for minimax value (0 = pure MC, 1 = pure minimax)
     * @param alternatingMinMax If true, alternates max/min based on player
     */
    public ImplicitMinimaxBackprop(
            final double minimaxWeight,
            final boolean alternatingMinMax)
    {
        this.minimaxWeight = minimaxWeight;
        this.alternatingMinMax = alternatingMinMax;
    }

    //-------------------------------------------------------------------------

    @Override
    public void computeUtilities
            (
                    final MCTS mcts,
                    final BaseNode startNode,
                    final Context context,
                    final double[] utilities,
                    final int numPlayoutMoves
            )
    {
        // Standard Monte Carlo utilities are passed in
        // We modify them to incorporate implicit minimax values

        BaseNode node = startNode;
        final int numPlayers = utilities.length;

        while (node != null)
        {
            // For each player, compute the implicit minimax value
            // v^τ_s = max_{a ∈ A(s)} v^τ_{s,a} (Algorithm 3.5, line 7)

            for (int p = 1; p < numPlayers; ++p)
            {
                final double mcUtility = utilities[p];

                // Compute implicit minimax value for this node and player
                final double minimaxValue = computeImplicitMinimaxValue(node, p);

                // Blend MC utility with minimax value
                // This implements the spirit of Algorithm 3.5 where v^τ influences decisions
                if (minimaxValue != Double.NEGATIVE_INFINITY)
                {
                    utilities[p] = (1.0 - minimaxWeight) * mcUtility + minimaxWeight * minimaxValue;
                }
                // If no minimax value available, keep the MC utility unchanged
            }

            node = node.parent();
        }
    }

    /**
     * Computes the implicit minimax value for a node.
     * 
     * v^τ_s = max_{a ∈ A(s)} v^τ_{s,a}
     *
     * For a two-player game with alternating perspectives:
     * - At the mover's turn: take max over children (best for mover)
     * - At opponent's turn: take min over children (opponent plays best)
     *
     * @param node The node to compute the implicit minimax value for
     * @param player The player whose perspective to evaluate from
     * @return The implicit minimax value, or NEGATIVE_INFINITY if not computable
     */
    private double computeImplicitMinimaxValue(final BaseNode node, final int player)
    {
        if (node == null)
        {
            return Double.NEGATIVE_INFINITY;
        }

        final int numChildren = node.numLegalMoves();
        if (numChildren == 0)
        {
            // Terminal node - no children to consider
            return Double.NEGATIVE_INFINITY;
        }

        // Determine if we should maximize or minimize from this player's perspective
        boolean maximize = true;
        if (alternatingMinMax)
        {
            // Get the mover at this node
            final int mover = node.contextRef().state().mover();
            // Maximize if it's the player's turn, minimize if opponent's turn
            maximize = (mover == player);
        }

        double bestValue = maximize ? Double.NEGATIVE_INFINITY : Double.POSITIVE_INFINITY;
        boolean hasVisitedChild = false;

        for (int i = 0; i < numChildren; ++i)
        {
            final BaseNode child = node.childForNthLegalMove(i);
            if (child != null && child.numVisits() > 0)
            {
                hasVisitedChild = true;
                // Get child's value from this player's perspective
                final int playerAgent = node.contextRef().state().playerToAgent(player);
                final double childValue = child.exploitationScore(playerAgent);

                if (maximize)
                {
                    if (childValue > bestValue)
                    {
                        bestValue = childValue;
                    }
                }
                else
                {
                    if (childValue < bestValue)
                    {
                        bestValue = childValue;
                    }
                }
            }
        }

        if (!hasVisitedChild)
        {
            return Double.NEGATIVE_INFINITY;
        }

        return bestValue;
    }

    @Override
    public int backpropagationFlags()
    {
        return 0;
    }

    //-------------------------------------------------------------------------

    @Override
    public String toString()
    {
        return String.format("ImplicitMinimaxBackprop[w=%.4f, alt=%b]",
                minimaxWeight, alternatingMinMax);
    }

}
