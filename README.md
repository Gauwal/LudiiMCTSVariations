# LudiiMCTSVariations

A comprehensive framework for experimenting with Monte Carlo Tree Search (MCTS) variations in the [Ludii](https://ludii.games/) general game playing system.

This project provides custom MCTS components (selection, simulation, backpropagation strategies), an automated testing pipeline, and tools for running large-scale experiments on HPC clusters via SLURM.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Prerequisites](#prerequisites)
3. [Project Structure](#project-structure)
4. [MCTS Components](#mcts-components)
   - [Selection Strategies](#selection-strategies)
   - [Simulation (Playout) Strategies](#simulation-playout-strategies)
   - [Backpropagation Strategies](#backpropagation-strategies)
   - [Final Move Selection](#final-move-selection)
5. [Using MCTSVariations](#using-mctsvariations)
6. [Experiment Pipeline](#experiment-pipeline)
   - [Step 1: Build the Game Catalog](#step-1-build-the-game-catalog)
   - [Step 2: Generate a Test Plan](#step-2-generate-a-test-plan)
   - [Step 3: Generate SLURM Scripts](#step-3-generate-slurm-scripts)
   - [Step 4: Run Planned Tests](#step-4-run-planned-tests)
   - [Step 5: Analyze Coverage](#step-5-analyze-coverage)
7. [Quick Local Testing](#quick-local-testing)
8. [Configuration Reference](#configuration-reference)
9. [Output Files](#output-files)
10. [Extending the Framework](#extending-the-framework)

---

## Project Overview

This project enables systematic evaluation of MCTS algorithm variations across Ludii's library of 1000+ games. The key goals are:

- **Modular MCTS Configuration**: Mix and match different selection, simulation, and backpropagation strategies
- **Automated Experimentation**: Generate test plans covering different method combinations
- **HPC Support**: Generate SLURM scripts for running experiments on computing clusters
- **Reproducibility**: All experiments are defined in CSV files and can be re-run deterministically

---

## Prerequisites

- **Java 11+** (tested with Java 17)
- **Ludii JAR** - Download from [ludii.games](https://ludii.games/downloads.php)
- **SLURM** (optional) - For HPC cluster execution



## Project Structure

```
LudiiMCTSVariations/
├── src/
│   ├── mcts/                          # MCTS algorithm components
│   │   ├── MCTSVariations.java        # Main wrapper class
│   │   ├── selection/                 # Selection strategies
│   │   │   ├── ProgressiveWidening.java
│   │   │   ├── ImplicitMinimaxSelection.java
│   │   │   └── AlphaBetaSelection.java
│   │   ├── simulation/                # Playout strategies
│   │   │   └── LGRSimulation.java
│   │   └── backpropagation/           # Backpropagation strategies
│   │       ├── ScoreBoundedBackprop.java
│   │       └── ImplicitMinimaxBackprop.java
│   │
│   └── experiments/                   # Experiment infrastructure
│       ├── AITest.java                # Quick local testing harness
│       ├── AutomatedMCTSTesting.java  # Automated experiment runner
│       ├── catalog/                   # Game catalog tools
│       │   ├── BuildGameCatalog.java
│       │   └── GameCatalog.java
│       └── planning/                  # Test planning & SLURM generation
│           ├── GenerateTestPlan.java
│           ├── RunPlannedTest.java
│           ├── GenerateSlurmScripts.java
│           └── ReportPlannedTestCoverage.java
│
├── game_catalog.csv                   # Generated game properties database
├── planned_tests.csv                  # Generated experiment plan
├── mcts_experiments.csv               # Experiment results
└── available_games.csv                # List of compatible games
```

---

## MCTS Components

### Selection Strategies

Strategies for selecting which child node to explore during tree traversal.

| Strategy | String Key | Description |
|----------|-----------|-------------|
| UCB1 | `"UCB1"` | Standard Upper Confidence Bound (default) |
| UCB1 Tuned | `"UCB1 tuned"` | Variance-aware UCB1 |
| UCB1 GRAVE | `"UCB1 GRAVE"` | Generalized Rapid Action Value Estimation |
| Progressive Bias | `"Progressive Bias"` | Heuristic biasing that diminishes with visits |
| Progressive History | `"Progressive History"` | History-based move ordering |
| Progressive Widening | `"Progressive Widening"` | Gradually expands children (k × n^α) |
| Implicit Minimax | `"Implicit Minimax"` | Combines UCB with minimax backups |
| Alpha-Beta | `"Alpha-Beta"` | Alpha-beta pruning within MCTS |
| McBRAVE | `"McBRAVE"` | Monte Carlo with BRAVE heuristic |
| McGRAVE | `"McGRAVE"` | Monte Carlo with GRAVE heuristic |
| AG0 | `"AG0"` | AlphaGo Zero style selection |
| Noisy AG0 | `"Noisy AG0"` | AG0 with exploration noise |
| ExIt | `"ExIt"` | Expert Iteration selection |

### Simulation (Playout) Strategies

Strategies for the simulation/rollout phase from leaf nodes to terminal states.

| Strategy | String Key | Description |
|----------|-----------|-------------|
| Random | `"Random"` | Uniform random move selection (default) |
| MAST | `"MAST"` | Move-Average Sampling Technique |
| NST | `"NST"` | N-gram Selection Technique |
| Heuristic | `"Heuristic"` | Uses game heuristics (requires heuristic support) |
| Heuristic Sampling | `"Heuristic Samping"` | Heuristic with sampling |
| HS Playout | `"HS Playout"` | Hybrid heuristic simulation |
| LGR | `"LGR"` | Last Good Reply - remembers successful responses |

### Backpropagation Strategies

Strategies for propagating simulation results back up the tree.

| Strategy | String Key | Description |
|----------|-----------|-------------|
| Monte Carlo | `"MonteCarlo"` | Standard average backpropagation (default) |
| Heuristic | `"Heuristic"` | Uses game heuristics for evaluation |
| AlphaGo | `"AlphaGo"` | AlphaGo-style value mixing |
| Qualitative | `"Qualitative"` | Qualitative bonus backpropagation |
| Score Bounded | `"Score Bounded"` | Maintains optimistic/pessimistic bounds |
| Implicit Minimax | `"Implicit Minimax"` | Minimax backup structure |

### Final Move Selection

How to choose the final move after MCTS iterations complete.

| Strategy | String Key | Description |
|----------|-----------|-------------|
| Robust Child | `"Robust"` | Most visited child (default) |
| Max Avg Score | `"MaxAvgScore"` | Highest average score |
| Proportional Exp | `"Proportional Exp"` | Proportional to exponential visit count |

---

## Using MCTSVariations

The `MCTSVariations` class is a wrapper around Ludii's MCTS that allows string-based configuration:

```java
import mcts.MCTSVariations;
import game.Game;
import other.GameLoader;
import other.context.Context;
import other.trial.Trial;

// Load a game
Game game = GameLoader.loadGameFromName("Amazons.lud");

// Create custom MCTS configuration
MCTSVariations agent = new MCTSVariations(
    "Progressive Widening",  // Selection strategy
    "MAST",                  // Simulation strategy  
    "Score Bounded",         // Backpropagation strategy
    "Robust"                 // Final move selection
);

// Initialize for a specific player
agent.initAI(game, 1);

// Use in a game
Trial trial = new Trial(game);
Context context = new Context(game, trial);
game.start(context);

while (!context.trial().over()) {
    int mover = context.state().mover();
    Move move = agent.selectAction(game, context, 1.0, -1, -1);  // 1 second per move
    game.apply(context, move);
}

agent.closeAI();
```

### Configuration Flexibility

The string keys are case-insensitive and support various formats:

```java
// These all create the same UCB1 Tuned selection:
new MCTSVariations("UCB1 tuned", "Random", "MonteCarlo", "Robust");
new MCTSVariations("ucb1tuned", "Random", "MonteCarlo", "Robust");
new MCTSVariations("UCB1Tuned", "Random", "MonteCarlo", "Robust");
```

---

## Experiment Pipeline

The full experimental pipeline for systematic MCTS evaluation:

### Step 1: Build the Game Catalog

Creates a database of game properties for all Ludii games. This is run once.

```bash
java -cp "Ludii.jar:bin" experiments.catalog.BuildGameCatalog
```

**Options:**
| Flag | Description |
|------|-------------|
| `--out <path>` | Output CSV path (default: `game_catalog.csv`) |
| `--report <path>` | Build report path (default: `game_catalog_build_report.csv`) |
| `--include-stochastic` | Include stochastic games |
| `--allow-simultaneous` | Include simultaneous-move games |
| `--echo-warnings` | Print all warnings to console |
| `--progress-every <n>` | Print progress every N games |

**Output:** `game_catalog.csv` containing properties for each game:
- Structural: `numPlayers`, `numCells`, `numRows`, `numColumns`, etc.
- Topology: `avgNumDirections`, `avgNumOrthogonal`, `avgNumDiagonal`
- Boolean flags: `isStacking`, `isStochastic`, `hasHeuristics`, etc.

### Step 2: Generate a Test Plan

Creates a CSV of planned experiments covering different MCTS configurations.

```bash
java -cp "Ludii.jar:bin" experiments.planning.GenerateTestPlan \
    --catalog game_catalog.csv \
    --out planned_tests.csv \
    --num-tests 1000 \
    --games-per-matchup 10 \
    --move-time 0.1 \
    --design ONE_FACTOR
```

**Options:**
| Flag | Description |
|------|-------------|
| `--catalog <path>` | Path to game catalog CSV |
| `--out <path>` | Output test plan CSV |
| `--num-tests <n>` | Number of tests to generate |
| `--games-per-matchup <n>` | Games per variant-vs-baseline matchup |
| `--move-time <seconds>` | Time per move |
| `--max-moves <n>` | Maximum moves per game (0 = no limit) |
| `--design <type>` | `ONEFACTOR` (vary one component) or `FULLCOMBO` (all combinations) |
| `--seed <n>` | Random seed for reproducibility |

**Design Types:**
- **ONEFACTOR**: Tests each policy variation while keeping others at baseline (UCB1/Random/MonteCarlo/Robust)
- **FULLCOMBO**: Tests all possible combinations (equivalent if elements are independant (which they are))

### Step 3: Generate SLURM Scripts

Creates batch scripts for HPC cluster execution.

```bash
java -cp "Ludii.jar:bin" experiments.planning.GenerateSlurmScripts \
    --plan planned_tests.csv \
    --catalog game_catalog.csv \
    --out-dir slurm_scripts \
    --project-dir /home/user/LudiiMCTSVariations \
    --ludii-jar /home/user/lib/Ludii.jar \
    --results-dir results
```

**Options:**
| Flag | Description |
|------|-------------|
| `--plan <path>` | Input test plan CSV |
| `--catalog <path>` | Game catalog for resource estimation |
| `--out-dir <dir>` | Directory for generated scripts |
| `--project-dir <path>` | Project directory on cluster |
| `--ludii-jar <path>` | Path to Ludii JAR on cluster |
| `--results-dir <dir>` | Where to write results |
| `--job-prefix <str>` | SLURM job name prefix |
| `--module-load <str>` | Module to load (e.g., `java/17`) |

**Output:**
- Individual test scripts: `test_<testId>.sh`
- Master submit script: `submit_all.sh`

### Step 4: Run Planned Tests

Execute a single test from the plan (used by SLURM scripts):

```bash
java -cp "Ludii.jar:bin" experiments.planning.RunPlannedTest \
    --plan planned_tests.csv \
    --test-id "TEST_001" \
    --out results/TEST_001.csv
```

Or run locally without SLURM:

```bash
# Run all tests sequentially (not recommended for large plans)
for test_id in $(cut -d',' -f1 planned_tests.csv | tail -n +2); do
    java -cp "Ludii.jar:bin" experiments.planning.RunPlannedTest \
        --plan planned_tests.csv \
        --test-id "$test_id" \
        --out "results/${test_id}.csv"
done
```

### Step 5: Analyze Coverage

Check which methods and games are covered by the test plan:

```bash
java -cp "Ludii.jar:bin" experiments.planning.ReportPlannedTestCoverage \
    --in planned_tests.csv
```

**Output Example:**
```
Test Plan Coverage Report
=========================
Total tests: 1000
Unique games: 150

Component Coverage:
  SELECTION: 11/11 methods covered
  SIMULATION: 8/8 methods covered
  BACKPROP: 5/5 methods covered
  FINAL_MOVE: 3/3 methods covered

Top Games by Test Count:
  1. Amazons.lud (25 tests)
  2. Breakthrough.lud (22 tests)
  ...
```

---

## Quick Local Testing

For quick local experiments without the full pipeline, use `AITest`:

```bash
java -cp "Ludii.jar:bin" experiments.AITest
```

This runs all MCTS variations against the UCB1/Random/MonteCarlo baseline on a single game (Amazons by default).

**Configuration** (edit `AITest.java`):
```java
private static final String GAME_NAME = "Amazons.lud";    // Game to test
private static final double MOVE_TIME_SECONDS = 0.1;       // Time per move
private static final int GAMES_PER_MATCHUP = 2;            // Games per configuration
```

**Output:** `aitest_results.csv` with win/loss/draw statistics for each configuration.

---

## Configuration Reference

### Baseline Configuration

The default baseline for comparisons is:
- Selection: `UCB1`
- Simulation: `Random`
- Backpropagation: `MonteCarlo`
- Final Move: `Robust` (most visited child)

### Game Filtering

The framework filters games by default:
- **Excludes stochastic games** (dice, card shuffling)
- **Requires alternating moves** (no simultaneous move games)
- **Two-player games only** (for matchup testing)

Games requiring heuristic support are automatically matched with appropriate heuristic-based methods.

### Resource Estimation

SLURM scripts automatically estimate resources based on:
- Move time × games per matchup × expected game length
- Game complexity (board size, branching factor)
- Method complexity (heuristic methods need more CPU)

---

## Output Files

| File | Description |
|------|-------------|
| `game_catalog.csv` | Database of game properties |
| `game_catalog_build_report.csv` | Warnings/errors from catalog build |
| `planned_tests.csv` | Generated test plan |
| `available_games.csv` | List of valid games for testing |
| `mcts_experiments.csv` | Experiment results (AutomatedMCTSTesting) |
| `aitest_results.csv` | Quick test results (AITest) |
| `results/*.csv` | Individual test results (RunPlannedTest) |

### Result CSV Format

Each result row contains:
```
testId,gameName,component,
baselineSelection,baselineSimulation,baselineBackprop,baselineFinalMove,
variantSelection,variantSimulation,variantBackprop,variantFinalMove,
moveTimeSeconds,gamesPerMatchup,maxMoves,requiresHeuristics,
variantWins,baselineWins,draws,failures,completedGames,attemptedGames,averageMoves,lastError
```

---

## Extending the Framework

### Adding a New Selection Strategy

1. Create a new class implementing `SelectionStrategy`:

```java
package mcts.selection;

import search.mcts.selection.SelectionStrategy;
import search.mcts.MCTS;
import search.mcts.nodes.BaseNode;

public class MyCustomSelection implements SelectionStrategy {
    @Override
    public int select(MCTS mcts, BaseNode current) {
        // Your selection logic here
        return bestChildIndex;
    }
}
```

2. Register it in `MCTSVariations.buildSelectionStrategy()`:

```java
if ("mycustom".equals(normalized) || "my custom".equals(normalized))
    return new StrategyChoice<>(new MyCustomSelection(), "MyCustom");
```

3. Add to the policy arrays in test generators:

```java
// In GenerateTestPlan.java, AITest.java, etc.
private static final String[] SELECTION_POLICIES = {
    // ... existing policies ...
    "My Custom"
};
```

### Adding a New Game Filter

In `GameCatalog.java`, add new row properties and update the CSV schema.

---
