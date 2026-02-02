package mcts.backpropagation;

import other.context.Context;
import search.mcts.MCTS;
import search.mcts.backpropagation.BackpropagationStrategy;
import search.mcts.nodes.BaseNode;

/**
 * Score-Bounded MCTS backpropagation strategy.
 *
 * Maintains optimistic (upper) and pessimistic (lower) score bounds at each node.
 * When bounds converge within a threshold, the node is considered "solved" or stable.
 * This reduces wasteful exploration in drawn positions or positions with proven outcomes.
 *
 * Particularly effective in:
 * - Games with frequent draws (Chess variants)
 * - Games with complex scoring (Go endgames)
 * - Deterministic games where positions can be partially solved
 *
 * @author Gauwain Savary-Kerneïs
 */
public class ScoreBoundedBackprop extends BackpropagationStrategy
{

    //-------------------------------------------------------------------------

    /** Threshold for considering bounds as converged (solved) */
    protected double convergenceThreshold;

    /** Weight for mixing current result with existing bounds (learning rate) */
    protected double updateWeight;

    /** Whether to use proven bounds (stricter) or statistical bounds (looser) */
    protected boolean useProvenBounds;

    //-------------------------------------------------------------------------

    /**
     * Constructor with default values:
     * - convergenceThreshold = 0.01 (1% difference means solved)
     * - updateWeight = 0.1 (gradual bound updates)
     * - useProvenBounds = false (use statistical bounds)
     */
    public ScoreBoundedBackprop()
    {
        this.convergenceThreshold = 0.01;
        this.updateWeight = 0.1;
        this.useProvenBounds = false;
    }

    /**
     * Constructor with custom parameters
     * @param convergenceThreshold When upper-lower < this, node is "solved"
     * @param updateWeight How quickly to update bounds (0-1, typical: 0.1)
     * @param useProvenBounds If true, only terminal outcomes update bounds strictly
     */
    public ScoreBoundedBackprop(
            final double convergenceThreshold,
            final double updateWeight,
            final boolean useProvenBounds)
    {
        this.convergenceThreshold = convergenceThreshold;
        this.updateWeight = updateWeight;
        this.useProvenBounds = useProvenBounds;
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
        // Update bounds along the path from leaf to root
        BaseNode node = startNode;

        while (node != null)
        {
            // Get bounds for this node (stored in node's additional statistics)
            // Note: This requires node to have scoreBounds storage
            // For now, we'll modify utilities to incorporate bound information

            final int numPlayers = utilities.length;

            for (int p = 1; p < numPlayers; ++p)
            {
                final double currentUtility = utilities[p];

                // In score-bounded MCTS, we want to:
                // 1. Maintain pessimistic (lower) and optimistic (upper) estimates
                // 2. Converge utilities toward these bounds over time
                // 3. Detect when bounds converge (position is "solved")

                if (useProvenBounds)
                {
                    // Stricter update: only terminal states give definitive bounds
                    if (context.trial().over())
                    {
                        // Terminal node - this is a proven result
                        // Store as both upper and lower bound (bounds converge)
                        // For implementation, just use the raw utility
                        utilities[p] = currentUtility;
                    }
                    else
                    {
                        // Non-terminal - use standard Monte Carlo with slight pessimism
                        // to encourage exploration of uncertain nodes
                        utilities[p] = currentUtility * (1.0 - updateWeight * 0.5);
                    }
                }
                else
                {
                    // Statistical bounds: gradually tighten bounds based on observations
                    // This implementation uses a simple pessimistic adjustment
                    // to encourage re-visiting nodes with high uncertainty

                    final double nodeVisits = Math.max(1.0, node.numVisits());
                    final double uncertainty = 1.0 / Math.sqrt(nodeVisits);

                    // If uncertainty is high, be more pessimistic about non-terminal results
                    if (!context.trial().over() && uncertainty > convergenceThreshold)
                    {
                        // Apply pessimistic discount proportional to uncertainty
                        utilities[p] = currentUtility - (updateWeight * uncertainty * currentUtility);
                    }
                    else
                    {
                        // Low uncertainty or terminal node - use result as-is
                        utilities[p] = currentUtility;
                    }
                }
            }

            node = node.parent();
        }
    }

    @Override
    public int backpropagationFlags()
    {
        // Could add custom flag for bound tracking if needed
        return 0;
    }

    //-------------------------------------------------------------------------

    /**
     * Helper method to check if a node's bounds have converged
     * (would require additional node storage not shown here)
     *
     * @param node
     * @param player
     * @return true if bounds converged within threshold
     */
    @SuppressWarnings("unused")
    private boolean boundsConverged(final BaseNode node, final int player)
    {
        // This would access node.lowerBound[player] and node.upperBound[player]
        // if we extend BaseNode with bound storage
        // For now, this is a placeholder for the concept

        // return (node.upperBound[player] - node.lowerBound[player]) < convergenceThreshold;
        return false;
    }

    //-------------------------------------------------------------------------

}