package experiments.planning;

import experiments.catalog.GameCatalog;
import game.Game;
import other.GameLoader;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.IOException;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Random;
import java.util.Set;
import java.util.stream.Collectors;

public final class GenerateTestPlan
{
	// -------------------- METHODS TO COVER --------------------

	// Keep these lists as the single source of truth for test generation.
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

	private static final String[] BACKPROP_POLICIES = {
			"MonteCarlo",
			"Heuristic",
			"AlphaGo",
			"Qualitative",
			"Score Bounded",
			"Implicit Minimax"
	};

	private static final String[] FINAL_MOVE_POLICIES = {
			"Robust",
			"MaxAvgScore",
			"Proportional Exp"
	};

	/**
	 * Methods that require heuristic support in the game definition.
	 *
	 * Note: This is intentionally conservative and can be extended.
	 */
	private static final Set<String> HEURISTIC_REQUIRED_SIM = new HashSet<>(Arrays.asList(
			"Heuristic",
			"Heuristic Samping",
			"HS Playout",
			"PlayoutHS",
			"LGR"
	));

	// -------------------- DEFAULT BASELINE --------------------

	private static final Config BASELINE = new Config(
			"UCB1",
			"Random",
			"MonteCarlo",
			"Robust"
	);

	// -------------------- CLI --------------------

	public static void main(final String[] args) throws Exception
	{
		final Args parsed = Args.parse(args);

		final Path catalogPath = parsed.catalogPath != null
				? parsed.catalogPath
				: Paths.get(GameCatalog.DEFAULT_CSV_NAME);

		// Load the precomputed game table so we can pick games by properties
		// (instead of re-loading and re-analyzing all games here).
		final GameCatalog.Table catalog = GameCatalog.load(catalogPath);

		final List<GameCatalog.Row> candidates = catalog.stream()
				.filter(r -> parsed.requireTwoPlayer ? r.numPlayers == 2 : r.numPlayers >= 2)
				.collect(Collectors.toList());

		if (candidates.isEmpty())
			throw new IllegalStateException("No candidate games found after filtering.");

		// Existing tests are used to avoid duplicates and to bias toward under-covered methods.
		final ExistingTests existing = ExistingTests.loadAll(parsed.existingPaths);

		// FeatureSpace turns catalog rows into numeric vectors so we can pick diverse games
		// ("as little in common as possible") per method.
		final FeatureSpace featureSpace = FeatureSpace.from(candidates);
		final Planner planner = new Planner(parsed.seed, existing, featureSpace);

		final List<TestSpec> planned;
		switch (parsed.design)
		{
			case FULL_COMBO:
				planned = planner.planFullCombo(
						candidates,
						parsed.numTests,
						parsed.gamesPerMatchup,
						parsed.moveTimeSeconds,
						parsed.maxMoves
				);
				break;
			case ONE_FACTOR:
			default:
				planned = planner.planOneFactor(
						candidates,
						parsed.numTests,
						parsed.gamesPerMatchup,
						parsed.moveTimeSeconds,
						parsed.maxMoves
				);
				break;
		}

		writePlanCsv(planned, parsed.outPath);
		System.out.println("Wrote " + planned.size() + " tests to: " + parsed.outPath.toAbsolutePath());
	}

	// -------------------- PLANNING --------------------

	enum Design
	{
		ONE_FACTOR,
		FULL_COMBO
	}

	enum Component
	{
		SELECTION,
		SIMULATION,
		BACKPROP,
		FINAL_MOVE,
		FULL
	}

	static final class Config
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
	}

	static final class TestSpec
	{
		final String testId;
		final String gameName;
		final Component component;

		final Config baseline;
		final Config variant;

		final int gamesPerMatchup;
		final double moveTimeSeconds;
		final int maxMoves;
		final int requiresHeuristics;

		TestSpec(
				final String testId,
				final String gameName,
				final Component component,
				final Config baseline,
				final Config variant,
				final int gamesPerMatchup,
				final double moveTimeSeconds,
				final int maxMoves,
				final int requiresHeuristics)
		{
			this.testId = testId;
			this.gameName = gameName;
			this.component = component;
			this.baseline = baseline;
			this.variant = variant;
			this.gamesPerMatchup = gamesPerMatchup;
			this.moveTimeSeconds = moveTimeSeconds;
			this.maxMoves = maxMoves;
			this.requiresHeuristics = requiresHeuristics;
		}

		String key()
		{
			return normalize(gameName) + "|" + component.name() + "|" +
				normalize(baseline.selection) + "|" + normalize(baseline.simulation) + "|" + normalize(baseline.backprop) + "|" + normalize(baseline.finalMove) + "|" +
				normalize(variant.selection) + "|" + normalize(variant.simulation) + "|" + normalize(variant.backprop) + "|" + normalize(variant.finalMove);
		}
	}

	static final class Planner
	{
		private final Random rng;
		private final ExistingTests existing;
		private final FeatureSpace featureSpace;
		private final Map<String, Boolean> heuristicCache = new HashMap<>();

		Planner(final long seed, final ExistingTests existing, final FeatureSpace featureSpace)
		{
			this.rng = new Random(seed);
			this.existing = existing;
			this.featureSpace = featureSpace;
		}

		List<TestSpec> planOneFactor(
				final List<GameCatalog.Row> candidates,
				final int numTests,
				final int gamesPerMatchup,
				final double moveTimeSeconds,
				final int maxMoves)
		{
			// New definition of coverage (per your request):
			// A method is "covered" when it has tests on games spanning many different properties.
			// We therefore greedily add the single test (method + game) with the best *marginal diversity gain*
			// each step, scanning all feasible games rather than sampling on demand.
			final List<TestSpec> out = new ArrayList<>();
			final Map<String, Integer> globalGameCounts = new HashMap<>(existing.gameCounts);

			final List<String> gameNames = candidates.stream().map(r -> r.gameName).collect(Collectors.toList());
			final Map<String, Integer> gameIndex = new HashMap<>();
			for (int i = 0; i < gameNames.size(); i++)
				gameIndex.put(gameNames.get(i), i);

			// Precompute heuristic capability per candidate (expensive reflection + game load).
			final boolean[] gameHasHeuristics = new boolean[gameNames.size()];
			boolean anyHeuristicGame = false;
			for (int i = 0; i < gameNames.size(); i++)
			{
				final boolean h = hasHeuristics(gameNames.get(i));
				gameHasHeuristics[i] = h;
				anyHeuristicGame |= h;
			}

			final CoverageByDiversity coverage = new CoverageByDiversity(featureSpace, gameNames, gameIndex, existing, anyHeuristicGame);

			// Guard exists to prevent infinite loops when the space is exhausted by duplicates/constraints.
			int guard = 0;
			while (out.size() < numTests && guard++ < numTests * 50)
			{
				Candidate best = null;
				double bestGain = Double.NEGATIVE_INFINITY;

				for (final Component component : Arrays.asList(Component.SELECTION, Component.SIMULATION, Component.BACKPROP, Component.FINAL_MOVE))
				{
					for (final String method : CoverageByDiversity.domainFor(component))
					{
						if (!coverage.allowedByGlobalFeasibility(component, method))
							continue;
						final boolean requiresH = (component == Component.SIMULATION) && HEURISTIC_REQUIRED_SIM.contains(method);

						final CoverageByDiversity.MethodState state = coverage.state(component, method);
						for (int gi = 0; gi < gameNames.size(); gi++)
						{
							if (requiresH && !gameHasHeuristics[gi])
								continue;
							if (state.isSelected(gi))
								continue;

							final String game = gameNames.get(gi);
							final double diversityGain = state.currentGain(gi);
							if (diversityGain <= 0.0)
								continue;

							final int globalCount = globalGameCounts.getOrDefault(game, 0);
							final double gain = diversityGain - 0.05 * globalCount;
							if (gain <= bestGain)
								continue;

							// Build the candidate test key without allocating full TestSpec objects.
							final String key = testKeyOneFactor(game, component, method);
							if (existing.testKeys.contains(key))
								continue;

							bestGain = gain;
							best = new Candidate(component, method, gi, gain);
						}
					}
				}

				if (best == null)
					break;

				final String game = gameNames.get(best.gameIndex);
				final Config variant = makeVariant(BASELINE, best.component, best.method);
				final int requiresHeuristics = requiresHeuristics(variant) ? 1 : 0;
				if (requiresHeuristics == 1 && !gameHasHeuristics[best.gameIndex])
					continue;

				final TestSpec spec = new TestSpec(
						"T" + (out.size() + 1),
						game,
						best.component,
						BASELINE,
						variant,
						gamesPerMatchup,
						moveTimeSeconds,
						maxMoves,
						requiresHeuristics
				);

				final String key = spec.key();
				if (existing.testKeys.contains(key))
					continue;

				out.add(spec);
				existing.recordPlanned(spec);
				coverage.record(best.component, best.method, best.gameIndex);
				globalGameCounts.merge(game, 1, Integer::sum);
			}

			return out;
		}

		List<TestSpec> planFullCombo(
				final List<GameCatalog.Row> candidates,
				final int numTests,
				final int gamesPerMatchup,
				final double moveTimeSeconds,
				final int maxMoves)
		{
			// Simplified "full combo" under the same coverage definition:
			// choose the single game + 4-method variant that maximizes total marginal diversity gain.
			final List<TestSpec> out = new ArrayList<>();
			final Map<String, Integer> globalGameCounts = new HashMap<>(existing.gameCounts);

			final List<String> gameNames = candidates.stream().map(r -> r.gameName).collect(Collectors.toList());
			final Map<String, Integer> gameIndex = new HashMap<>();
			for (int i = 0; i < gameNames.size(); i++)
				gameIndex.put(gameNames.get(i), i);

			final boolean[] gameHasHeuristics = new boolean[gameNames.size()];
			boolean anyHeuristicGame = false;
			for (int i = 0; i < gameNames.size(); i++)
			{
				final boolean h = hasHeuristics(gameNames.get(i));
				gameHasHeuristics[i] = h;
				anyHeuristicGame |= h;
			}

			final CoverageByDiversity coverage = new CoverageByDiversity(featureSpace, gameNames, gameIndex, existing, anyHeuristicGame);
			final MethodPairingState pairingState = new MethodPairingState();

			int guard = 0;
			while (out.size() < numTests && guard++ < numTests * 200)
			{
				FullCandidate best = null;
				double bestGain = Double.NEGATIVE_INFINITY;

				for (int gi = 0; gi < gameNames.size(); gi++)
				{
					final String game = gameNames.get(gi);
					final boolean h = gameHasHeuristics[gi];

					final PickedMethod sel = coverage.pickBestMethodForGame(Component.SELECTION, gi, h);
					final PickedMethod sim = coverage.pickBestMethodForGame(Component.SIMULATION, gi, h);
					final PickedMethod back = coverage.pickBestMethodForGame(Component.BACKPROP, gi, h);
					final PickedMethod fin = coverage.pickBestMethodForGame(Component.FINAL_MOVE, gi, h);
					if (sel == null || sim == null || back == null || fin == null)
						continue;

					final double diversityGain = sel.gain + sim.gain + back.gain + fin.gain;
					final int globalCount = globalGameCounts.getOrDefault(game, 0);
					final Config candidateVariant = new Config(sel.method, sim.method, back.method, fin.method);
					final double pairingPenalty = pairingState.pairingPenalty(candidateVariant);
					final double gain = diversityGain - 0.05 * globalCount - 0.1 * pairingPenalty;
					if (gain <= bestGain)
						continue;

					final String key = testKeyFullCombo(game, sel.method, sim.method, back.method, fin.method);
					if (existing.testKeys.contains(key))
						continue;

					bestGain = gain;
					best = new FullCandidate(gi, sel, sim, back, fin, gain);
				}

				if (best == null)
					break;

				final String game = gameNames.get(best.gameIndex);
				final Config variant = new Config(best.sel.method, best.sim.method, best.back.method, best.fin.method);
				final int requiresHeuristics = requiresHeuristics(variant) ? 1 : 0;
				if (requiresHeuristics == 1 && !gameHasHeuristics[best.gameIndex])
					continue;

				final TestSpec spec = new TestSpec(
						"T" + (out.size() + 1),
						game,
						Component.FULL,
						BASELINE,
						variant,
						gamesPerMatchup,
						moveTimeSeconds,
						maxMoves,
						requiresHeuristics
				);

				final String key = spec.key();
				if (existing.testKeys.contains(key))
					continue;

				out.add(spec);
				existing.recordPlanned(spec);
				coverage.record(Component.SELECTION, best.sel.method, best.gameIndex);
				coverage.record(Component.SIMULATION, best.sim.method, best.gameIndex);
				coverage.record(Component.BACKPROP, best.back.method, best.gameIndex);
				coverage.record(Component.FINAL_MOVE, best.fin.method, best.gameIndex);
				pairingState.record(variant);
				globalGameCounts.merge(game, 1, Integer::sum);
			}

			return out;
		}

		private static final class Candidate
		{
			final Component component;
			final String method;
			final int gameIndex;
			final double gain;
			Candidate(final Component component, final String method, final int gameIndex, final double gain)
			{
				this.component = component;
				this.method = method;
				this.gameIndex = gameIndex;
				this.gain = gain;
			}
		}

		private static final class FullCandidate
		{
			final int gameIndex;
			final PickedMethod sel;
			final PickedMethod sim;
			final PickedMethod back;
			final PickedMethod fin;
			final double gain;
			FullCandidate(
					final int gameIndex,
					final PickedMethod sel,
					final PickedMethod sim,
					final PickedMethod back,
					final PickedMethod fin,
					final double gain)
			{
				this.gameIndex = gameIndex;
				this.sel = sel;
				this.sim = sim;
				this.back = back;
				this.fin = fin;
				this.gain = gain;
			}
		}

		private boolean hasHeuristics(final String gameName)
		{
			final Boolean cached = heuristicCache.get(gameName);
			if (cached != null)
				return cached;

			final boolean result = HeuristicSupport.hasHeuristics(gameName);
			heuristicCache.put(gameName, result);
			return result;
		}
	}

	// -------------------- COVERAGE (DIVERSITY-BASED, GREEDY) --------------------

	static final class PickedMethod
	{
		final String method;
		final double gain;
		PickedMethod(final String method, final double gain)
		{
			this.method = method;
			this.gain = gain;
		}
	}

	/**
	 * Tracks how often pairs of methods from different components appear together.
	 * Used to penalize repeated pairings and encourage orthogonal designs.
	 */
	static final class MethodPairingState
	{
		private final Map<String, Integer> pairCounts = new HashMap<>();

		void record(final Config variant)
		{
			increment(Component.SELECTION, variant.selection, Component.SIMULATION, variant.simulation);
			increment(Component.SELECTION, variant.selection, Component.BACKPROP, variant.backprop);
			increment(Component.SELECTION, variant.selection, Component.FINAL_MOVE, variant.finalMove);
			increment(Component.SIMULATION, variant.simulation, Component.BACKPROP, variant.backprop);
			increment(Component.SIMULATION, variant.simulation, Component.FINAL_MOVE, variant.finalMove);
			increment(Component.BACKPROP, variant.backprop, Component.FINAL_MOVE, variant.finalMove);
		}

		double pairingPenalty(final Config variant)
		{
			return getCount(Component.SELECTION, variant.selection, Component.SIMULATION, variant.simulation)
				+ getCount(Component.SELECTION, variant.selection, Component.BACKPROP, variant.backprop)
				+ getCount(Component.SELECTION, variant.selection, Component.FINAL_MOVE, variant.finalMove)
				+ getCount(Component.SIMULATION, variant.simulation, Component.BACKPROP, variant.backprop)
				+ getCount(Component.SIMULATION, variant.simulation, Component.FINAL_MOVE, variant.finalMove)
				+ getCount(Component.BACKPROP, variant.backprop, Component.FINAL_MOVE, variant.finalMove);
		}

		private void increment(final Component c1, final String m1, final Component c2, final String m2)
		{
			pairCounts.merge(pairKey(c1, m1, c2, m2), 1, Integer::sum);
		}

		private int getCount(final Component c1, final String m1, final Component c2, final String m2)
		{
			return pairCounts.getOrDefault(pairKey(c1, m1, c2, m2), 0);
		}

		private static String pairKey(final Component c1, final String m1, final Component c2, final String m2)
		{
			return c1.name() + "|" + normalize(m1) + "|" + c2.name() + "|" + normalize(m2);
		}
	}

	static final class CoverageByDiversity
	{
		private final FeatureSpace featureSpace;
		private final List<String> gameNames;
		private final Map<String, Integer> gameIndex;
		private final boolean allowHeuristicRequiredSimulation;
		private final Map<String, MethodState> states = new HashMap<>();

		CoverageByDiversity(
				final FeatureSpace featureSpace,
				final List<String> gameNames,
				final Map<String, Integer> gameIndex,
				final ExistingTests existing,
				final boolean allowHeuristicRequiredSimulation)
		{
			this.featureSpace = featureSpace;
			this.gameNames = gameNames;
			this.gameIndex = gameIndex;
			this.allowHeuristicRequiredSimulation = allowHeuristicRequiredSimulation;

			for (final Component c : Arrays.asList(Component.SELECTION, Component.SIMULATION, Component.BACKPROP, Component.FINAL_MOVE))
			{
				for (final String method : domainFor(c))
				{
					final MethodState st = new MethodState(gameNames.size());
					final Set<String> used = existing.usedGamesFor(c, method);
					st.initFrom(used, gameIndex, gameNames, featureSpace);
					states.put(key(c, method), st);
				}
			}
		}

		static List<String> domainFor(final Component component)
		{
			switch (component)
			{
				case SELECTION:
					return Arrays.asList(SELECTION_POLICIES);
				case SIMULATION:
					return Arrays.asList(SIMULATION_POLICIES);
				case BACKPROP:
					return Arrays.asList(BACKPROP_POLICIES);
				case FINAL_MOVE:
					return Arrays.asList(FINAL_MOVE_POLICIES);
				default:
					return Collections.emptyList();
			}
		}

		boolean allowedByGlobalFeasibility(final Component component, final String method)
		{
			return !(component == Component.SIMULATION
					&& !allowHeuristicRequiredSimulation
					&& HEURISTIC_REQUIRED_SIM.contains(method));
		}

		MethodState state(final Component component, final String method)
		{
			return states.computeIfAbsent(key(component, method), k -> new MethodState(gameNames.size()));
		}

		void record(final Component component, final String method, final int gameIdx)
		{
			final MethodState st = state(component, method);
			st.addSelected(gameIdx, gameNames, featureSpace);
		}

		PickedMethod pickBestMethodForGame(final Component component, final int gameIdx, final boolean gameHasHeuristics)
		{
			double best = Double.NEGATIVE_INFINITY;
			String bestMethod = null;
			for (final String method : domainFor(component))
			{
				if (!allowedByGlobalFeasibility(component, method))
					continue;

				if (component == Component.SIMULATION && HEURISTIC_REQUIRED_SIM.contains(method) && !gameHasHeuristics)
					continue;

				final MethodState st = state(component, method);
				if (st.isSelected(gameIdx))
					continue;

				final double gain = st.currentGain(gameIdx);
				if (gain > best)
				{
					best = gain;
					bestMethod = method;
				}
			}
			return bestMethod == null ? null : new PickedMethod(bestMethod, best);
		}

		private static String key(final Component component, final String method)
		{
			return component.name() + "|" + normalize(method);
		}

		static final class MethodState
		{
			private final boolean[] selected;
			private final double[] minDist;

			MethodState(final int n)
			{
				this.selected = new boolean[n];
				this.minDist = new double[n];
				Arrays.fill(this.minDist, Double.POSITIVE_INFINITY);
			}

			boolean isSelected(final int idx)
			{
				return selected[idx];
			}

			double currentGain(final int idx)
			{
				return selected[idx] ? Double.NEGATIVE_INFINITY : minDist[idx];
			}

			void initFrom(
					final Set<String> initialSelected,
					final Map<String, Integer> gameIndex,
					final List<String> gameNames,
					final FeatureSpace featureSpace)
			{
				if (initialSelected == null || initialSelected.isEmpty())
				{
					// Large constant + centroid distance makes the first sample for a method count as real coverage.
					for (int i = 0; i < gameNames.size(); i++)
						minDist[i] = 1.0 + featureSpace.distanceFromCentroid(gameNames.get(i));
					return;
				}

				for (final String g : initialSelected)
				{
					final Integer idx = gameIndex.get(g);
					if (idx != null)
						selected[idx] = true;
				}

				for (int i = 0; i < gameNames.size(); i++)
				{
					if (selected[i])
					{
						minDist[i] = 0.0;
						continue;
					}
					double best = Double.POSITIVE_INFINITY;
					final String a = gameNames.get(i);
					for (final String s : initialSelected)
					{
						final Integer si = gameIndex.get(s);
						if (si == null)
							continue;
						best = Math.min(best, featureSpace.distance(a, s));
					}
					minDist[i] = best == Double.POSITIVE_INFINITY ? 0.0 : best;
				}
			}

			void addSelected(final int newIdx, final List<String> gameNames, final FeatureSpace featureSpace)
			{
				if (selected[newIdx])
					return;
				selected[newIdx] = true;
				minDist[newIdx] = 0.0;

				final String newGame = gameNames.get(newIdx);
				for (int i = 0; i < gameNames.size(); i++)
				{
					if (selected[i])
						continue;
					final double d = featureSpace.distance(newGame, gameNames.get(i));
					if (d < minDist[i])
						minDist[i] = d;
				}
			}
		}
	}

	private static String testKeyOneFactor(final String game, final Component component, final String method)
	{
		final Config variant = makeVariant(BASELINE, component, method);
		return normalize(game) + "|" + component.name() + "|" +
			normalize(BASELINE.selection) + "|" + normalize(BASELINE.simulation) + "|" + normalize(BASELINE.backprop) + "|" + normalize(BASELINE.finalMove) + "|" +
			normalize(variant.selection) + "|" + normalize(variant.simulation) + "|" + normalize(variant.backprop) + "|" + normalize(variant.finalMove);
	}

	private static String testKeyFullCombo(final String game, final String sel, final String sim, final String back, final String fin)
	{
		return normalize(game) + "|" + Component.FULL.name() + "|" +
			normalize(BASELINE.selection) + "|" + normalize(BASELINE.simulation) + "|" + normalize(BASELINE.backprop) + "|" + normalize(BASELINE.finalMove) + "|" +
			normalize(sel) + "|" + normalize(sim) + "|" + normalize(back) + "|" + normalize(fin);
	}

	private static Config makeVariant(final Config baseline, final Component component, final String value)
	{
		switch (component)
		{
			case SELECTION:
				return new Config(value, baseline.simulation, baseline.backprop, baseline.finalMove);
			case SIMULATION:
				return new Config(baseline.selection, value, baseline.backprop, baseline.finalMove);
			case BACKPROP:
				return new Config(baseline.selection, baseline.simulation, value, baseline.finalMove);
			case FINAL_MOVE:
				return new Config(baseline.selection, baseline.simulation, baseline.backprop, value);
			default:
				return baseline;
		}
	}

	private static boolean requiresHeuristics(final Config config)
	{
		return HEURISTIC_REQUIRED_SIM.contains(config.simulation);
	}

	// -------------------- FEATURE SPACE (GAME DIVERSITY) --------------------

	/**
	 * Converts GameCatalog rows into normalized feature vectors and provides distances.
	 * Used to select games that are as dissimilar as possible for a given method.
	 */
	static final class FeatureSpace
	{
		private final Map<String, double[]> scaled;
		private final double[] centroid;

		private FeatureSpace(final Map<String, double[]> scaled, final double[] centroid)
		{
			this.scaled = scaled;
			this.centroid = centroid;
		}

		static FeatureSpace from(final List<GameCatalog.Row> rows)
		{
			final Map<String, double[]> raw = new HashMap<>();
			for (final GameCatalog.Row r : rows)
				raw.put(r.gameName, toRawVector(r));

			final int dims = raw.values().iterator().next().length;
			final double[] min = new double[dims];
			final double[] max = new double[dims];
			Arrays.fill(min, Double.POSITIVE_INFINITY);
			Arrays.fill(max, Double.NEGATIVE_INFINITY);

			for (final double[] v : raw.values())
			{
				for (int i = 0; i < dims; i++)
				{
					min[i] = Math.min(min[i], v[i]);
					max[i] = Math.max(max[i], v[i]);
				}
			}

			final Map<String, double[]> scaled = new HashMap<>();
			final double[] centroid = new double[dims];
			for (final Map.Entry<String, double[]> e : raw.entrySet())
			{
				final double[] v = e.getValue();
				final double[] s = new double[dims];
				for (int i = 0; i < dims; i++)
				{
					final double denom = (max[i] - min[i]);
					final double val = denom == 0.0 ? 0.0 : (v[i] - min[i]) / denom;
					s[i] = val;
					centroid[i] += val;
				}
				scaled.put(e.getKey(), s);
			}

			final int n = scaled.size();
			for (int i = 0; i < dims; i++)
				centroid[i] = centroid[i] / Math.max(1, n);

			return new FeatureSpace(scaled, centroid);
		}

		double minDistanceToSet(final String gameName, final Set<String> others)
		{
			final double[] a = scaled.get(gameName);
			if (a == null || others.isEmpty())
				return 0.0;
			double best = Double.POSITIVE_INFINITY;
			for (final String o : others)
			{
				final double[] b = scaled.get(o);
				if (b == null)
					continue;
				best = Math.min(best, euclidean(a, b));
			}
			return best == Double.POSITIVE_INFINITY ? 0.0 : best;
		}

		double distance(final String gameA, final String gameB)
		{
			if (gameA == null || gameB == null)
				return 0.0;
			final double[] a = scaled.get(gameA);
			final double[] b = scaled.get(gameB);
			if (a == null || b == null)
				return 0.0;
			return euclidean(a, b);
		}

		double distanceFromCentroid(final String gameName)
		{
			final double[] a = scaled.get(gameName);
			if (a == null)
				return 0.0;
			return euclidean(a, centroid);
		}

		private static double euclidean(final double[] a, final double[] b)
		{
			double sum = 0.0;
			for (int i = 0; i < Math.min(a.length, b.length); i++)
			{
				final double d = a[i] - b[i];
				sum += d * d;
			}
			return Math.sqrt(sum);
		}

		private static double[] toRawVector(final GameCatalog.Row r)
		{
			// Apply a light log scaling to large counts to reduce domination by board size.
			return new double[] {
				r.numPlayers,
				log1p(r.numCells),
				log1p(r.numVertices),
				log1p(r.numEdges),
				log1p(r.numRows),
				log1p(r.numColumns),
				log1p(r.numCorners),
				log1p(r.numComponents),
				log1p(r.numPhases),
				log1p(r.numPlayableSites),
				r.avgNumDirections,
				r.avgNumOrthogonal,
				r.avgNumDiagonal,
				r.isStacking,
				r.isStochastic,
				r.isAlternating,
				r.hasHiddenInfo,
				r.requiresTeams,
				r.hasTrack,
				r.hasCard,
				r.hasHandDice,
				r.hasHeuristics,
				r.isVertexGame,
				r.isEdgeGame,
				r.isCellGame,
				r.isDeductionPuzzle
			};
		}

		private static double log1p(final int v)
		{
			return Math.log(1.0 + Math.max(0, v));
		}
	}

	// -------------------- HEURISTIC SUPPORT CHECK --------------------

	/**
	 * Heuristic availability check. Uses reflection to reduce coupling to specific Ludii metadata classes.
	 *
	 * Conservative behavior: if we cannot detect heuristics, returns false.
	 */
	static final class HeuristicSupport
	{
		static boolean hasHeuristics(final String gameName)
		{
			final Game game;
			try
			{
				game = GameLoader.loadGameFromName(gameName);
			}
			catch (final Throwable t)
			{
				return false;
			}

			if (game == null)
				return false;

			// Approach 1: try metadata.ai().heuristics() and inspect emptiness.
			try
			{
				final Object metadata = invokeNoArg(game, "metadata");
				final Object ai = invokeNoArg(metadata, "ai");
				final Object heuristics = invokeNoArg(ai, "heuristics");
				if (heuristics == null)
					return false;

				// Some versions wrap lists inside another object.
				final Object inner = invokeNoArg(heuristics, "heuristics");
				if (inner instanceof List)
					return !((List<?>) inner).isEmpty();

				if (heuristics instanceof List)
					return !((List<?>) heuristics).isEmpty();

				final Object isEmpty = invokeNoArg(heuristics, "isEmpty");
				if (isEmpty instanceof Boolean)
					return !((Boolean) isEmpty);

				final String s = heuristics.toString().toLowerCase(Locale.ROOT);
				return s.contains("heur") && !s.contains("[]");
			}
			catch (final Throwable ignored)
			{
				// fall through
			}

			return false;
		}

		private static Object invokeNoArg(final Object target, final String method)
		{
			if (target == null)
				return null;
			try
			{
				final Method m = target.getClass().getMethod(method);
				m.setAccessible(true);
				return m.invoke(target);
			}
			catch (final Throwable t)
			{
				return null;
			}
		}
	}

	// -------------------- EXISTING TESTS INPUT --------------------

	static final class ExistingTests
	{
		final Set<String> testKeys = new HashSet<>();
		final Map<String, Integer> gameCounts = new HashMap<>();
		final Map<String, Integer> selectionCounts = initDomain(SELECTION_POLICIES);
		final Map<String, Integer> simulationCounts = initDomain(SIMULATION_POLICIES);
		final Map<String, Integer> backpropCounts = initDomain(BACKPROP_POLICIES);
		final Map<String, Integer> finalMoveCounts = initDomain(FINAL_MOVE_POLICIES);
		final Map<Component, Map<String, Set<String>>> usedGamesByMethod = initUsedGames();

		static ExistingTests loadAll(final List<Path> paths) throws IOException
		{
			final ExistingTests out = new ExistingTests();
			for (final Path p : paths)
				out.load(p);
			return out;
		}

		private void load(final Path path) throws IOException
		{
			if (path == null || !Files.exists(path))
				return;

			try (BufferedReader br = Files.newBufferedReader(path, StandardCharsets.UTF_8))
			{
				final String headerLine = br.readLine();
				if (headerLine == null)
					return;

				final List<String> header = Csv.parseLine(headerLine);
				final Map<String, Integer> idx = index(header);

				String line;
				while ((line = br.readLine()) != null)
				{
					line = line.trim();
					if (line.isEmpty() || line.startsWith("#"))
						continue;

					final List<String> fields = Csv.parseLine(line);
					final String game = get(fields, idx, "gameName");
					final String component = get(fields, idx, "component");
					final String vSel = get(fields, idx, "variantSelection");
					final String vSim = get(fields, idx, "variantSimulation");
					final String vBack = get(fields, idx, "variantBackprop");
					final String vFin = get(fields, idx, "variantFinalMove");
					final String bSel = get(fields, idx, "baselineSelection");
					final String bSim = get(fields, idx, "baselineSimulation");
					final String bBack = get(fields, idx, "baselineBackprop");
					final String bFin = get(fields, idx, "baselineFinalMove");

					final TestSpec tmp = new TestSpec(
							"",
							game,
							parseComponent(component),
							new Config(bSel, bSim, bBack, bFin),
							new Config(vSel, vSim, vBack, vFin),
							0,
							0.0,
							0,
							0
					);
					testKeys.add(tmp.key());
					gameCounts.merge(game, 1, Integer::sum);

					// For coverage, count the *variant* methods (what we are choosing).
					if (!isBlank(vSel)) selectionCounts.merge(normalize(vSel), 1, Integer::sum);
					if (!isBlank(vSim)) simulationCounts.merge(normalize(vSim), 1, Integer::sum);
					if (!isBlank(vBack)) backpropCounts.merge(normalize(vBack), 1, Integer::sum);
					if (!isBlank(vFin)) finalMoveCounts.merge(normalize(vFin), 1, Integer::sum);

					// Track which games have been used for which method (per component) to drive diversity.
					if (!isBlank(vSel)) usedGamesByMethod.get(Component.SELECTION).get(normalize(vSel)).add(game);
					if (!isBlank(vSim)) usedGamesByMethod.get(Component.SIMULATION).get(normalize(vSim)).add(game);
					if (!isBlank(vBack)) usedGamesByMethod.get(Component.BACKPROP).get(normalize(vBack)).add(game);
					if (!isBlank(vFin)) usedGamesByMethod.get(Component.FINAL_MOVE).get(normalize(vFin)).add(game);
				}
			}
		}

		void recordPlanned(final TestSpec spec)
		{
			// Treat planned tests as existing for the remainder of this run (prevents duplicates within one run).
			testKeys.add(spec.key());

			// Update the diversity state as we build the plan so later selections spread out.
			final String game = spec.gameName;
			if (!isBlank(spec.variant.selection)) usedGamesByMethod.get(Component.SELECTION).get(normalize(spec.variant.selection)).add(game);
			if (!isBlank(spec.variant.simulation)) usedGamesByMethod.get(Component.SIMULATION).get(normalize(spec.variant.simulation)).add(game);
			if (!isBlank(spec.variant.backprop)) usedGamesByMethod.get(Component.BACKPROP).get(normalize(spec.variant.backprop)).add(game);
			if (!isBlank(spec.variant.finalMove)) usedGamesByMethod.get(Component.FINAL_MOVE).get(normalize(spec.variant.finalMove)).add(game);

			// Keep counts in sync too (useful if other tooling depends on ExistingTests stats).
			gameCounts.merge(game, 1, Integer::sum);
			if (!isBlank(spec.variant.selection)) selectionCounts.merge(normalize(spec.variant.selection), 1, Integer::sum);
			if (!isBlank(spec.variant.simulation)) simulationCounts.merge(normalize(spec.variant.simulation), 1, Integer::sum);
			if (!isBlank(spec.variant.backprop)) backpropCounts.merge(normalize(spec.variant.backprop), 1, Integer::sum);
			if (!isBlank(spec.variant.finalMove)) finalMoveCounts.merge(normalize(spec.variant.finalMove), 1, Integer::sum);
		}

		Set<String> usedGamesFor(final Component component, final String method)
		{
			final Map<String, Set<String>> byMethod = usedGamesByMethod.get(component);
			if (byMethod == null)
				return Collections.emptySet();
			final Set<String> s = byMethod.get(normalize(method));
			return s == null ? Collections.emptySet() : s;
		}

		Set<String> usedGamesUnion()
		{
			final Set<String> out = new HashSet<>();
			for (final Map<String, Set<String>> byMethod : usedGamesByMethod.values())
				for (final Set<String> g : byMethod.values())
					out.addAll(g);
			return out;
		}

		private static Component parseComponent(final String s)
		{
			final String v = normalize(s);
			if ("selection".equals(v)) return Component.SELECTION;
			if ("simulation".equals(v)) return Component.SIMULATION;
			if ("backprop".equals(v)) return Component.BACKPROP;
			if ("final_move".equals(v) || "finalmove".equals(v) || "finalmove".equals(v.replace("_", ""))) return Component.FINAL_MOVE;
			if ("full".equals(v)) return Component.FULL;
			return Component.FULL;
		}

		private static Map<String, Integer> initDomain(final String[] values)
		{
			final Map<String, Integer> map = new HashMap<>();
			for (final String v : values)
				map.put(normalize(v), 0);
			return map;
		}

		private static Map<Component, Map<String, Set<String>>> initUsedGames()
		{
			final Map<Component, Map<String, Set<String>>> map = new HashMap<>();
			map.put(Component.SELECTION, initUsedGamesDomain(SELECTION_POLICIES));
			map.put(Component.SIMULATION, initUsedGamesDomain(SIMULATION_POLICIES));
			map.put(Component.BACKPROP, initUsedGamesDomain(BACKPROP_POLICIES));
			map.put(Component.FINAL_MOVE, initUsedGamesDomain(FINAL_MOVE_POLICIES));
			return map;
		}

		private static Map<String, Set<String>> initUsedGamesDomain(final String[] values)
		{
			final Map<String, Set<String>> map = new HashMap<>();
			for (final String v : values)
				map.put(normalize(v), new HashSet<>());
			return map;
		}
	}

	// -------------------- OUTPUT --------------------

	private static void writePlanCsv(final List<TestSpec> tests, final Path out) throws IOException
	{
		final List<String> header = Arrays.asList(
				"testId",
				"gameName",
				"component",
				"variantSelection",
				"variantSimulation",
				"variantBackprop",
				"variantFinalMove",
				"baselineSelection",
				"baselineSimulation",
				"baselineBackprop",
				"baselineFinalMove",
				"moveTimeSeconds",
				"gamesPerMatchup",
				"maxMoves",
				"requiresHeuristics"
		);

		try (BufferedWriter bw = Files.newBufferedWriter(out, StandardCharsets.UTF_8))
		{
			bw.write(Csv.toLine(header));
			bw.newLine();

			for (final TestSpec t : tests)
			{
				final List<String> row = Arrays.asList(
					t.testId,
					t.gameName,
					t.component.name(),
					t.variant.selection,
					t.variant.simulation,
					t.variant.backprop,
					t.variant.finalMove,
					t.baseline.selection,
					t.baseline.simulation,
					t.baseline.backprop,
					t.baseline.finalMove,
					Double.toString(t.moveTimeSeconds),
					Integer.toString(t.gamesPerMatchup),
					Integer.toString(t.maxMoves),
					Integer.toString(t.requiresHeuristics)
				);
				bw.write(Csv.toLine(row));
				bw.newLine();
			}
		}
	}

	// -------------------- ARGS --------------------

	static final class Args
	{
		final int numTests;
		final int gamesPerMatchup;
		final double moveTimeSeconds;
		final int maxMoves;
		final boolean requireTwoPlayer;
		final Design design;
		final Path outPath;
		final Path catalogPath;
		final List<Path> existingPaths;
		final long seed;

		private Args(
				final int numTests,
				final int gamesPerMatchup,
				final double moveTimeSeconds,
				final int maxMoves,
				final boolean requireTwoPlayer,
				final Design design,
				final Path outPath,
				final Path catalogPath,
				final List<Path> existingPaths,
				final long seed)
		{
			this.numTests = numTests;
			this.gamesPerMatchup = gamesPerMatchup;
			this.moveTimeSeconds = moveTimeSeconds;
			this.maxMoves = maxMoves;
			this.requireTwoPlayer = requireTwoPlayer;
			this.design = design;
			this.outPath = outPath;
			this.catalogPath = catalogPath;
			this.existingPaths = existingPaths;
			this.seed = seed;
		}

		static Args parse(final String[] args)
		{
			int numTests = 200;
			int gamesPerMatchup = 10;
			double moveTimeSeconds = 0.1;
			int maxMoves = 500;
			boolean requireTwoPlayer = true;
			Design design = Design.ONE_FACTOR;
			Path out = Paths.get("planned_tests.csv");
			Path catalog = null;
			final List<Path> existing = new ArrayList<>();
			long seed = 42;

			for (int i = 0; i < args.length; i++)
			{
				final String a = args[i];
				if ("--num-tests".equalsIgnoreCase(a) && i + 1 < args.length)
					numTests = Integer.parseInt(args[++i]);
				else if ("--length".equalsIgnoreCase(a) && i + 1 < args.length)
					gamesPerMatchup = Integer.parseInt(args[++i]);
				else if ("--games-per-matchup".equalsIgnoreCase(a) && i + 1 < args.length)
					gamesPerMatchup = Integer.parseInt(args[++i]);
				else if ("--move-time".equalsIgnoreCase(a) && i + 1 < args.length)
					moveTimeSeconds = Double.parseDouble(args[++i]);
				else if ("--max-moves".equalsIgnoreCase(a) && i + 1 < args.length)
					maxMoves = Integer.parseInt(args[++i]);
				else if ("--out".equalsIgnoreCase(a) && i + 1 < args.length)
					out = Paths.get(args[++i]);
				else if ("--catalog".equalsIgnoreCase(a) && i + 1 < args.length)
					catalog = Paths.get(args[++i]);
				else if ("--existing".equalsIgnoreCase(a) && i + 1 < args.length)
					existing.add(Paths.get(args[++i]));
				else if ("--seed".equalsIgnoreCase(a) && i + 1 < args.length)
					seed = Long.parseLong(args[++i]);
				else if ("--allow-non-two-player".equalsIgnoreCase(a))
					requireTwoPlayer = false;
				else if ("--design".equalsIgnoreCase(a) && i + 1 < args.length)
				{
					final String v = args[++i];
					if ("full".equalsIgnoreCase(v) || "fullcombo".equalsIgnoreCase(v))
						design = Design.FULL_COMBO;
					else
						design = Design.ONE_FACTOR;
				}
			}

			if (numTests <= 0)
				throw new IllegalArgumentException("--num-tests must be > 0");
			if (gamesPerMatchup <= 0)
				throw new IllegalArgumentException("--games-per-matchup must be > 0");
			if (moveTimeSeconds <= 0)
				throw new IllegalArgumentException("--move-time must be > 0");
			if (maxMoves <= 0)
				throw new IllegalArgumentException("--max-moves must be > 0");

			return new Args(
					numTests,
					gamesPerMatchup,
					moveTimeSeconds,
					maxMoves,
					requireTwoPlayer,
					design,
					out,
					catalog,
					existing,
					seed
			);
		}
	}

	// -------------------- CSV HELPERS --------------------

	static final class Csv
	{
		static String toLine(final List<String> fields)
		{
			return fields.stream().map(Csv::escape).collect(Collectors.joining(","));
		}

		static String escape(final String raw)
		{
			final String s = raw == null ? "" : raw;
			final String escaped = s.replace("\"", "\"\"");
			return "\"" + escaped + "\"";
		}

		static List<String> parseLine(final String line)
		{
			final List<String> out = new ArrayList<>();
			if (line == null)
				return out;

			final StringBuilder current = new StringBuilder();
			boolean inQuotes = false;
			for (int i = 0; i < line.length(); i++)
			{
				final char ch = line.charAt(i);
				if (inQuotes)
				{
					if (ch == '"')
					{
						final boolean nextIsQuote = (i + 1 < line.length()) && (line.charAt(i + 1) == '"');
						if (nextIsQuote)
						{
							current.append('"');
							i++;
						}
						else
						{
							inQuotes = false;
						}
					}
					else
					{
						current.append(ch);
					}
				}
				else
				{
					if (ch == '"')
					{
						inQuotes = true;
					}
					else if (ch == ',')
					{
						out.add(current.toString());
						current.setLength(0);
					}
					else
					{
						current.append(ch);
					}
				}
			}
			out.add(current.toString());
			return out;
		}
	}

	private static Map<String, Integer> index(final List<String> header)
	{
		final Map<String, Integer> map = new HashMap<>();
		for (int i = 0; i < header.size(); i++)
			map.put(normalize(header.get(i)), i);
		return map;
	}

	private static String get(final List<String> fields, final Map<String, Integer> idx, final String col)
	{
		final Integer i = idx.get(normalize(col));
		if (i == null || i < 0 || i >= fields.size())
			return "";
		return fields.get(i);
	}

	private static boolean isBlank(final String s)
	{
		return s == null || s.trim().isEmpty();
	}

	private static String normalize(final String s)
	{
		return s == null ? "" : s.trim().toLowerCase(Locale.ROOT);
	}
}
