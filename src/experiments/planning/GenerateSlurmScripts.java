package experiments.planning;

import experiments.catalog.GameCatalog;

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
 * Generates SLURM sbatch scripts (like your basic_test.sh) for every row in a planned test CSV.
 *
 * Resource calculation is deterministic and based on:
 * - planned meta parameters (moveTimeSeconds, gamesPerMatchup, maxMoves)
 * - the chosen methods (variant policies)
 * - game properties from the catalog (e.g., numPlayableSites, stacking, hidden-info)
 */
public final class GenerateSlurmScripts
{
	private GenerateSlurmScripts()
	{
		// utility
	}

	public static void main(final String[] args) throws Exception
	{
		final Args parsed = Args.parse(args);

		final GameCatalog.Table catalog = GameCatalog.load(parsed.catalogPath);
		final Map<String, GameCatalog.Row> byName = new HashMap<>();
		for (final GameCatalog.Row r : catalog.rows())
			byName.put(r.gameName, r);

		final List<PlannedTest> tests = PlannedTest.loadAll(parsed.planPath);
		Files.createDirectories(parsed.outDir);

		final String submitAll = "submit_all.sh";
		final Path submitAllPath = parsed.outDir.resolve(submitAll);
		try (BufferedWriter submit = Files.newBufferedWriter(submitAllPath, StandardCharsets.UTF_8))
		{
			submit.write("#!/bin/bash\nset -euo pipefail\n");

			for (final PlannedTest t : tests)
			{
				final GameCatalog.Row row = byName.get(t.gameName);
				if (row == null)
				{
					System.err.println("Skipping (no catalog row): " + t.testId + " -> " + t.gameName);
					continue;
				}

				final Resources res = ResourceEstimator.estimate(t, row, parsed);
				final Path scriptPath = parsed.outDir.resolve("test_" + safeFile(t.testId) + ".sh");
				writeOneScript(scriptPath, t, res, parsed);
				submit.write("sbatch \"" + scriptPath.toAbsolutePath().toString() + "\"\n");
			}
		}

		try
		{
			// Best effort make executable bit when run on Linux; harmless on Windows.
			submitAllPath.toFile().setExecutable(true);
		}
		catch (final Throwable ignored)
		{
			// ignore
		}

		System.out.println("Wrote SLURM scripts to: " + parsed.outDir.toAbsolutePath());
		System.out.println("Submit-all helper: " + submitAllPath.toAbsolutePath());
	}

	private static void writeOneScript(final Path out, final PlannedTest t, final Resources res, final Args parsed) throws IOException
	{
		try (BufferedWriter bw = Files.newBufferedWriter(out, StandardCharsets.UTF_8))
		{
			bw.write("#!/bin/bash\n");
			bw.write("#\n");
			bw.write("#SBATCH --job-name=" + parsed.jobPrefix + safeSlurm(t.testId) + "\n");
			bw.write("#SBATCH --output=" + parsed.resultsDir + "/" + parsed.logPrefix + safeSlurm(t.testId) + "_%j.out\n");
			bw.write("#SBATCH --error=" + parsed.resultsDir + "/" + parsed.logPrefix + safeSlurm(t.testId) + "_%j.err\n");
			bw.write("#\n");
			bw.write("#SBATCH --ntasks=1\n");
			bw.write("#SBATCH --cpus-per-task=" + res.cpus + "\n");
			bw.write("#SBATCH --mem=" + res.mem + "\n");
			bw.write("#SBATCH --time=" + res.time + "\n\n");

			if (parsed.moduleLoad != null && !parsed.moduleLoad.trim().isEmpty())
				bw.write("module load " + parsed.moduleLoad + "\n\n");

		bw.write("SCRIPT_DIR=\"$( cd \"$( dirname \"${BASH_SOURCE[0]}\" )\" && pwd )\"\n");
		bw.write("PROJECT_DIR=\"" + parsed.projectDir + "\"\n");
		bw.write("LUDII_JAR=\"" + parsed.ludiiJar + "\"\n");
		bw.write("CLASSPATH=\"${LUDII_JAR}:${PROJECT_DIR}/bin\"\n\n");

		bw.write("PLAN=\"" + parsed.planInProjectDir + "\"\n");
		bw.write("OUT_DIR=\"" + parsed.resultsDir + "\"\n");
		bw.write("mkdir -p \"${OUT_DIR}\"\n\n");
			bw.write("echo \"Running " + t.testId + " on $(hostname) at $(date)\"\n");
			bw.write("echo \"Game: " + escapeForEcho(t.gameName) + "\"\n");
			bw.write("echo \"Variant: " + escapeForEcho(t.variantSelection) + " | " + escapeForEcho(t.variantSimulation) + " | " + escapeForEcho(t.variantBackprop) + " | " + escapeForEcho(t.variantFinalMove) + "\"\n");
			bw.write("echo \"Meta: moveTime=" + t.moveTimeSeconds + ", gamesPerMatchup=" + t.gamesPerMatchup + ", maxMoves=" + t.maxMoves + "\"\n");
			bw.write("echo \"Estimated: cpus=" + res.cpus + ", mem=" + res.mem + ", time=" + res.time + "\"\n\n");

			bw.write("srun java -cp \"${CLASSPATH}\" " + parsed.runnerClass + " ");
			bw.write("--plan \"${PLAN}\" --test-id \"" + safeSlurm(t.testId) + "\" ");
			bw.write("--out \"${OUT_DIR}/" + safeFile(t.testId) + ".csv\"\n\n");

			bw.write("echo \"Job completed at $(date)\"\n");
		}

		try
		{
			out.toFile().setExecutable(true);
		}
		catch (final Throwable ignored)
		{
			// ignore
		}
	}

	private static String escapeForEcho(final String s)
	{
		if (s == null)
			return "";
		return s.replace("\"", "'");
	}

	private static String safeSlurm(final String s)
	{
		return s == null ? "" : s.replaceAll("[^A-Za-z0-9_\\-]", "_");
	}

	private static String safeFile(final String s)
	{
		return safeSlurm(s);
	}

	// -------------------- RESOURCE ESTIMATION --------------------

	static final class Resources
	{
		final int cpus;
		final String mem;  // SLURM format (e.g. 6G)
		final String time; // HH:MM:SS

		Resources(final int cpus, final String mem, final String time)
		{
			this.cpus = cpus;
			this.mem = mem;
			this.time = time;
		}
	}

	static final class ResourceEstimator
	{
		static Resources estimate(final PlannedTest t, final GameCatalog.Row g, final Args parsed)
		{
			final int cpus = estimateCpus(t, g, parsed);
			final String mem = estimateMem(t, g, parsed);
			final String time = estimateTime(t, g, parsed);
			return new Resources(cpus, mem, time);
		}

		private static int estimateCpus(final PlannedTest t, final GameCatalog.Row g, final Args parsed)
		{
			// Deterministic rule: start from a user-provided base (defaults to what you used in basic_test.sh).
			int cpus = parsed.baseCpus;

			// Slight bump for very large state spaces to reduce scheduling starvation.
			if (g.numPlayableSites >= 200)
				cpus = Math.max(cpus, parsed.baseCpus + 1);
			if (g.isStacking == 1)
				cpus = Math.max(cpus, parsed.baseCpus + 1);

			return Math.max(1, Math.min(parsed.maxCpus, cpus));
		}

		private static String estimateMem(final PlannedTest t, final GameCatalog.Row g, final Args parsed)
		{
			// Compute in MB then format to G. Uses only catalog/game + test meta.
			final int baseMb = parsed.baseMemMb;
			int mb = baseMb;

			mb += (int) Math.round(parsed.memMbPerPlayableSite * Math.max(0, g.numPlayableSites));
			mb += (int) Math.round(parsed.memMbPerComponent * Math.max(0, g.numComponents));
			mb += (g.hasHiddenInfo == 1 ? parsed.hiddenInfoMemMb : 0);
			mb += (t.requiresHeuristics == 1 ? parsed.heuristicsMemMb : 0);

			mb = Math.max(baseMb, Math.min(mb, parsed.maxMemMb));
			final int gb = (int) Math.ceil(mb / 1024.0);
			return gb + "G";
		}

		private static String estimateTime(final PlannedTest t, final GameCatalog.Row g, final Args parsed)
		{
			// WORST-CASE time estimation:
			// - Each move can take up to moveTimeSeconds (the MCTS thinking budget)
			// - Both players make moves, so total moves per game = maxMoves * 2
			// - We assume all games go to maxMoves (worst case, no early termination)
			final double movesPerGame = t.maxMoves * 2.0; // both players
			final double searchSeconds = (double) t.gamesPerMatchup * movesPerGame * t.moveTimeSeconds;

			double overheadSeconds = parsed.baseOverheadSeconds;
			overheadSeconds += parsed.overheadSecondsPerPlayableSite * Math.max(0, g.numPlayableSites);
			overheadSeconds += parsed.overheadSecondsPerComponent * Math.max(0, g.numComponents);
			if (t.requiresHeuristics == 1)
				overheadSeconds += parsed.heuristicsOverheadSeconds;

			// Method-dependent deterministic overhead (small, but makes the function depend on methods as requested).
			overheadSeconds += parsed.methodOverheadSeconds(t);

			final double total = (searchSeconds + overheadSeconds) * parsed.timeSafetyMultiplier;
			final int seconds = (int) Math.ceil(total);
			return toSlurmTime(seconds);
		}

		private static String toSlurmTime(final int totalSeconds)
		{
			int s = Math.max(0, totalSeconds);
			final int hours = s / 3600;
			s -= hours * 3600;
			final int mins = s / 60;
			s -= mins * 60;
			return String.format(Locale.ROOT, "%02d:%02d:%02d", hours, mins, s);
		}
	}

	// -------------------- PLANNED TEST CSV --------------------

	static final class PlannedTest
	{
		final String testId;
		final String gameName;
		final String component;
		final String variantSelection;
		final String variantSimulation;
		final String variantBackprop;
		final String variantFinalMove;
		final String baselineSelection;
		final String baselineSimulation;
		final String baselineBackprop;
		final String baselineFinalMove;
		final double moveTimeSeconds;
		final int gamesPerMatchup;
		final int maxMoves;
		final int requiresHeuristics;

		PlannedTest(
				final String testId,
				final String gameName,
				final String component,
				final String variantSelection,
				final String variantSimulation,
				final String variantBackprop,
				final String variantFinalMove,
				final String baselineSelection,
				final String baselineSimulation,
				final String baselineBackprop,
				final String baselineFinalMove,
				final double moveTimeSeconds,
				final int gamesPerMatchup,
				final int maxMoves,
				final int requiresHeuristics)
		{
			this.testId = testId;
			this.gameName = gameName;
			this.component = component;
			this.variantSelection = variantSelection;
			this.variantSimulation = variantSimulation;
			this.variantBackprop = variantBackprop;
			this.variantFinalMove = variantFinalMove;
			this.baselineSelection = baselineSelection;
			this.baselineSimulation = baselineSimulation;
			this.baselineBackprop = baselineBackprop;
			this.baselineFinalMove = baselineFinalMove;
			this.moveTimeSeconds = moveTimeSeconds;
			this.gamesPerMatchup = gamesPerMatchup;
			this.maxMoves = maxMoves;
			this.requiresHeuristics = requiresHeuristics;
		}

		static List<PlannedTest> loadAll(final Path plan) throws IOException
		{
			final List<PlannedTest> out = new ArrayList<>();
			try (BufferedReader br = Files.newBufferedReader(plan, StandardCharsets.UTF_8))
			{
				final String headerLine = br.readLine();
				if (headerLine == null)
					return out;
				final List<String> header = Csv.parseLine(headerLine);
				final Map<String, Integer> idx = Csv.index(header);

				String line;
				while ((line = br.readLine()) != null)
				{
					if (line.trim().isEmpty())
						continue;
					final List<String> fields = Csv.parseLine(line);
					out.add(new PlannedTest(
							Csv.get(fields, idx, "testId"),
							Csv.get(fields, idx, "gameName"),
							Csv.get(fields, idx, "component"),
							Csv.get(fields, idx, "variantSelection"),
							Csv.get(fields, idx, "variantSimulation"),
							Csv.get(fields, idx, "variantBackprop"),
							Csv.get(fields, idx, "variantFinalMove"),
							Csv.get(fields, idx, "baselineSelection"),
							Csv.get(fields, idx, "baselineSimulation"),
							Csv.get(fields, idx, "baselineBackprop"),
							Csv.get(fields, idx, "baselineFinalMove"),
							Csv.getDouble(fields, idx, "moveTimeSeconds", 0.1),
							Csv.getInt(fields, idx, "gamesPerMatchup", 2),
							Csv.getInt(fields, idx, "maxMoves", 500),
							Csv.getInt(fields, idx, "requiresHeuristics", 0)
					));
				}
			}
			return out;
		}
	}

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

		static Map<String, Integer> index(final List<String> header)
		{
			final Map<String, Integer> map = new HashMap<>();
			for (int i = 0; i < header.size(); i++)
				map.put(norm(header.get(i)), i);
			return map;
		}

		static String get(final List<String> fields, final Map<String, Integer> idx, final String col)
		{
			final Integer i = idx.get(norm(col));
			if (i == null || i < 0 || i >= fields.size())
				return "";
			return fields.get(i);
		}

		static int getInt(final List<String> fields, final Map<String, Integer> idx, final String col, final int def)
		{
			final String s = get(fields, idx, col);
			try
			{
				return Integer.parseInt(s.trim());
			}
			catch (final Exception ignored)
			{
				return def;
			}
		}

		static double getDouble(final List<String> fields, final Map<String, Integer> idx, final String col, final double def)
		{
			final String s = get(fields, idx, col);
			try
			{
				return Double.parseDouble(s.trim());
			}
			catch (final Exception ignored)
			{
				return def;
			}
		}

		private static String norm(final String s)
		{
			return s == null ? "" : s.trim().toLowerCase(Locale.ROOT);
		}
	}

	// -------------------- ARGS --------------------

	static final class Args
	{
		final Path planPath;
		final Path catalogPath;
		final Path outDir;

		final String moduleLoad;
		final String projectDir;
		final String ludiiJar;
		final String planInProjectDir;
		final String resultsDir;
		final String runnerClass;

		final String jobPrefix;
		final String logPrefix;

		// resource model parameters
		final int baseCpus;
		final int maxCpus;
		final int baseMemMb;
		final int maxMemMb;
		final double memMbPerPlayableSite;
		final double memMbPerComponent;
		final int hiddenInfoMemMb;
		final int heuristicsMemMb;
		final double baseOverheadSeconds;
		final double overheadSecondsPerPlayableSite;
		final double overheadSecondsPerComponent;
		final double heuristicsOverheadSeconds;
		final double timeSafetyMultiplier;

		private Args(
				final Path planPath,
				final Path catalogPath,
				final Path outDir,
				final String moduleLoad,
				final String projectDir,
				final String ludiiJar,
				final String planInProjectDir,
				final String resultsDir,
				final String runnerClass,
				final String jobPrefix,
				final String logPrefix,
				final int baseCpus,
				final int maxCpus,
				final int baseMemMb,
				final int maxMemMb,
				final double memMbPerPlayableSite,
				final double memMbPerComponent,
				final int hiddenInfoMemMb,
				final int heuristicsMemMb,
				final double baseOverheadSeconds,
				final double overheadSecondsPerPlayableSite,
				final double overheadSecondsPerComponent,
				final double heuristicsOverheadSeconds,
				final double timeSafetyMultiplier)
		{
			this.planPath = planPath;
			this.catalogPath = catalogPath;
			this.outDir = outDir;
			this.moduleLoad = moduleLoad;
			this.projectDir = projectDir;
			this.ludiiJar = ludiiJar;
			this.planInProjectDir = planInProjectDir;
			this.resultsDir = resultsDir;
			this.runnerClass = runnerClass;
			this.jobPrefix = jobPrefix;
			this.logPrefix = logPrefix;
			this.baseCpus = baseCpus;
			this.maxCpus = maxCpus;
			this.baseMemMb = baseMemMb;
			this.maxMemMb = maxMemMb;
			this.memMbPerPlayableSite = memMbPerPlayableSite;
			this.memMbPerComponent = memMbPerComponent;
			this.hiddenInfoMemMb = hiddenInfoMemMb;
			this.heuristicsMemMb = heuristicsMemMb;
			this.baseOverheadSeconds = baseOverheadSeconds;
			this.overheadSecondsPerPlayableSite = overheadSecondsPerPlayableSite;
			this.overheadSecondsPerComponent = overheadSecondsPerComponent;
			this.heuristicsOverheadSeconds = heuristicsOverheadSeconds;
			this.timeSafetyMultiplier = timeSafetyMultiplier;
		}

		double methodOverheadSeconds(final PlannedTest t)
		{
			// Small deterministic overhead to satisfy "based on methods".
			double s = 0.0;
			final String sim = norm(t.variantSimulation);
			if ("mast".equals(sim) || "nst".equals(sim)) s += 10.0;
			if ("heuristic".equals(sim) || sim.contains("playouths") || "lgr".equals(sim)) s += 20.0;

			final String sel = norm(t.variantSelection);
			if (sel.contains("grave") || sel.contains("brave")) s += 10.0;
			if (sel.contains("progressive widening")) s += 10.0;

			final String back = norm(t.variantBackprop);
			if (back.contains("alphago") || back.contains("heuristic")) s += 10.0;

			return s;
		}

		static Args parse(final String[] args)
		{
			Path plan = Paths.get("planned_tests.csv");
			Path catalog = Paths.get(GameCatalog.DEFAULT_CSV_NAME);
			Path outDir = Paths.get("slurm_jobs");

			String moduleLoad = "Java";
			String projectDir = "$HOME/LudiiMCTSVariations";
			String ludiiJar = "$HOME/Ludii-1.3.14.jar";
			String planInProjectDir = "${PROJECT_DIR}/planned_tests.csv";
			String resultsDir = "${PROJECT_DIR}/out/planned_results";
			String runnerClass = "experiments.planning.RunPlannedTest";

			String jobPrefix = "mcts_";
			String logPrefix = "planned_";

			// Defaults are the same baseline as your basic_test.sh (4 CPUs, 6G). The scaling is deterministic.
			int baseCpus = 4;
			int maxCpus = 16;
			int baseMemMb = 6 * 1024;
			int maxMemMb = 64 * 1024;
			double memMbPerPlayableSite = 2.0;
			double memMbPerComponent = 50.0;
			int hiddenInfoMemMb = 512;
			int heuristicsMemMb = 512;
			double baseOverheadSeconds = 60.0;
			double overheadSecondsPerPlayableSite = 0.2;
			double overheadSecondsPerComponent = 2.0;
			double heuristicsOverheadSeconds = 30.0;
			double timeSafetyMultiplier = 1.10;

			for (int i = 0; i < args.length; i++)
			{
				final String a = args[i];
				if ("--plan".equalsIgnoreCase(a) && i + 1 < args.length)
					plan = Paths.get(args[++i]);
				else if ("--catalog".equalsIgnoreCase(a) && i + 1 < args.length)
					catalog = Paths.get(args[++i]);
				else if ("--out-dir".equalsIgnoreCase(a) && i + 1 < args.length)
					outDir = Paths.get(args[++i]);
				else if ("--project-dir".equalsIgnoreCase(a) && i + 1 < args.length)
					projectDir = args[++i];
				else if ("--ludii-jar".equalsIgnoreCase(a) && i + 1 < args.length)
					ludiiJar = args[++i];
				else if ("--module".equalsIgnoreCase(a) && i + 1 < args.length)
					moduleLoad = args[++i];
				else if ("--plan-path".equalsIgnoreCase(a) && i + 1 < args.length)
					planInProjectDir = args[++i];
				else if ("--results-dir".equalsIgnoreCase(a) && i + 1 < args.length)
					resultsDir = args[++i];
				else if ("--runner".equalsIgnoreCase(a) && i + 1 < args.length)
					runnerClass = args[++i];
				else if ("--job-prefix".equalsIgnoreCase(a) && i + 1 < args.length)
					jobPrefix = args[++i];
				else if ("--log-prefix".equalsIgnoreCase(a) && i + 1 < args.length)
					logPrefix = args[++i];
				else if ("--base-cpus".equalsIgnoreCase(a) && i + 1 < args.length)
					baseCpus = Integer.parseInt(args[++i]);
				else if ("--base-mem-mb".equalsIgnoreCase(a) && i + 1 < args.length)
					baseMemMb = Integer.parseInt(args[++i]);
				else if ("--time-safety".equalsIgnoreCase(a) && i + 1 < args.length)
					timeSafetyMultiplier = Double.parseDouble(args[++i]);
			}

			return new Args(
					plan,
					catalog,
					outDir,
					moduleLoad,
					projectDir,
					ludiiJar,
					planInProjectDir,
					resultsDir,
					runnerClass,
					jobPrefix,
					logPrefix,
					baseCpus,
					maxCpus,
					baseMemMb,
					maxMemMb,
					memMbPerPlayableSite,
					memMbPerComponent,
					hiddenInfoMemMb,
					heuristicsMemMb,
					baseOverheadSeconds,
					overheadSecondsPerPlayableSite,
					overheadSecondsPerComponent,
					heuristicsOverheadSeconds,
					timeSafetyMultiplier
			);
		}

		private static String norm(final String s)
		{
			return s == null ? "" : s.trim().toLowerCase(Locale.ROOT);
		}
	}
}
