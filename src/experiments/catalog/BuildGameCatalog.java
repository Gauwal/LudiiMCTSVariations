package experiments.catalog;

import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

import java.util.Arrays;
import java.util.List;

/**
 * CLI entrypoint to build and persist the game catalog CSV.
 *
 * What it does:
 * - Enumerates all Ludii games.
 * - Loads each game and extracts a fixed set of static-ish properties.
 * - Writes the resulting table to a CSV (default: game_catalog.csv).
 * - Also writes a build report CSV with any loader/extractor warnings/errors
 *   attributed per-game (default: game_catalog_build_report.csv).
 *
 * This is intentionally a "data prep" tool: it does not run MCTS or play games.
 */
public final class BuildGameCatalog
{
	private BuildGameCatalog()
	{
		// utility
	}

	public static void main(final String[] args) throws Exception
	{
		// Output files.
		Path out = Paths.get(GameCatalog.DEFAULT_CSV_NAME);
		Path reportOut = Paths.get("game_catalog_build_report.csv");

		// Console behavior.
		boolean echoAllWarnings = false;
		int progressEvery = 100;
		boolean excludeWarnedGames = true;

		// Validity filters (defaults match our experiment constraints).
		boolean disallowStochastic = true;
		boolean requireAlternating = true;

		// Very small CLI parser (kept dependency-free on purpose).
		for (int i = 0; i < args.length; i++)
		{
			final String a = args[i];
			if ("--out".equalsIgnoreCase(a) && i + 1 < args.length)
			{
				out = Paths.get(args[++i]);
			}
			else if ("--report".equalsIgnoreCase(a) && i + 1 < args.length)
			{
				reportOut = Paths.get(args[++i]);
			}
			else if ("--echo-warnings".equalsIgnoreCase(a))
			{
				echoAllWarnings = true;
			}
			else if ("--exclude-warnings".equalsIgnoreCase(a))
			{
				excludeWarnedGames = true;
			}
			else if ("--include-warned-games".equalsIgnoreCase(a))
			{
				excludeWarnedGames = false;
			}
			else if ("--progress-every".equalsIgnoreCase(a) && i + 1 < args.length)
			{
				progressEvery = Integer.parseInt(args[++i]);
			}
			else if ("--no-progress".equalsIgnoreCase(a))
			{
				progressEvery = 0;
			}
			else if ("--include-stochastic".equalsIgnoreCase(a))
			{
				disallowStochastic = false;
			}
			else if ("--allow-simultaneous".equalsIgnoreCase(a))
			{
				requireAlternating = false;
			}
		}

		final GameCatalog.Validity validity = new GameCatalog.Validity(disallowStochastic, requireAlternating);

		System.out.println("Building game catalog...");
		// Progress is printed every N games so you can see the script is alive.
		final long startMs = System.currentTimeMillis();
		final GameCatalog.ProgressCallback progress = p ->
		{
			final long elapsedMs = System.currentTimeMillis() - startMs;
			final double pct = (p.total <= 0) ? 0.0 : (100.0 * p.index / p.total);
			System.out.println(String.format(
					"Progress: %d/%d (%.1f%%) | rows=%d | warnings=%d | errors=%d | elapsed=%ds | last=%s",
					p.index,
					p.total,
					pct,
					p.rowsSoFar,
					p.warningCount,
					p.errorCount,
					Math.max(0L, elapsedMs / 1000L),
					p.gameName
			));
		};
		final GameCatalog.BuildResult result = GameCatalog.buildWithReport(validity, progressEvery > 0 ? progress : null, progressEvery);

		final GameCatalog.Table tableToWrite;
		if (excludeWarnedGames)
		{
			final java.util.HashSet<String> warned = new java.util.HashSet<>();
			for (final GameCatalog.BuildIssue issue : result.issues)
				warned.add(issue.gameName);
			tableToWrite = result.table.where(r -> !warned.contains(r.gameName));
			System.out.println("Catalog rows (excluding warned games): " + tableToWrite.size() + " (excluded " + (result.table.size() - tableToWrite.size()) + ")");
		}
		else
		{
			tableToWrite = result.table;
			System.out.println("Catalog rows: " + tableToWrite.size());
		}

		System.out.println("Writing: " + out.toAbsolutePath());
		GameCatalog.save(tableToWrite, out);

		System.out.println("Writing build report: " + reportOut.toAbsolutePath());
		writeReportCsv(result, reportOut);

		// Note: warnings are not suppressed. They are captured and reported per-game.
		System.out.println("Warnings: " + result.warningCount + " | Errors: " + result.errorCount);
		final int defaultPreview = 50;
		final int limit = echoAllWarnings ? Integer.MAX_VALUE : defaultPreview;
		int printed = 0;
		for (final GameCatalog.BuildIssue issue : result.issues)
		{
			if (printed >= limit)
				break;
			System.out.println("[" + issue.level + "/" + issue.stage + "] " + issue.gameName + ": " + issue.message);
			printed++;
		}
		if (!echoAllWarnings && result.issues.size() > defaultPreview)
			System.out.println("(Previewed " + defaultPreview + " issues; pass --echo-warnings to print all. Full report is in: " + reportOut.toAbsolutePath() + ")");
		System.out.println("Done.");
	}

	private static void writeReportCsv(final GameCatalog.BuildResult result, final Path reportOut) throws IOException
	{
		final List<String> header = Arrays.asList("level", "stage", "gameName", "message");
		try (BufferedWriter bw = Files.newBufferedWriter(reportOut, StandardCharsets.UTF_8))
		{
			bw.write(GameCatalog.Csv.toLine(header));
			bw.newLine();
			for (final GameCatalog.BuildIssue issue : result.issues)
			{
				bw.write(GameCatalog.Csv.toLine(Arrays.asList(issue.level, issue.stage, issue.gameName, issue.message)));
				bw.newLine();
			}
		}
	}
}
