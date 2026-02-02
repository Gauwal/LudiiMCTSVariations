package experiments;

import java.io.*;
import java.util.*;
import java.util.stream.*;

import game.equipment.container.board.Board;
import game.types.state.GameType;
import main.FileHandling;
import mcts.*;
import game.Game;
import other.context.Context;
import other.AI;
import other.GameLoader;
import other.trial.Trial;

public class AutomatedMCTSTesting {

    // ==================== CONFIGURATION ====================

    // Available techniques (strings matching MCTSVariations.java)
        private static final String[] SELECTION_POLICIES = {
            "UCB1",            // Default Ludii UCB1 implementation
            "UCB1 tuned",      // Variance-aware UCB1
            "Progressive Bias", // Heuristic biasing from Ludii
            "Implicit Minimax", // Implicit minimax backups (Algorithm 3.5)
            "Alpha-Beta"        // Alpha-beta MCTS selection (Algorithm 3.6/3.7)
        };

        private static final String[] SIMULATION_POLICIES = {
            "Random",  // Ludii's default random playouts
            "MAST",    // Ludii's implementation of MAST
            "NST"      // N-gram selection technique available in Ludii

        };

        private static final String[] BACKPROP_POLICIES = {
            "MonteCarlo",      // Standard Monte-Carlo backpropagation
            "Heuristic",       // Heuristic backprop in Ludii
            "AlphaGo",         // AlphaGo-style backprop available in Ludii
            "Implicit Minimax" // Implicit minimax backprop (Algorithm 3.5)
        };

    // Games to test (will auto-split train/test)
    private static final String[] ALL_GAMES = FileHandling.listGames();
    private static final List<String> AVAILABLE_GAMES = new ArrayList<String>();
    private static final String GAMES_CSV_PATH = "available_games.csv";
    private static boolean UPDATE_GAME_LIST = false; // Set to true to regenerate the list

    static {
        File csvFile = new File(GAMES_CSV_PATH);


        if (csvFile.exists() && !UPDATE_GAME_LIST) {
            System.out.println("Loading games from CSV: " + GAMES_CSV_PATH);
            try (BufferedReader br = new BufferedReader(new FileReader(csvFile))) {
                String line;
                while ((line = br.readLine()) != null) {
                    line = line.trim();
                    if (!line.isEmpty()) {
                        AVAILABLE_GAMES.add(line);
                    }
                }
                System.out.println("Loaded " + AVAILABLE_GAMES.size() + " games from CSV");
            } catch (IOException e) {
                System.err.println("Error reading games CSV: " + e.getMessage());
                System.out.println("Falling back to extracting games from scratch");
                extractAndSaveGames();
            }
        }
        else{
            extractAndSaveGames();
            // Save to CSV
            try (BufferedWriter bw = new BufferedWriter(new FileWriter(GAMES_CSV_PATH))) {
                for (String gameName : AVAILABLE_GAMES) {
                    bw.write(gameName);
                    bw.newLine();
                }
                System.out.println("Saved " + AVAILABLE_GAMES.size() + " games to " + GAMES_CSV_PATH);
            } catch (IOException e) {
                System.err.println("Error saving games to CSV: " + e.getMessage());
            }
        }
    }
    private static void extractAndSaveGames() {
        System.out.println("Extracting all valid games");
        AVAILABLE_GAMES.clear();
        for (int i = 0; i < ALL_GAMES.length; i++) {
            if (i%100==0){System.out.println(i+"/"+ALL_GAMES.length);}
            String gameName = ALL_GAMES[i];
            Game game = GameLoader.loadGameFromName(gameName);
            // Only add if NOT stochastic and alternating move
            if (game != null && !game.isStochasticGame() && game.isAlternatingMoveGame()) {
                AVAILABLE_GAMES.add(gameName);
            }
        }
    }

    // Testing parameters
    private static final int MIN_GAMES_PER_TEST = 20/4;
    private static final int MAX_GAMES_PER_TEST = 100/5;
    private static final double TIME_PER_MOVE = 0.1; // 100ms
    private static final int TOTAL_EXPERIMENT_BUDGET = 10000/50; // Total games

    // Files for persistence
    private static final String DATA_FILE = "mcts_experiments.csv";
    private static final String GAME_PROPS_FILE = "game_properties.csv";
    private static final String CLASSIFIER_FILE = "mcts_classifiers.dat";

    // ==================== DATA STRUCTURES ====================

    /**
     * Single experimental data point
     */
    public static class DataPoint {
        String gameName;
        String selection;
        String simulation;
        String backprop;
        double winRate;
        int gamesPlayed;
        long timestamp;


        public String toCSV() {
            return String.format("%s,%s,%s,%s,%.4f,%d,%d",
                    gameName, selection, simulation, backprop,
                    winRate, gamesPlayed, timestamp);
        }

        public static DataPoint fromCSV(String line) {
            String[] parts = line.split(",");
            DataPoint dp = new DataPoint();
            dp.gameName = parts[0];
            dp.selection = parts[1];
            dp.simulation = parts[2];
            dp.backprop = parts[3];
            dp.winRate = Double.parseDouble(parts[4]);
            dp.gamesPlayed = Integer.parseInt(parts[5]);
            dp.timestamp = Long.parseLong(parts[6]);
            return dp;
        }

        public String getKey() {
            return gameName + "|" + selection + "|" + simulation + "|" + backprop;
        }
    }

    /**
     * Game property features for classification
     */
    public static class GameFeatures {
        String gameName;

        // Structural features
        int numPlayers;
        int numCells;
        int numVertices;
        int numEdges;
        int numComponents;
        int numPhases;
        int numRows;
        int numColumns;
        int numCorners;
        int numPlayableSites;

        // Topology features
        double avgNumDirections;
        double avgNumOrthogonal;
        double avgNumDiagonal;

        // Boolean features (0 or 1)
        int isStacking;
        int isStochastic;
        int hasHiddenInfo;
        int requiresTeams;
        int hasTrack;
        int hasCard;
        int hasHandDice;
        int isVertexGame;
        int isEdgeGame;
        int isCellGame;
        int isDeductionPuzzle;


        /**
         * Convert to feature array for ML
         */
        public double[] toArray() {
            return new double[] {
                    // Structural (10)
                    numPlayers,
                    numCells,
                    numVertices,
                    numEdges,
                    numComponents,
                    numPhases,
                    numRows,
                    numColumns,
                    numCorners,
                    numPlayableSites,

                    // Topology (3)
                    avgNumDirections,
                    avgNumOrthogonal,
                    avgNumDiagonal,

                    // Boolean (11)
                    isStacking,
                    isStochastic,
                    hasHiddenInfo,
                    requiresTeams,
                    hasTrack,
                    hasCard,
                    hasHandDice,
                    isVertexGame,
                    isEdgeGame,
                    isCellGame,
                    isDeductionPuzzle,

            };
        }

        public String toCSV() {
            return String.format("%s,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%.2f,%.2f,%.2f," +
                            "%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d",
                    gameName,
                    numPlayers, numCells, numVertices, numEdges, numComponents,
                    numPhases, numRows, numColumns, numCorners, numPlayableSites,
                    avgNumDirections, avgNumOrthogonal, avgNumDiagonal,
                    isStacking, isStochastic, hasHiddenInfo, requiresTeams,
                    hasTrack, hasCard, hasHandDice, isVertexGame, isEdgeGame,
                    isCellGame, isDeductionPuzzle);
        }

        public static GameFeatures fromCSV(String line) {
            String[] parts = line.split(",");
            GameFeatures gf = new GameFeatures();
            int i = 0;
            gf.gameName = parts[i++];
            gf.numPlayers = Integer.parseInt(parts[i++]);
            gf.numCells = Integer.parseInt(parts[i++]);
            gf.numVertices = Integer.parseInt(parts[i++]);
            gf.numEdges = Integer.parseInt(parts[i++]);
            gf.numComponents = Integer.parseInt(parts[i++]);
            gf.numPhases = Integer.parseInt(parts[i++]);
            gf.numRows = Integer.parseInt(parts[i++]);
            gf.numColumns = Integer.parseInt(parts[i++]);
            gf.numCorners = Integer.parseInt(parts[i++]);
            gf.numPlayableSites = Integer.parseInt(parts[i++]);
            gf.avgNumDirections = Double.parseDouble(parts[i++]);
            gf.avgNumOrthogonal = Double.parseDouble(parts[i++]);
            gf.avgNumDiagonal = Double.parseDouble(parts[i++]);
            gf.isStacking = Integer.parseInt(parts[i++]);
            gf.isStochastic = Integer.parseInt(parts[i++]);
            gf.hasHiddenInfo = Integer.parseInt(parts[i++]);
            gf.requiresTeams = Integer.parseInt(parts[i++]);
            gf.hasTrack = Integer.parseInt(parts[i++]);
            gf.hasCard = Integer.parseInt(parts[i++]);
            gf.hasHandDice = Integer.parseInt(parts[i++]);
            gf.isVertexGame = Integer.parseInt(parts[i++]);
            gf.isEdgeGame = Integer.parseInt(parts[i++]);
            gf.isCellGame = Integer.parseInt(parts[i++]);
            gf.isDeductionPuzzle = Integer.parseInt(parts[i++]);
            return gf;
        }
    }

    // ==================== STATE ====================

    private List<DataPoint> allData;
    private Map<String, GameFeatures> gameFeatures;
    private List<String> trainingGames;
    private List<String> testGames;
    private Random random;
    private int gamesPlayedTotal;

    // Classifiers
    private SimpleClassifier selectionClassifier;
    private SimpleClassifier simulationClassifier;
    private SimpleClassifier backpropClassifier;

    // ==================== MAIN PIPELINE ====================

    public AutomatedMCTSTesting() {
        this.allData = new ArrayList<>();
        this.gameFeatures = new HashMap<>();
        this.random = new Random(42);
        this.gamesPlayedTotal = 0;
    }

    /**
     * MAIN ENTRY POINT: Run the full testing pipeline
     */
    public void runFullPipeline() {
        System.out.println("╔════════════════════════════════════════════════════╗");
        System.out.println("║   AUTOMATED MCTS TESTING & CLASSIFICATION SYSTEM   ║");
        System.out.println("╚════════════════════════════════════════════════════╝\n");

        System.out.println("[STEP 1] Extracting Static Game Features...");
        loadOrExtractGameFeatures();

        System.out.println("\n[STEP 2] Splitting Games (70% train, 30% test)...");
        splitTrainTestGames();

        System.out.println("\n[STEP 3] Loading Previous Experiments...");
        loadExistingData();

        System.out.println("\n[STEP 4] Running Intelligent Experiments...");
        runActiveExperiments();

        System.out.println("\n[STEP 5] Training Component Classifiers...");
        trainClassifiers();

        System.out.println("\n[STEP 6] Evaluating on Holdout Games...");
        evaluateOnTestSet();

        System.out.println("\n[STEP 7] Generating Final Report...");
        generateReport();

        System.out.println("\n╔════════════════════════════════════════════════════╗");
        System.out.println("║                  TESTING COMPLETE                  ║");
        System.out.println("╚════════════════════════════════════════════════════╝");
    }

    // ==================== STEP IMPLEMENTATIONS ====================

    /**
     * Load cached features or extract from Game objects
     */
    private void loadOrExtractGameFeatures() {
        File file = new File(GAME_PROPS_FILE);
        if (file.exists()) {
            System.out.println("  Loading cached static features...");
            try (BufferedReader br = new BufferedReader(new FileReader(file))) {
                String line = br.readLine();
                while ((line = br.readLine()) != null) {
                    GameFeatures gf = GameFeatures.fromCSV(line);
                    gameFeatures.put(gf.gameName, gf);
                }
                System.out.println("  Loaded " + gameFeatures.size() + " cached features");
            } catch (IOException e) {
                System.err.println("  Error loading: " + e.getMessage());
            }
        }

        // Extract features for missing games
        int extracted = 0;
        for (String gameName : AVAILABLE_GAMES) {
            if (!gameFeatures.containsKey(gameName)) {
                System.out.println("  Extracting features: " + gameName);
                Game game = GameLoader.loadGameFromName(gameName);
                if (game != null) {
                    GameFeatures gf = extractStaticFeatures(game);
                    gameFeatures.put(gameName, gf);
                    extracted++;
                }
            }
        }

        if (extracted > 0) {
            System.out.println("  Extracted " + extracted + " new feature sets");
            saveGameFeatures();
        }

        System.out.println("  Total games: " + gameFeatures.size());
    }

    /**
     * Extract static features from Game object
     */
    private GameFeatures extractStaticFeatures(Game game) {
        GameFeatures gf = new GameFeatures();
        gf.gameName = game.name();

        Trial trial = new Trial(game);
        Context context = new Context(game, trial);

        // Structural features
        gf.numPlayers = game.players().count();

        // Safely get board features - handle null board
        Board board = context.board();
        if (board != null && board.topology() != null) {
            gf.numCells = board.topology().cells().size();
            gf.numVertices = board.topology().vertices().size();
            gf.numEdges = board.topology().edges().size();

            // Topology features (with safe defaults)
            try {
                gf.numRows = board.topology().rows(board.defaultSite()).size();
                gf.numColumns = board.topology().columns(board.defaultSite()).size();
                gf.numCorners = board.topology().corners(board.defaultSite()).size();
            } catch (Exception e) {
                gf.numRows = 0;
                gf.numColumns = 0;
                gf.numCorners = 0;
            }
        } else {
            // Default values for games without proper board
            gf.numCells = 0;
            gf.numVertices = 0;
            gf.numEdges = 0;
            gf.numRows = 0;
            gf.numColumns = 0;
            gf.numCorners = 0;
        }

        // Other features that don't depend on board
        gf.numComponents = context.equipment().components().length - 1;
        gf.numPhases = context.rules().phases().length;

        // Playable sites from concepts
        String numSitesStr = game.nonBooleanConcepts().get(
                other.concept.Concept.NumPlayableSites.id()
        );
        if (numSitesStr != null) {
            String s = numSitesStr.trim();
            if (s.endsWith(".0")) s = s.substring(0, s.length() - 2);
            try {
                gf.numPlayableSites = Integer.parseInt(s);
            } catch (NumberFormatException e) {
                gf.numPlayableSites = 0;
            }
        } else {
            gf.numPlayableSites = gf.numCells + gf.numVertices + gf.numEdges;
        }

        // Average directions from concepts
        String avgDirStr = game.nonBooleanConcepts().get(
                other.concept.Concept.NumDirections.id()
        );
        gf.avgNumDirections = avgDirStr != null ?
                Double.parseDouble(avgDirStr) : 4.0;

        String avgOrthStr = game.nonBooleanConcepts().get(
                other.concept.Concept.NumOrthogonalDirections.id()
        );
        gf.avgNumOrthogonal = avgOrthStr != null ?
                Double.parseDouble(avgOrthStr) : 2.0;

        String avgDiagStr = game.nonBooleanConcepts().get(
                other.concept.Concept.NumDiagonalDirections.id()
        );
        gf.avgNumDiagonal = avgDiagStr != null ?
                Double.parseDouble(avgDiagStr) : 2.0;

        // Boolean features (convert to 0/1) - use safe methods
        gf.isStacking = game.isStacking() ? 1 : 0;
        gf.isStochastic = game.isStochasticGame() ? 1 : 0;
        gf.hasHiddenInfo = game.hiddenInformation() ? 1 : 0;
        gf.requiresTeams = game.requiresTeams() ? 1 : 0;

        // Safely check for track
        try {
            gf.hasTrack = game.hasTrack() ? 1 : 0;
        } catch (NullPointerException e) {
            gf.hasTrack = 0; // Default to no track if check fails
        }

        gf.hasCard = game.hasCard() ? 1 : 0;

        // Safely check for hand dice
        try {
            gf.hasHandDice = game.hasHandDice() ? 1 : 0;
        } catch (NullPointerException e) {
            gf.hasHandDice = 0;
        }

        gf.isVertexGame = context.isVertexGame() ? 1 : 0;
        gf.isEdgeGame = context.isEdgeGame() ? 1 : 0;
        gf.isCellGame = context.isCellGame() ? 1 : 0;
        gf.isDeductionPuzzle = game.isDeductionPuzzle() ? 1 : 0;


        return gf;
    }

    private void splitTrainTestGames() {
        List<String> gamesWithFeatures = new ArrayList<>(gameFeatures.keySet());
        Collections.shuffle(gamesWithFeatures, random);

        int trainSize = (int) (gamesWithFeatures.size() * 0.7);
        trainingGames = gamesWithFeatures.subList(0, trainSize);
        testGames = gamesWithFeatures.subList(trainSize, gamesWithFeatures.size());

        System.out.println("  Training: " + trainingGames.size() + " games");
        System.out.println("  Test: " + testGames.size() + " games");
    }

    private void loadExistingData() {
        File file = new File(DATA_FILE);
        if (!file.exists()) {
            System.out.println("  No previous data found");
            return;
        }

        try (BufferedReader br = new BufferedReader(new FileReader(file))) {
            String line = br.readLine(); // Skip header
            while ((line = br.readLine()) != null) {
                DataPoint dp = DataPoint.fromCSV(line);
                allData.add(dp);
                gamesPlayedTotal += dp.gamesPlayed;
            }
            System.out.println("  Loaded " + allData.size() + " experiments");
            System.out.println("  Total games played: " + gamesPlayedTotal);
        } catch (IOException e) {
            System.err.println("  Error: " + e.getMessage());
        }
    }

    private void runActiveExperiments() {
        System.out.println("  Budget: " + TOTAL_EXPERIMENT_BUDGET + " games");
        System.out.println("  Remaining: " +
                (TOTAL_EXPERIMENT_BUDGET - gamesPlayedTotal) + " games\n");

        ActiveExperimentSelector selector = new ActiveExperimentSelector(
                trainingGames,
                Arrays.asList(SELECTION_POLICIES),
                Arrays.asList(SIMULATION_POLICIES),
                Arrays.asList(BACKPROP_POLICIES),
                allData
        );

        int iteration = 0;
        while (gamesPlayedTotal < TOTAL_EXPERIMENT_BUDGET) {
            ExperimentConfig config = selector.selectNextExperiment();
            if (config == null) {
                System.out.println("  All experiments completed!");
                break;
            }

            // Check existing data
            Optional<DataPoint> existing = allData.stream()
                    .filter(dp -> dp.getKey().equals(config.getKey()))
                    .findFirst();

            if (existing.isPresent() &&
                    existing.get().gamesPlayed >= MIN_GAMES_PER_TEST) {
                selector.markAsComplete(config);
                continue;
            }

            // Run experiment
            System.out.printf("  [%d] %s | %s | %s | %s\n",
                    ++iteration, config.gameName, config.selection,
                    config.simulation, config.backprop);

            DataPoint result = runExperiment(config);

            if (existing.isPresent()) {
                allData.remove(existing.get());
            }
            allData.add(result);
            gamesPlayedTotal += result.gamesPlayed;

            saveData();
            selector.updateWithResult(result);

            System.out.printf("    → %.1f%% win rate | Total: %d/%d\n",
                    result.winRate * 100, gamesPlayedTotal,
                    TOTAL_EXPERIMENT_BUDGET);
        }
    }

    private DataPoint runExperiment(ExperimentConfig config) {
        Game game = GameLoader.loadGameFromName(config.gameName);

        int wins = 0;
        int total = 0;

        // Play against baseline
        for (int i = 0; i < MIN_GAMES_PER_TEST && total < MAX_GAMES_PER_TEST; i++) {
            boolean won1 = playGame(game, config, getBaseline(), true);
            if (won1) wins++;
            total++;

            boolean won2 = playGame(game, getBaseline(), config, false);
            if (won2) wins++;
            total++;
        }

        DataPoint dp = new DataPoint();
        dp.gameName = config.gameName;
        dp.selection = config.selection;
        dp.simulation = config.simulation;
        dp.backprop = config.backprop;
        dp.winRate = (double) wins / total;
        dp.gamesPlayed = total;
        dp.timestamp = System.currentTimeMillis();

        return dp;
    }

    private boolean playGame(Game game, ExperimentConfig config1,
                             ExperimentConfig config2, boolean returnP1Result) {
        Context context = new Context(game, new other.trial.Trial(game));
        game.start(context);

        AI agent1 = new MCTSVariations(config1.selection, config1.simulation,
                config1.backprop, "robust");
        AI agent2 = new MCTSVariations(config2.selection, config2.simulation,
                config2.backprop, "robust");

        agent1.initAI(game, 1);
        agent2.initAI(game, 2);

        int moves = 0;
        while (!context.trial().over() && moves < 500) {
            int mover = context.state().mover();
            AI agent = (mover == 1) ? agent1 : agent2;

            other.move.Move move = agent.selectAction(
                    game, new Context(context), TIME_PER_MOVE, -1, -1
            );

            if (move != null) {
                game.apply(context, move);
            }
            moves++;
        }

        if (!context.trial().over()) return false;

        double[] utils = other.RankUtils.utilities(context);
        return returnP1Result ? (utils[1] > utils[2]) : (utils[2] > utils[1]);
    }

    private ExperimentConfig getBaseline() {
        ExperimentConfig baseline = new ExperimentConfig();
        baseline.selection = "default";
        baseline.simulation = "default";
        baseline.backprop = "default";
        return baseline;
    }

    /**
     * Train 3 independent classifiers
     * Each predicts the best technique for its component
     */
    private void trainClassifiers() {
        System.out.println("  Training Selection Classifier...");
        selectionClassifier = trainComponentClassifier("selection");
        double selAcc = evaluateClassifier(selectionClassifier, "selection", trainingGames);
        System.out.println("    Training accuracy: " + String.format("%.1f%%", selAcc * 100));

        System.out.println("  Training Simulation Classifier...");
        simulationClassifier = trainComponentClassifier("simulation");
        double simAcc = evaluateClassifier(simulationClassifier, "simulation", trainingGames);
        System.out.println("    Training accuracy: " + String.format("%.1f%%", simAcc * 100));

        System.out.println("  Training Backprop Classifier...");
        backpropClassifier = trainComponentClassifier("backprop");
        double backAcc = evaluateClassifier(backpropClassifier, "backprop", trainingGames);
        System.out.println("    Training accuracy: " + String.format("%.1f%%", backAcc * 100));
    }

    /**
     * Train a classifier for one component
     * Goal: predict which value achieves highest winrate
     */
    private SimpleClassifier trainComponentClassifier(String component) {
        // For each game, find best component value
        Map<String, Map<String, List<Double>>> gameComponentScores = new HashMap<>();

        for (DataPoint dp : allData) {
            if (!trainingGames.contains(dp.gameName)) continue;

            String componentValue = getComponentValue(dp, component);
            gameComponentScores
                    .computeIfAbsent(dp.gameName, k -> new HashMap<>())
                    .computeIfAbsent(componentValue, k -> new ArrayList<>())
                    .add(dp.winRate);
        }

        // Create training examples
        List<double[]> features = new ArrayList<>();
        List<String> labels = new ArrayList<>();

        for (Map.Entry<String, Map<String, List<Double>>> entry :
                gameComponentScores.entrySet()) {
            String gameName = entry.getKey();
            Map<String, List<Double>> compScores = entry.getValue();

            // Find best by average winrate
            String best = compScores.entrySet().stream()
                    .max(Comparator.comparingDouble(e ->
                            e.getValue().stream().mapToDouble(Double::doubleValue)
                                    .average().orElse(0.0)))
                    .map(Map.Entry::getKey)
                    .orElse("default");

            features.add(gameFeatures.get(gameName).toArray());
            labels.add(best);
        }

        return new SimpleClassifier(features, labels);
    }

    private String getComponentValue(DataPoint dp, String component) {
        switch (component) {
            case "selection": return dp.selection;
            case "simulation": return dp.simulation;
            case "backprop": return dp.backprop;
            default: return "default";
        }
    }

    private double evaluateClassifier(SimpleClassifier classifier,
                                      String component, List<String> games) {
        int correct = 0;
        int total = 0;

        for (String game : games) {
            double[] features = gameFeatures.get(game).toArray();
            String prediction = classifier.predict(features);

            // Find actual best from data
            String actual = allData.stream()
                    .filter(dp -> dp.gameName.equals(game))
                    .max(Comparator.comparingDouble(dp -> dp.winRate))
                    .map(dp -> getComponentValue(dp, component))
                    .orElse("default");

            if (prediction.equals(actual)) correct++;
            total++;
        }

        return total > 0 ? (double) correct / total : 0.0;
    }

    private void evaluateOnTestSet() {
        System.out.println("\n  Predictions on Holdout Games:\n");

        for (String gameName : testGames) {
            System.out.println("  Game: " + gameName);

            double[] features = gameFeatures.get(gameName).toArray();

            String predSel = selectionClassifier.predict(features);
            String predSim = simulationClassifier.predict(features);
            String predBack = backpropClassifier.predict(features);

            System.out.println("    Predicted: " + predSel + " + " +
                    predSim + " + " + predBack);

            // Test if budget allows
            if (gamesPlayedTotal < TOTAL_EXPERIMENT_BUDGET) {
                ExperimentConfig config = new ExperimentConfig();
                config.gameName = gameName;
                config.selection = predSel;
                config.simulation = predSim;
                config.backprop = predBack;

                DataPoint result = runExperiment(config);
                allData.add(result);
                gamesPlayedTotal += result.gamesPlayed;
                saveData();

                System.out.printf("    Tested: %.1f%% win rate\n",
                        result.winRate * 100);
            }
        }
    }

    private void generateReport() {
        System.out.println("\n╔═══ FINAL RESULTS ═══════════════════════════════════╗");
        System.out.println("║ Test Set Accuracy (Predicting Best Technique)      ║");
        System.out.println("╠═════════════════════════════════════════════════════╣");

        double selAcc = evaluateClassifier(selectionClassifier, "selection", testGames);
        double simAcc = evaluateClassifier(simulationClassifier, "simulation", testGames);
        double backAcc = evaluateClassifier(backpropClassifier, "backprop", testGames);

        System.out.printf("║ Selection Policy:   %.1f%%                         ║\n", selAcc * 100);
        System.out.printf("║ Simulation Policy:  %.1f%%                         ║\n", simAcc * 100);
        System.out.printf("║ Backprop Policy:    %.1f%%                         ║\n", backAcc * 100);
        System.out.println("╚═════════════════════════════════════════════════════╝");

        System.out.println("\nInsights by Game Type:");
        generateInsights();
    }

    private void generateInsights() {


        // Many playable sites
        List<String> largeBoardGames = gameFeatures.values().stream()
                .filter(gf -> gf.numPlayableSites > 50)
                .map(gf -> gf.gameName)
                .collect(Collectors.toList());

        if (!largeBoardGames.isEmpty()) {
            String bestSim = findMostCommonBest(largeBoardGames, "simulation");
            System.out.println("  • Large board games → " + bestSim + " simulation");
        }

        // Stacking games
        List<String> stackingGames = gameFeatures.values().stream()
                .filter(gf -> gf.isStacking == 1)
                .map(gf -> gf.gameName)
                .collect(Collectors.toList());

        if (!stackingGames.isEmpty()) {
            String bestBack = findMostCommonBest(stackingGames, "backprop");
            System.out.println("  • Stacking games → " + bestBack + " backprop");
        }
    }

    private String findMostCommonBest(List<String> games, String component) {
        Map<String, Integer> counts = new HashMap<>();

        for (String game : games) {
            String best = allData.stream()
                    .filter(dp -> dp.gameName.equals(game))
                    .max(Comparator.comparingDouble(dp -> dp.winRate))
                    .map(dp -> getComponentValue(dp, component))
                    .orElse("default");

            counts.merge(best, 1, Integer::sum);
        }

        return counts.entrySet().stream()
                .max(Comparator.comparingInt(Map.Entry::getValue))
                .map(Map.Entry::getKey)
                .orElse("default");
    }

    // ==================== PERSISTENCE ====================

    private void saveData() {
        try (PrintWriter pw = new PrintWriter(new FileWriter(DATA_FILE))) {
            pw.println("game,selection,simulation,backprop,winRate,gamesPlayed,timestamp");
            for (DataPoint dp : allData) {
                pw.println(dp.toCSV());
            }
        } catch (IOException e) {
            System.err.println("Error saving: " + e.getMessage());
        }
    }

    private void saveGameFeatures() {
        try (PrintWriter pw = new PrintWriter(new FileWriter(GAME_PROPS_FILE))) {
            pw.println("game,numPlayers,numCells,numVertices,numEdges,numComponents," +
                    "numPhases,numRows,numColumns,numCorners,numPlayableSites," +
                    "avgNumDirections,avgNumOrthogonal,avgNumDiagonal," +
                    "isStacking,isStochastic,hasHiddenInfo,requiresTeams,hasTrack," +
                    "hasCard,hasHandDice,isVertexGame,isEdgeGame,isCellGame," +
                    "isDeductionPuzzle,isSimultaneous,isAlternating," +
                    "maxCount,maxLocalStates,stateSpaceLog");
            for (GameFeatures gf : gameFeatures.values()) {
                pw.println(gf.toCSV());
            }
        } catch (IOException e) {
            System.err.println("Error saving: " + e.getMessage());
        }
    }

    // ==================== HELPER CLASSES ====================

    static class ExperimentConfig {
        String gameName;
        String selection;
        String simulation;
        String backprop;

        String getKey() {
            return gameName + "|" + selection + "|" + simulation + "|" + backprop;
        }
    }

    static class ActiveExperimentSelector {
        private List<String> games;
        private List<String> selections;
        private List<String> simulations;
        private List<String> backprops;
        private Map<String, Integer> experimentCounts;
        private Map<String, Double> expectedInfo;
        private Random random;

        ActiveExperimentSelector(List<String> games, List<String> sel,
                                 List<String> sim, List<String> back,
                                 List<DataPoint> existingData) {
            this.games = games;
            this.selections = sel;
            this.simulations = sim;
            this.backprops = back;
            this.experimentCounts = new HashMap<>();
            this.expectedInfo = new HashMap<>();
            this.random = new Random(42);

            for (DataPoint dp : existingData) {
                experimentCounts.merge(dp.getKey(), 1, Integer::sum);
            }
        }

        ExperimentConfig selectNextExperiment() {
            double bestScore = Double.NEGATIVE_INFINITY;
            ExperimentConfig best = null;

            int totalExp = experimentCounts.values().stream()
                    .mapToInt(Integer::intValue).sum();

            for (String game : games) {
                for (String sel : selections) {
                    for (String sim : simulations) {
                        for (String back : backprops) {
                            String key = game + "|" + sel + "|" + sim + "|" + back;
                            int count = experimentCounts.getOrDefault(key, 0);

                            double info = expectedInfo.getOrDefault(key, 1.0);
                            double exploration = Math.sqrt(
                                    2 * Math.log(totalExp + 1) / (count + 1)
                            );
                            double score = info + exploration;

                            if (score > bestScore) {
                                bestScore = score;
                                ExperimentConfig config = new ExperimentConfig();
                                config.gameName = game;
                                config.selection = sel;
                                config.simulation = sim;
                                config.backprop = back;
                                best = config;
                            }
                        }
                    }
                }
            }

            return best;
        }

        void updateWithResult(DataPoint dp) {
            String key = dp.getKey();
            experimentCounts.merge(key, 1, Integer::sum);
            double info = Math.abs(dp.winRate - 0.5);
            expectedInfo.put(key, info);
        }

        void markAsComplete(ExperimentConfig config) {
            experimentCounts.merge(config.getKey(), 999, Integer::sum);
        }
    }

    /**
     * Simple k-NN classifier
     */
    static class SimpleClassifier {
        private List<double[]> trainingFeatures;
        private List<String> trainingLabels;
        private int k = 5;

        SimpleClassifier(List<double[]> features, List<String> labels) {
            this.trainingFeatures = features;
            this.trainingLabels = labels;
        }

        String predict(double[] features) {
            if (trainingFeatures.isEmpty()) return "default";

            PriorityQueue<ScoredLabel> nearest = new PriorityQueue<>(
                    Comparator.comparingDouble((ScoredLabel sl) -> sl.distance).reversed()
            );

            for (int i = 0; i < trainingFeatures.size(); i++) {
                double dist = euclideanDistance(features, trainingFeatures.get(i));
                nearest.offer(new ScoredLabel(trainingLabels.get(i), dist));
                if (nearest.size() > k) nearest.poll();
            }

            // Majority vote
            Map<String, Integer> votes = new HashMap<>();
            while (!nearest.isEmpty()) {
                ScoredLabel sl = nearest.poll();
                votes.merge(sl.label, 1, Integer::sum);
            }

            return votes.entrySet().stream()
                    .max(Comparator.comparingInt(Map.Entry::getValue))
                    .map(Map.Entry::getKey)
                    .orElse("default");
        }

        private double euclideanDistance(double[] a, double[] b) {
            double sum = 0;
            for (int i = 0; i < Math.min(a.length, b.length); i++) {
                sum += Math.pow(a[i] - b[i], 2);
            }
            return Math.sqrt(sum);
        }

        static class ScoredLabel {
            String label;
            double distance;
            ScoredLabel(String l, double d) { label = l; distance = d; }
        }
    }

    // ==================== MAIN ====================

    public static void main(String[] args) {
        AutomatedMCTSTesting tester = new AutomatedMCTSTesting();
        tester.runFullPipeline();
    }
}