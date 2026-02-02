package experiments;

import game.Game;
import mcts.MCTSVariations;
import other.AI;
import other.GameLoader;
import other.RankUtils;
import other.context.Context;
import other.move.Move;
import other.trial.Trial;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Quick harness that pits every policy combination against a baseline Ludii MCTS setup.
 */
public final class AITest
{
    private static final String GAME_NAME = "Amazons.lud";
    private static final double MOVE_TIME_SECONDS = 0.1;
    private static final int GAMES_PER_MATCHUP = 2; // must be even to alternate seats
    private static final Path RESULTS_PATH = Paths.get("aitest_results.csv");

    // selection policies (many variants included to match normalize(...) checks in MCTSVariations)
    private static final String[] SELECTION_POLICIES = {
            "UCB1",
            "UCB1 tuned",
            "UCB1 GRAVE",
            "Progressive Bias",
            "Progressive History",
            "McBRAVE",
            "McGRAVE",
            "AG0",              
            "Noisy AG0",
            "ExIt",
            "Progressive Widening",
            "Implicit Minimax",
            "Alpha-Beta"
    };

    // playout/simulation policies
    private static final String[] SIMULATION_POLICIES = {
            "Random",
            "MAST",
            "NST",
            "Heuristic",
            "Heuristic Samping",
            "HS Playout",
            "PlayoutHS",
            "LGR"
    };

    // backprop policies
    private static final String[] BACKPROP_POLICIES = {
            "MonteCarlo",
            "Heuristic",
            "AlphaGo",
            "Qualitative",
            "Score Bounded",
            "Implicit Minimax"
    };

    // final-move selection policies
    private static final String[] FINAL_MOVE_POLICIES = {
            "Robust",
            "MaxAvgScore",
            "Proportional Exp"
    };

    // baseline now includes a final-move strategy
    private static final Config BASELINE = new Config("UCB1", "Random", "MonteCarlo", "Robust");

    public static void main(final String[] args)
    {
        final Game game = GameLoader.loadGameFromName(GAME_NAME);
        if (game == null)
        {
            System.err.println("Unable to load game: " + GAME_NAME);
            return;
        }

        if (game.players().count() != 2)
        {
            System.err.println("This harness assumes a two-player game; found " + game.players().count());
            return;
        }

        final Map<String, SavedResult> storedResults = loadStoredResults();
        final List<Config> configs = enumerateConfigs();
        System.out.printf("Baseline: %s%n", BASELINE.label());

        for (final Config challenger : configs)
        {
            if (challenger.equals(BASELINE))
                continue;

            final String label = challenger.label();
            final SavedResult previous = storedResults.get(label);
            if (previous != null && previous.isComplete(GAMES_PER_MATCHUP))
            {
                System.out.printf("Skipping %s (already completed)%n", label);
                continue;
            }

            final MatchStats stats = runMatchup(game, challenger, BASELINE);
            System.out.printf(
                    "%s vs %s -> wins: %d, losses: %d, draws: %d, failed: %d, completed: %d/%d, avgLen: %.1f%n",
                    label,
                    BASELINE.label(),
                    stats.challengerWins,
                    stats.baselineWins,
                    stats.draws,
                    stats.failures,
                    stats.completedGames,
                    stats.attemptedGames,
                    stats.averageMoves()
            );

            storedResults.put(label, SavedResult.fromStats(challenger, stats));
        }

        saveResults(storedResults);
    }

    private static List<Config> enumerateConfigs()
    {
        final List<Config> configs = new ArrayList<>();
        String baseSelect = "UCB1";
        String baseSim ="Random";
        String baseBack = "MCback";
        String baseFinal = "Robust";
        for (final String selection : SELECTION_POLICIES)
        {
            configs.add(new Config(selection, baseSim, baseBack, baseFinal));
        }
        for (final String simulation : SIMULATION_POLICIES)
        {
            configs.add(new Config(baseSelect, simulation, baseBack, baseFinal));
        }
        for (final String backprop : BACKPROP_POLICIES)
        {
            configs.add(new Config(baseSelect, baseSim, backprop, baseFinal));
        }
        for (final String finalMove : FINAL_MOVE_POLICIES)
        {
            configs.add(new Config(baseSelect, baseSim, baseBack, finalMove));
        }
        return configs;
    }

    private static Map<String, SavedResult> loadStoredResults()
    {
        final Map<String, SavedResult> results = new HashMap<>();

        if (!Files.exists(RESULTS_PATH))
            return results;

        try (BufferedReader reader = Files.newBufferedReader(RESULTS_PATH, StandardCharsets.UTF_8))
        {
            String line;
            while ((line = reader.readLine()) != null)
            {
                line = line.trim();
                if (line.isEmpty() || line.startsWith("#"))
                    continue;
                if (line.toLowerCase(Locale.ROOT).startsWith("selection"))
                    continue;

                final String[] parts = line.split(",", -1);
                // now expecting 11 columns: selection,simulation,backprop,finalMove,wins,losses,draws,failures,completedGames,attemptedGames,averageMoves
                if (parts.length < 11)
                    continue;

                try
                {
                    final SavedResult parsed = SavedResult.parse(parts);
                    results.put(parsed.label(), parsed);
                }
                catch (final NumberFormatException e)
                {
                    System.err.println("Ignoring malformed result row: " + line);
                }
            }
        }
        catch (final IOException e)
        {
            System.err.println("Unable to read previous AI test results: " + e.getMessage());
        }

        return results;
    }

    private static void saveResults(final Map<String, SavedResult> results)
    {
        if (results.isEmpty())
        {
            try
            {
                Files.deleteIfExists(RESULTS_PATH);
            }
            catch (final IOException ignored)
            {
                // Nothing we can do here.
            }
            return;
        }

        final List<SavedResult> sorted = new ArrayList<>(results.values());
        sorted.sort((a, b) -> a.label().compareToIgnoreCase(b.label()));

        try (BufferedWriter writer = Files.newBufferedWriter(RESULTS_PATH, StandardCharsets.UTF_8))
        {
            writer.write("selection,simulation,backprop,finalMove,wins,losses,draws,failures,completedGames,attemptedGames,averageMoves");
            writer.newLine();

            for (final SavedResult result : sorted)
            {
                writer.write(result.toCsv());
                writer.newLine();
            }
        }
        catch (final IOException e)
        {
            System.err.println("Unable to store AI test results: " + e.getMessage());
        }
    }

    private static final class SavedResult
    {
        final String selection;
        final String simulation;
        final String backprop;
        final String finalMove;
        final int wins;
        final int losses;
        final int draws;
        final int failures;
        final int completedGames;
        final int attemptedGames;
        final double averageMoves;

        SavedResult(
                final String selection,
                final String simulation,
                final String backprop,
                final String finalMove,
                final int wins,
                final int losses,
                final int draws,
                final int failures,
                final int completedGames,
                final int attemptedGames,
                final double averageMoves
        )
        {
            this.selection = selection;
            this.simulation = simulation;
            this.backprop = backprop;
            this.finalMove = finalMove;
            this.wins = wins;
            this.losses = losses;
            this.draws = draws;
            this.failures = failures;
            this.completedGames = completedGames;
            this.attemptedGames = attemptedGames;
            this.averageMoves = averageMoves;
        }

        static SavedResult parse(final String[] parts)
        {
            // parts: 0=selection,1=simulation,2=backprop,3=finalMove,4=wins,5=losses,6=draws,7=failures,8=completedGames,9=attemptedGames,10=averageMoves
            return new SavedResult(
                    parts[0],
                    parts[1],
                    parts[2],
                    parts[3],
                    Integer.parseInt(parts[4]),
                    Integer.parseInt(parts[5]),
                    Integer.parseInt(parts[6]),
                    Integer.parseInt(parts[7]),
                    Integer.parseInt(parts[8]),
                    Integer.parseInt(parts[9]),
                    Double.parseDouble(parts[10])
            );
        }

        static SavedResult fromStats(final Config config, final MatchStats stats)
        {
            return new SavedResult(
                    config.selection,
                    config.simulation,
                    config.backprop,
                    config.finalMove,
                    stats.challengerWins,
                    stats.baselineWins,
                    stats.draws,
                    stats.failures,
                    stats.completedGames,
                    stats.attemptedGames,
                    stats.averageMoves()
            );
        }

        String label()
        {
            return String.format("%s | %s | %s | %s", selection, simulation, backprop, finalMove);
        }

        boolean isComplete(final int requiredGames)
        {
            return failures == 0 && completedGames >= requiredGames;
        }

        String toCsv()
        {
            return String.format(
                    Locale.ROOT,
                    "%s,%s,%s,%s,%d,%d,%d,%d,%d,%d,%.4f",
                    selection,
                    simulation,
                    backprop,
                    finalMove,
                    wins,
                    losses,
                    draws,
                    failures,
                    completedGames,
                    attemptedGames,
                    averageMoves
            );
        }
    }

    private static MatchStats runMatchup(final Game game, final Config challenger, final Config baseline)
    {
        final MatchStats stats = new MatchStats();

        for (int gameIndex = 0; gameIndex < GAMES_PER_MATCHUP; ++gameIndex)
        {
            stats.attemptedGames++;
            final boolean challengerFirst = (gameIndex % 2 == 0);
            final Config p1Config = challengerFirst ? challenger : baseline;
            final Config p2Config = challengerFirst ? baseline : challenger;

            final GameOutcome outcome = playGame(game, p1Config, p2Config);
            if (!outcome.success)
            {
                stats.failures++;
                System.err.printf("  Skipping game due to %s%n", outcome.describeError());
                continue;
            }

            stats.completedGames++;
            stats.totalMoves += outcome.numMoves;

            final double utilityP1 = outcome.utilities[1];
            final double utilityP2 = outcome.utilities[2];

            final int result;
            if (utilityP1 > utilityP2)
                result = 1;
            else if (utilityP2 > utilityP1)
                result = -1;
            else
                result = 0;

            if (result == 0)
            {
                stats.draws++;
            }
            else if (result > 0)
            {
                if (challengerFirst)
                    stats.challengerWins++;
                else
                    stats.baselineWins++;
            }
            else
            {
                if (challengerFirst)
                    stats.baselineWins++;
                else
                    stats.challengerWins++;
            }
        }

        return stats;
    }

    private static GameOutcome playGame(final Game game, final Config player1, final Config player2)
    {
        final Trial trial = new Trial(game);
        final Context context = new Context(game, trial);
        game.start(context);

        final AI[] agents = new AI[3]; // 1-indexed for two players
        agents[1] = player1.instantiate();
        agents[2] = player2.instantiate();

        for (int p = 1; p <= 2; ++p)
        {
            agents[p].initAI(game, p);
        }

        Exception failure = null;

        while (!context.trial().over() && failure == null)
        {
            final int mover = context.state().mover();
            final AI agent = agents[mover];
            final Move move;
            try
            {
                move = agent.selectAction(
                        game,
                        new Context(context),
                        MOVE_TIME_SECONDS,
                        -1,
                        -1
                );
            }
            catch (final RuntimeException ex)
            {
                failure = ex;
                break;
            }

            game.apply(context, move);
        }

        for (int p = 1; p <= 2; ++p)
        {
            agents[p].closeAI();
        }

        if (failure != null)
            return GameOutcome.failure(failure);

        return GameOutcome.success(RankUtils.agentUtilities(context), context.trial().numMoves());
    }

    private static final class Config
    {
        final String selection;
        final String simulation;
        final String backprop;
        final String finalMove;

        Config(final String selection, final String simulation, final String backprop, final String finalMove)
        {
            this.selection = selection;
            this.simulation = simulation;
            this.backprop = backprop;
            this.finalMove = finalMove;
        }

        AI instantiate()
        {
            return new MCTSVariations(selection, simulation, backprop, finalMove);
        }

        String label()
        {
            return String.format("%s | %s | %s | %s", selection, simulation, backprop, finalMove);
        }

        @Override
        public boolean equals(final Object obj)
        {
            if (this == obj)
                return true;
            if (!(obj instanceof Config))
                return false;
            final Config other = (Config) obj;
            return selection.equals(other.selection)
                    && simulation.equals(other.simulation)
                    && backprop.equals(other.backprop)
                    && finalMove.equals(other.finalMove);
        }

        @Override
        public int hashCode()
        {
            int result = selection.hashCode();
            result = 31 * result + simulation.hashCode();
            result = 31 * result + backprop.hashCode();
            result = 31 * result + finalMove.hashCode();
            return result;
        }
    }

    private static final class MatchStats
    {
        int challengerWins;
        int baselineWins;
        int draws;
        int totalMoves;
        int completedGames;
        int failures;
        int attemptedGames;

        double averageMoves()
        {
            return completedGames == 0 ? 0.0 : (double) totalMoves / completedGames;
        }
    }

    private static final class GameOutcome
    {
        final boolean success;
        final double[] utilities;
        final int numMoves;
        final Exception error;

        private GameOutcome(final boolean success, final double[] utilities, final int numMoves, final Exception error)
        {
            this.success = success;
            this.utilities = utilities;
            this.numMoves = numMoves;
            this.error = error;
        }

        static GameOutcome success(final double[] utilities, final int numMoves)
        {
            return new GameOutcome(true, utilities, numMoves, null);
        }

        static GameOutcome failure(final Exception error)
        {
            return new GameOutcome(false, null, 0, error);
        }

        String describeError()
        {
            if (error == null)
                return "unknown error";
            final String message = error.getMessage();
            if (message != null && !message.isEmpty())
                return message;
            return error.toString();
        }
    }
}
