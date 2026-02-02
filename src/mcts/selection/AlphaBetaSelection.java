package mcts.selection;

import java.util.concurrent.ThreadLocalRandom;

import other.state.State;
import search.mcts.MCTS;
import search.mcts.nodes.BaseNode;
import search.mcts.selection.SelectionStrategy;

/**
 * Alpha-Beta MCTS Selection strategy (Algorithms 3.6 and 3.7 from thesis).
 *
 * This selection strategy adapts traditional α-β pruning to the non-deterministic
 * context of MCTS. It uses ancestor-based bounds to narrow the search space
 * while maintaining the UCT exploration-exploitation balance.
 *
 * Key concepts:
 * - α (alpha): Lower bound - best value the maximizing player can guarantee
 * - β (beta): Upper bound - best value the minimizing player can guarantee
 * - CB(s,a): Confidence bound = C_αβ * sqrt(ln(n_s) / n(s,a))
 *
 * For the maximizing player:
 *   - Updates α when Q(s,a) - CB(s,a) > α
 *   - Uses UCT_αβ(s, α, β, α_, β+)
 *
 * For the minimizing player:
 *   - Updates β when Q(s,a) + CB(s,a) < β
 *   - Uses UCT_αβ(s, 1-β, 1-α, -β+, -α_)
 *
 * @author Gauwain Savary-Kerneïs
 */
public class AlphaBetaSelection implements SelectionStrategy
{

    //-------------------------------------------------------------------------

    /** Exploration constant for UCB1 component */
    protected double explorationConstant;

    /** Confidence bound constant C_αβ for α-β bounds */
    protected double alphaBetaConstant;

    /** Current alpha bound (tracked across selection path) */
    protected ThreadLocal<Double> currentAlpha;

    /** Current beta bound (tracked across selection path) */
    protected ThreadLocal<Double> currentBeta;

    /** Alpha offset (α_) for UCT_αβ */
    protected ThreadLocal<Double> alphaOffset;

    /** Beta offset (β+) for UCT_αβ */
    protected ThreadLocal<Double> betaOffset;

    //-------------------------------------------------------------------------

    /**
     * Constructor with default values:
     * - exploration constant = sqrt(2)
     * - alpha-beta constant = sqrt(2)
     */
    public AlphaBetaSelection()
    {
        this.explorationConstant = Math.sqrt(2.0);
        this.alphaBetaConstant = Math.sqrt(2.0);
        initThreadLocals();
    }

    /**
     * Constructor with custom parameters
     * @param explorationConstant UCB1 exploration parameter
     * @param alphaBetaConstant Confidence bound constant C_αβ
     */
    public AlphaBetaSelection(
            final double explorationConstant,
            final double alphaBetaConstant)
    {
        this.explorationConstant = explorationConstant;
        this.alphaBetaConstant = alphaBetaConstant;
        initThreadLocals();
    }

    private void initThreadLocals()
    {
        currentAlpha = ThreadLocal.withInitial(() -> Double.NEGATIVE_INFINITY);
        currentBeta = ThreadLocal.withInitial(() -> Double.POSITIVE_INFINITY);
        alphaOffset = ThreadLocal.withInitial(() -> 0.0);
        betaOffset = ThreadLocal.withInitial(() -> 0.0);
    }

    //-------------------------------------------------------------------------

    /**
     * Reset bounds at the start of a new simulation.
     * Called when starting from the root (Algorithm 3.7, line 6).
     */
    public void resetBounds()
    {
        currentAlpha.set(Double.NEGATIVE_INFINITY);
        currentBeta.set(Double.POSITIVE_INFINITY);
        alphaOffset.set(0.0);
        betaOffset.set(0.0);
    }

    /**
     * Computes the confidence bound CB(s,a) = C_αβ * sqrt(ln(n_s) / n(s,a))
     * as defined in the algorithm.
     */
    private double confidenceBound(final double parentLogVisits, final int childVisits)
    {
        if (childVisits <= 0)
            return Double.POSITIVE_INFINITY;
        return alphaBetaConstant * Math.sqrt(parentLogVisits / childVisits);
    }

    /**
     * Updates the α-β bounds based on current node (BOUNDS function from Algorithm 3.7).
     *
     * For first player (maximizer):
     *   if α < Q(s) - CB(s) then
     *     α = Q(s) - CB(s)
     *     α_ = -CB(s)
     *
     * For second player (minimizer):
     *   if β > Q(s) + CB(s) then
     *     β = Q(s) + CB(s)
     *     β+ = CB(s)
     */
    private void updateBounds(
            final BaseNode node,
            final int moverAgent,
            final boolean isMaximizingPlayer,
            final double parentLogVisits)
    {
        if (node == null || node.numVisits() == 0)
            return;

        final double qValue = node.exploitationScore(moverAgent);
        final int visits = node.numVisits() + node.numVirtualVisits();
        final double cb = confidenceBound(parentLogVisits, visits);

        if (isMaximizingPlayer)
        {
            // Algorithm 3.7, lines 29-31: Update alpha for maximizing player
            final double lowerBound = qValue - cb;
            if (currentAlpha.get() < lowerBound)
            {
                currentAlpha.set(lowerBound);
                alphaOffset.set(-cb);
            }
        }
        else
        {
            // Algorithm 3.7, lines 33-35: Update beta for minimizing player
            final double upperBound = qValue + cb;
            if (currentBeta.get() > upperBound)
            {
                currentBeta.set(upperBound);
                betaOffset.set(cb);
            }
        }
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
        final int mover = state.mover();
        final double unvisitedValueEstimate =
                current.valueEstimateUnvisitedChildren(moverAgent);

        // Determine if current player is maximizing (player 1) or minimizing (player 2)
        // In two-player zero-sum games, player 1 maximizes, player 2 minimizes
        final boolean isMaximizingPlayer = (mover == 1);

        final int parentVisits = Math.max(1, current.sumLegalChildVisits());
        final double parentLog = Math.log(parentVisits);

        // Get current bounds
        final double alpha = currentAlpha.get();
        final double beta = currentBeta.get();
        final double alphaOff = alphaOffset.get();
        final double betaOff = betaOffset.get();

        // Select using UCT_αβ formula
        for (int i = 0; i < numChildren; ++i)
        {
            final BaseNode child = current.childForNthLegalMove(i);
            final double selectionValue;

            if (child == null)
            {
                // Unvisited child - high priority for exploration
                selectionValue = unvisitedValueEstimate + explorationConstant * Math.sqrt(parentLog);
            }
            else
            {
                final double qValue = child.exploitationScore(moverAgent);
                final int childVisits = Math.max(child.numVisits() + child.numVirtualVisits(), 1);
                final double cb = confidenceBound(parentLog, childVisits);

                // Apply UCT_αβ selection based on player type
                // Algorithm 3.6 and 3.7 lines 13-15
                if (alpha != Double.NEGATIVE_INFINITY && beta != Double.POSITIVE_INFINITY)
                {
                    // Both bounds are set - use bounded selection
                    if (isMaximizingPlayer)
                    {
                        // UCT_αβ(s, α, β, α_, β+) for maximizing player
                        selectionValue = computeUCTAlphaBeta(
                                qValue, childVisits, parentLog,
                                alpha, beta, alphaOff, betaOff);
                    }
                    else
                    {
                        // UCT_αβ(s, 1-β, 1-α, -β+, -α_) for minimizing player
                        // Transform bounds for minimizing player's perspective
                        selectionValue = computeUCTAlphaBeta(
                                1.0 - qValue, childVisits, parentLog,
                                1.0 - beta, 1.0 - alpha, -betaOff, -alphaOff);
                    }
                }
                else
                {
                    // Standard UCT when bounds not yet established
                    final double exploit = qValue;
                    final double explore = Math.sqrt(parentLog / childVisits);
                    selectionValue = exploit + explorationConstant * explore;
                }
            }

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

        // Update bounds for the selected child (for next level of selection)
        final BaseNode selectedChild = current.childForNthLegalMove(bestIdx);
        if (selectedChild != null)
        {
            updateBounds(selectedChild, moverAgent, isMaximizingPlayer, parentLog);
        }

        return bestIdx;
    }

    /**
     * Computes the UCT_αβ value incorporating alpha-beta bounds.
     *
     * This combines the standard UCT formula with bound information:
     * - Uses the Q-value as base exploitation
     * - Adjusts exploration based on how far the value is from bounds
     * - Reduces exploration for actions that clearly exceed or fall short of bounds
     *
     * @param qValue The exploitation value Q(s,a)
     * @param childVisits Number of visits to the child
     * @param parentLogVisits Log of parent's visit count
     * @param alpha Current alpha bound
     * @param beta Current beta bound
     * @param alphaOffset Offset α_ from bound computation
     * @param betaOffset Offset β+ from bound computation
     * @return The UCT_αβ selection value
     */
    private double computeUCTAlphaBeta(
            final double qValue,
            final int childVisits,
            final double parentLogVisits,
            final double alpha,
            final double beta,
            final double alphaOffset,
            final double betaOffset)
    {
        // Base UCT components
        final double exploitation = qValue;
        final double exploration = explorationConstant * Math.sqrt(parentLogVisits / childVisits);

        // Compute confidence bound for this child
        final double cb = confidenceBound(parentLogVisits, childVisits);

        // UCT_αβ adjustment:
        // If the lower bound (Q - CB) is already above alpha, this node is promising
        // If the upper bound (Q + CB) is below beta, this node might be prunable
        final double lowerBound = qValue - cb;
        final double upperBound = qValue + cb;

        double boundAdjustment = 0.0;

        // Bonus for exceeding alpha (good for maximizer)
        if (lowerBound > alpha && alpha != Double.NEGATIVE_INFINITY)
        {
            boundAdjustment += 0.1 * (lowerBound - alpha);
        }

        // Penalty for potentially being below beta (could be pruned by minimizer)
        if (upperBound < beta && beta != Double.POSITIVE_INFINITY)
        {
            boundAdjustment -= 0.1 * (beta - upperBound);
        }

        return exploitation + exploration + boundAdjustment;
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
            else if (input.toLowerCase().startsWith("alphabetaconstant="))
            {
                alphaBetaConstant = Double.parseDouble(
                        input.substring("alphabetaconstant=".length()));
            }
        }
    }

    //-------------------------------------------------------------------------

    @Override
    public String toString()
    {
        return String.format("AlphaBetaSelection[C=%.4f, C_αβ=%.4f]",
                explorationConstant, alphaBetaConstant);
    }

}
