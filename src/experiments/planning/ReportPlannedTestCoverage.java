package experiments.planning;

import java.io.BufferedReader;
import java.io.IOException;
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
import java.util.Set;
import java.util.stream.Collectors;

/**
 * Quick CLI to summarize "coverage" of a planned test CSV produced by {@link GenerateTestPlan}.
 *
 * It prints:
 * - How many tests and unique games are covered.
 * - How many tests vary each component (ONE_FACTOR vs FULL).
 * - Per-component method coverage (how many distinct methods appeared as variants).
 * - Top games by number of planned tests.
 *
 * This does not run any experiments; it only reads the CSV.
 */
public final class ReportPlannedTestCoverage
{
	// Keep in sync with GenerateTestPlan's policy lists.
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

	private ReportPlannedTestCoverage()
	{
		// utility
	}

	public static void main(final String[] args) throws Exception
	{
		final Path in = parseIn(args);
		final CoverageStats stats = analyze(in);
		print(stats);
	}

	private static Path parseIn(final String[] args)
	{
		if (args == null || args.length == 0)
			return Paths.get("planned_tests.csv");

		for (int i = 0; i < args.length; i++)
		{
			final String a = args[i];
			if ("--in".equalsIgnoreCase(a) && i + 1 < args.length)
				return Paths.get(args[++i]);
			if (!a.startsWith("--"))
				return Paths.get(a);
		}
		return Paths.get("planned_tests.csv");
	}

	private static CoverageStats analyze(final Path in) throws IOException
	{
		final CoverageStats stats = new CoverageStats();

		try (BufferedReader br = Files.newBufferedReader(in, StandardCharsets.UTF_8))
		{
			final String headerLine = br.readLine();
			if (headerLine == null)
				throw new IOException("Empty file: " + in);

			final List<String> header = Csv.parseLine(headerLine);
			final Map<String, Integer> idx = index(header);

			String line;
			while ((line = br.readLine()) != null)
			{
				line = line.trim();
				if (line.isEmpty())
					continue;

				final List<String> fields = Csv.parseLine(line);
				final String gameName = field(fields, idx, "gameName");
				final String component = field(fields, idx, "component");
				final String vSel = field(fields, idx, "variantSelection");
				final String vSim = field(fields, idx, "variantSimulation");
				final String vBack = field(fields, idx, "variantBackprop");
				final String vFinal = field(fields, idx, "variantFinalMove");

				stats.tests++;
				if (!gameName.isEmpty())
				{
					stats.uniqueGames.add(gameName);
					stats.testsPerGame.merge(gameName, 1, Integer::sum);
				}

				stats.testsPerComponent.merge(componentOrUnknown(component), 1, Integer::sum);

				// Variant-coverage is based on what actually appears in variant columns.
				stats.overallVariantCoverage.selection.add(norm(vSel));
				stats.overallVariantCoverage.simulation.add(norm(vSim));
				stats.overallVariantCoverage.backprop.add(norm(vBack));
				stats.overallVariantCoverage.finalMove.add(norm(vFinal));

				// Component-specific counts: for ONE_FACTOR only count the varied component;
				// for FULL tests count all variant columns.
				switch (componentOrUnknown(component))
				{
					case "SELECTION":
						stats.variantCounts.selection.merge(norm(vSel), 1, Integer::sum);
						break;
					case "SIMULATION":
						stats.variantCounts.simulation.merge(norm(vSim), 1, Integer::sum);
						break;
					case "BACKPROP":
						stats.variantCounts.backprop.merge(norm(vBack), 1, Integer::sum);
						break;
					case "FINAL_MOVE":
						stats.variantCounts.finalMove.merge(norm(vFinal), 1, Integer::sum);
						break;
					case "FULL":
						stats.variantCounts.selection.merge(norm(vSel), 1, Integer::sum);
						stats.variantCounts.simulation.merge(norm(vSim), 1, Integer::sum);
						stats.variantCounts.backprop.merge(norm(vBack), 1, Integer::sum);
						stats.variantCounts.finalMove.merge(norm(vFinal), 1, Integer::sum);
						break;
					default:
						// Unknown: treat as FULL so we don't undercount.
						stats.variantCounts.selection.merge(norm(vSel), 1, Integer::sum);
						stats.variantCounts.simulation.merge(norm(vSim), 1, Integer::sum);
						stats.variantCounts.backprop.merge(norm(vBack), 1, Integer::sum);
						stats.variantCounts.finalMove.merge(norm(vFinal), 1, Integer::sum);
						break;
				}
			}
		}

		return stats;
	}

	private static void print(final CoverageStats stats)
	{
		System.out.println("Planned test coverage summary");
		System.out.println("- Tests: " + stats.tests);
		System.out.println("- Unique games: " + stats.uniqueGames.size());

		if (!stats.testsPerGame.isEmpty())
		{
			final List<Integer> counts = new ArrayList<>(stats.testsPerGame.values());
			counts.sort(Comparator.naturalOrder());
			final int min = counts.get(0);
			final int max = counts.get(counts.size() - 1);
			final double avg = counts.stream().mapToInt(Integer::intValue).average().orElse(0.0);
			System.out.println(String.format(Locale.ROOT, "- Tests/game: min=%d avg=%.2f max=%d", min, avg, max));
		}

		System.out.println("\nTests by component:");
		stats.testsPerComponent.entrySet().stream()
				.sorted(Map.Entry.comparingByKey())
				.forEach(e -> System.out.println("- " + e.getKey() + ": " + e.getValue()));

		System.out.println("\nVariant method coverage (unique methods that appear as variants):");
		printCoverageLine("Selection", stats.overallVariantCoverage.selection, SELECTION_POLICIES);
		printCoverageLine("Simulation", stats.overallVariantCoverage.simulation, SIMULATION_POLICIES);
		printCoverageLine("Backprop", stats.overallVariantCoverage.backprop, BACKPROP_POLICIES);
		printCoverageLine("FinalMove", stats.overallVariantCoverage.finalMove, FINAL_MOVE_POLICIES);

		System.out.println("\nTop games by number of planned tests:");
		stats.testsPerGame.entrySet().stream()
				.sorted((a, b) -> Integer.compare(b.getValue(), a.getValue()))
				.limit(15)
				.forEach(e -> System.out.println("- " + e.getKey() + ": " + e.getValue()));

		System.out.println("\nTop variant methods per component (within tests where that component varied):");
		printTop("Selection", stats.variantCounts.selection);
		printTop("Simulation", stats.variantCounts.simulation);
		printTop("Backprop", stats.variantCounts.backprop);
		printTop("FinalMove", stats.variantCounts.finalMove);
	}

	private static void printCoverageLine(final String label, final Set<String> seenNorm, final String[] universe)
	{
		final Set<String> universeNorm = Arrays.stream(universe).map(ReportPlannedTestCoverage::norm).collect(Collectors.toSet());
		final Set<String> seenInUniverse = new HashSet<>(seenNorm);
		seenInUniverse.retainAll(universeNorm);

		System.out.println(String.format(
				Locale.ROOT,
				"- %s: %d/%d (%.1f%%)",
				label,
				seenInUniverse.size(),
				universeNorm.size(),
				(universeNorm.isEmpty() ? 0.0 : (100.0 * seenInUniverse.size() / universeNorm.size()))
		));

		final Set<String> missing = new HashSet<>(universeNorm);
		missing.removeAll(seenNorm);
		if (!missing.isEmpty())
			System.out.println("  Missing: " + summarizeSet(missing, 10));
	}

	private static void printTop(final String label, final Map<String, Integer> counts)
	{
		final List<Map.Entry<String, Integer>> top = counts.entrySet().stream()
				.filter(e -> !e.getKey().isEmpty())
				.sorted((a, b) -> Integer.compare(b.getValue(), a.getValue()))
				.limit(8)
				.collect(Collectors.toList());

		if (top.isEmpty())
		{
			System.out.println("- " + label + ": (no data)");
			return;
		}

		final String joined = top.stream()
				.map(e -> e.getKey() + "=" + e.getValue())
				.collect(Collectors.joining(", "));
		System.out.println("- " + label + ": " + joined);
	}

	private static String summarizeSet(final Set<String> set, final int limit)
	{
		final List<String> sorted = new ArrayList<>(set);
		sorted.sort(String::compareTo);
		if (sorted.size() <= limit)
			return sorted.toString();
		return sorted.subList(0, limit) + " ... (+" + (sorted.size() - limit) + " more)";
	}

	private static String componentOrUnknown(final String raw)
	{
		final String s = raw == null ? "" : raw.trim();
		if (s.isEmpty())
			return "UNKNOWN";
		return s;
	}

	private static String norm(final String s)
	{
		return s == null ? "" : s.trim().toLowerCase(Locale.ROOT);
	}

	private static Map<String, Integer> index(final List<String> header)
	{
		final Map<String, Integer> map = new HashMap<>();
		for (int i = 0; i < header.size(); i++)
			map.put(norm(header.get(i)), i);
		return map;
	}

	private static String field(final List<String> fields, final Map<String, Integer> idx, final String col)
	{
		final Integer i = idx.get(norm(col));
		if (i == null || i < 0 || i >= fields.size())
			return "";
		return fields.get(i);
	}

	/** Minimal CSV helper (quotes + commas supported). */
	static final class Csv
	{
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

	private static final class CoverageStats
	{
		int tests = 0;
		final Set<String> uniqueGames = new HashSet<>();
		final Map<String, Integer> testsPerGame = new HashMap<>();
		final Map<String, Integer> testsPerComponent = new HashMap<>();

		final VariantCoverage overallVariantCoverage = new VariantCoverage();
		final VariantCounts variantCounts = new VariantCounts();
	}

	private static final class VariantCoverage
	{
		final Set<String> selection = new HashSet<>();
		final Set<String> simulation = new HashSet<>();
		final Set<String> backprop = new HashSet<>();
		final Set<String> finalMove = new HashSet<>();
	}

	private static final class VariantCounts
	{
		final Map<String, Integer> selection = new HashMap<>();
		final Map<String, Integer> simulation = new HashMap<>();
		final Map<String, Integer> backprop = new HashMap<>();
		final Map<String, Integer> finalMove = new HashMap<>();
	}
}
