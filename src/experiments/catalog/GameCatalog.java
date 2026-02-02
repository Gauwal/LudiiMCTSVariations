package experiments.catalog;

import game.Game;
import game.equipment.container.board.Board;
import main.FileHandling;
import other.GameLoader;
import other.concept.Concept;
import other.context.Context;
import other.trial.Trial;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.function.Predicate;
import java.util.stream.Collectors;
import java.util.stream.Stream;

/**
 * Builds and loads a persisted "game catalog" (a searchable table of properties for all games).
 *
 * Intended usage:
 * - Run {@link BuildGameCatalog} once to generate game_catalog.csv.
 * - Other scripts call {@link #loadDefault()} and then filter via {@link Table#where(Predicate)}
 *   or convenience methods like {@link Table#whereEquals(String, String)}.
 *
 * Notes:
 * - This code is dependency-free (plain Java + Ludii) and does not call into AutomatedMCTSTesting.
 * - The catalog is meant to be stable and reproducible: it extracts "static-ish" properties from
 *   game definitions, not performance results.
 */
public final class GameCatalog
{
	public static final String DEFAULT_CSV_NAME = "game_catalog.csv";
	public static final int SCHEMA_VERSION = 2;

	private GameCatalog()
	{
		// utility
	}

	/**
	 * Criteria for which games are considered "valid" for the catalog.
	 */
	public static final class Validity
	{
		public final boolean disallowStochastic;
		public final boolean requireAlternatingMove;

		public Validity(final boolean disallowStochastic, final boolean requireAlternatingMove)
		{
			this.disallowStochastic = disallowStochastic;
			this.requireAlternatingMove = requireAlternatingMove;
		}

		public static Validity defaultValidity()
		{
			return new Validity(true, true);
		}
	}

	/**
	 * One row in the catalog.
	 *
	 * We keep strongly-typed fields but also expose {@link #get(String)} so callers can write
	 * simple property-based filters.
	 */
	public static final class Row
	{
		public final String gameName;

		// structural
		public final int numPlayers;
		public final int numCells;
		public final int numVertices;
		public final int numEdges;
		public final int numRows;
		public final int numColumns;
		public final int numCorners;
		public final int numComponents;
		public final int numPhases;
		public final int numPlayableSites;

		// topology (from concepts)
		public final double avgNumDirections;
		public final double avgNumOrthogonal;
		public final double avgNumDiagonal;

		// booleans (0/1 for easier CSV + filtering)
		public final int isStacking;
		public final int isStochastic;
		public final int isAlternating;
		public final int hasHiddenInfo;
		public final int requiresTeams;
		public final int hasTrack;
		public final int hasCard;
		public final int hasHandDice;
		/**
		 * 1 if Ludii metadata indicates heuristic(s) are provided for this game.
		 * Used to guard heuristic-dependent methods (and generally "domain-knowledge" based techniques).
		 */
		public final int hasHeuristics;
		public final int isVertexGame;
		public final int isEdgeGame;
		public final int isCellGame;
		public final int isDeductionPuzzle;

		private Row(
				final String gameName,
				final int numPlayers,
				final int numCells,
				final int numVertices,
				final int numEdges,
				final int numRows,
				final int numColumns,
				final int numCorners,
				final int numComponents,
				final int numPhases,
				final int numPlayableSites,
				final double avgNumDirections,
				final double avgNumOrthogonal,
				final double avgNumDiagonal,
				final int isStacking,
				final int isStochastic,
				final int isAlternating,
				final int hasHiddenInfo,
				final int requiresTeams,
				final int hasTrack,
				final int hasCard,
				final int hasHandDice,
				final int hasHeuristics,
				final int isVertexGame,
				final int isEdgeGame,
				final int isCellGame,
				final int isDeductionPuzzle)
		{
			this.gameName = gameName;
			this.numPlayers = numPlayers;
			this.numCells = numCells;
			this.numVertices = numVertices;
			this.numEdges = numEdges;
			this.numRows = numRows;
			this.numColumns = numColumns;
			this.numCorners = numCorners;
			this.numComponents = numComponents;
			this.numPhases = numPhases;
			this.numPlayableSites = numPlayableSites;
			this.avgNumDirections = avgNumDirections;
			this.avgNumOrthogonal = avgNumOrthogonal;
			this.avgNumDiagonal = avgNumDiagonal;
			this.isStacking = isStacking;
			this.isStochastic = isStochastic;
			this.isAlternating = isAlternating;
			this.hasHiddenInfo = hasHiddenInfo;
			this.requiresTeams = requiresTeams;
			this.hasTrack = hasTrack;
			this.hasCard = hasCard;
			this.hasHandDice = hasHandDice;
			this.hasHeuristics = hasHeuristics;
			this.isVertexGame = isVertexGame;
			this.isEdgeGame = isEdgeGame;
			this.isCellGame = isCellGame;
			this.isDeductionPuzzle = isDeductionPuzzle;
		}

		/**
		 * Property access by column name. Column names are defined by {@link #columns()}.
		 */
		public String get(final String column)
		{
			final String c = normalizeColumn(column);
			switch (c)
			{
				case "gamename":
					return gameName;
				case "numplayers":
					return Integer.toString(numPlayers);
				case "numcells":
					return Integer.toString(numCells);
				case "numvertices":
					return Integer.toString(numVertices);
				case "numedges":
					return Integer.toString(numEdges);
				case "numrows":
					return Integer.toString(numRows);
				case "numcolumns":
					return Integer.toString(numColumns);
				case "numcorners":
					return Integer.toString(numCorners);
				case "numcomponents":
					return Integer.toString(numComponents);
				case "numphases":
					return Integer.toString(numPhases);
				case "numplayablesites":
					return Integer.toString(numPlayableSites);
				case "avgnumdirections":
					return Double.toString(avgNumDirections);
				case "avgnumorthogonal":
					return Double.toString(avgNumOrthogonal);
				case "avgnumdiagonal":
					return Double.toString(avgNumDiagonal);
				case "isstacking":
					return Integer.toString(isStacking);
				case "isstochastic":
					return Integer.toString(isStochastic);
				case "isalternating":
					return Integer.toString(isAlternating);
				case "hashiddeninfo":
					return Integer.toString(hasHiddenInfo);
				case "requiresteams":
					return Integer.toString(requiresTeams);
				case "hastrack":
					return Integer.toString(hasTrack);
				case "hascard":
					return Integer.toString(hasCard);
				case "hashanddice":
					return Integer.toString(hasHandDice);
				case "hasheuristics":
					return Integer.toString(hasHeuristics);
				case "isvertexgame":
					return Integer.toString(isVertexGame);
				case "isedgegame":
					return Integer.toString(isEdgeGame);
				case "iscellgame":
					return Integer.toString(isCellGame);
				case "isdeductionpuzzle":
					return Integer.toString(isDeductionPuzzle);
				default:
					throw new IllegalArgumentException("Unknown column: " + column);
			}
		}
	}

	/**
	 * A searchable in-memory table.
	 */
	public static final class Table
	{
		private final List<Row> rows;
		private final Map<String, Row> byName;

		public Table(final List<Row> rows)
		{
			this.rows = Collections.unmodifiableList(new ArrayList<>(rows));
			final Map<String, Row> tmp = new HashMap<>();
			for (final Row r : rows)
				tmp.put(r.gameName, r);
			this.byName = Collections.unmodifiableMap(tmp);
		}

		public int size()
		{
			return rows.size();
		}

		public Stream<Row> stream()
		{
			return rows.stream();
		}

		public Optional<Row> findByName(final String gameName)
		{
			return Optional.ofNullable(byName.get(gameName));
		}

		public Table where(final Predicate<Row> predicate)
		{
			return new Table(rows.stream().filter(predicate).collect(Collectors.toList()));
		}

		public Table whereEquals(final String column, final String value)
		{
			final String expected = value == null ? "" : value.trim();
			return where(r -> Objects.equals(r.get(column).trim(), expected));
		}

		public Table whereIntAtLeast(final String column, final int min)
		{
			return where(r -> safeParseInt(r.get(column)) >= min);
		}

		public Table whereIntAtMost(final String column, final int max)
		{
			return where(r -> safeParseInt(r.get(column)) <= max);
		}

		public Table whereDoubleAtLeast(final String column, final double min)
		{
			return where(r -> safeParseDouble(r.get(column)) >= min);
		}

		public List<Row> rows()
		{
			return rows;
		}
	}

	/**
	 * Column order for persistence.
	 */
	public static List<String> columns()
	{
		final List<String> cols = new ArrayList<>();
		cols.add("schemaVersion");
		cols.add("gameName");
		cols.add("numPlayers");
		cols.add("numCells");
		cols.add("numVertices");
		cols.add("numEdges");
		cols.add("numRows");
		cols.add("numColumns");
		cols.add("numCorners");
		cols.add("numComponents");
		cols.add("numPhases");
		cols.add("numPlayableSites");
		cols.add("avgNumDirections");
		cols.add("avgNumOrthogonal");
		cols.add("avgNumDiagonal");
		cols.add("isStacking");
		cols.add("isStochastic");
		cols.add("isAlternating");
		cols.add("hasHiddenInfo");
		cols.add("requiresTeams");
		cols.add("hasTrack");
		cols.add("hasCard");
		cols.add("hasHandDice");
		cols.add("hasHeuristics");
		cols.add("isVertexGame");
		cols.add("isEdgeGame");
		cols.add("isCellGame");
		cols.add("isDeductionPuzzle");
		return Collections.unmodifiableList(cols);
	}

	public static Table build(final Validity validity)
	{
		return buildWithReport(validity).table;
	}

	@FunctionalInterface
	public interface ProgressCallback
	{
		/** Called periodically while scanning all games. */
		void onProgress(BuildProgress progress);
	}

	public static final class BuildProgress
	{
		public final int index; // 1-based
		public final int total;
		public final String gameName;
		public final int rowsSoFar;
		public final int warningCount;
		public final int errorCount;

		BuildProgress(
				final int index,
				final int total,
				final String gameName,
				final int rowsSoFar,
				final int warningCount,
				final int errorCount)
		{
			this.index = index;
			this.total = total;
			this.gameName = gameName;
			this.rowsSoFar = rowsSoFar;
			this.warningCount = warningCount;
			this.errorCount = errorCount;
		}
	}

	/**
	 * Builds a catalog and also returns a structured report of warnings/errors emitted while loading games.
	 *
	 * This is the non-"hiding" solution to noisy parser output: we capture it and attach it to the game name.
	 *
	 * Important: this captures System.out/System.err while loading/extracting a single game so we can
	 * attribute messages to that game.
	 */
	public static BuildResult buildWithReport(final Validity validity)
	{
		return buildWithReport(validity, null, 0);
	}

	/**
	 * Same as {@link #buildWithReport(Validity)} but calls {@code progress} every {@code progressEvery} games.
	 * Set {@code progressEvery} to 0 to disable callbacks.
	 */
	public static BuildResult buildWithReport(final Validity validity, final ProgressCallback progress, final int progressEvery)
	{
		final String[] allGames = listAllGames();
		final List<Row> rows = new ArrayList<>(allGames.length);
		final List<BuildIssue> issues = new ArrayList<>();
		int warningCount = 0;
		int errorCount = 0;

		for (int i = 0; i < allGames.length; i++)
		{
			final String gameName = allGames[i];
			if (progress != null && progressEvery > 0)
			{
				final int idx1 = i + 1;
				if (idx1 == 1 || idx1 == allGames.length || (idx1 % progressEvery) == 0)
					progress.onProgress(new BuildProgress(idx1, allGames.length, gameName, rows.size(), warningCount, errorCount));
			}

			final CapturedOutput captureLoad = CapturedOutput.start();
			final Game game;
			try
			{
				game = GameLoader.loadGameFromName(gameName);
			}
			catch (final Throwable t)
			{
				captureLoad.close();
				errorCount++;
				issues.addAll(captureLoad.toIssues("LOAD", gameName));
				issues.add(new BuildIssue("ERROR", "LOAD", gameName, "Exception loading game: " + t.getClass().getSimpleName() + ": " + safeMessage(t)));
				continue;
			}
			finally
			{
				captureLoad.close();
			}

			issues.addAll(captureLoad.toIssues("LOAD", gameName));
			warningCount += captureLoad.lineCount();

			if (game == null)
				continue;

			if (!isValid(game, validity))
				continue;

			final CapturedOutput captureExtract = CapturedOutput.start();
			final Row row;
			try
			{
				row = extractRow(game);
			}
			catch (final Throwable t)
			{
				captureExtract.close();
				errorCount++;
				issues.addAll(captureExtract.toIssues("EXTRACT", gameName));
				issues.add(new BuildIssue("ERROR", "EXTRACT", gameName, "Exception extracting features: " + t.getClass().getSimpleName() + ": " + safeMessage(t)));
				continue;
			}
			finally
			{
				captureExtract.close();
			}

			issues.addAll(captureExtract.toIssues("EXTRACT", gameName));
			warningCount += captureExtract.lineCount();

			rows.add(row);
		}

		return new BuildResult(new Table(rows), issues, warningCount, errorCount);
	}

	public static final class BuildResult
	{
		public final Table table;
		public final List<BuildIssue> issues;
		public final int warningCount;
		public final int errorCount;

		BuildResult(final Table table, final List<BuildIssue> issues, final int warningCount, final int errorCount)
		{
			this.table = table;
			this.issues = Collections.unmodifiableList(new ArrayList<>(issues));
			this.warningCount = warningCount;
			this.errorCount = errorCount;
		}
	}

	public static final class BuildIssue
	{
		public final String level; // "WARNING" or "ERROR"
		public final String stage; // "LOAD" or "EXTRACT"
		public final String gameName;
		public final String message;

		BuildIssue(final String level, final String stage, final String gameName, final String message)
		{
			this.level = level;
			this.stage = stage;
			this.gameName = gameName;
			this.message = message;
		}
	}

	public static Table loadDefault() throws IOException
	{
		return load(Paths.get(DEFAULT_CSV_NAME));
	}

	public static Table load(final Path csvPath) throws IOException
	{
		try (BufferedReader br = Files.newBufferedReader(csvPath, StandardCharsets.UTF_8))
		{
			final String headerLine = br.readLine();
			if (headerLine == null)
				throw new IOException("Empty catalog file: " + csvPath);

			final List<String> header = Csv.parseLine(headerLine);
			final Map<String, Integer> colIndex = new HashMap<>();
			for (int i = 0; i < header.size(); i++)
				colIndex.put(normalizeColumn(header.get(i)), i);

			final List<Row> rows = new ArrayList<>();
			String line;
			while ((line = br.readLine()) != null)
			{
				line = line.trim();
				if (line.isEmpty() || line.startsWith("#"))
					continue;

				final List<String> fields = Csv.parseLine(line);
				final int version = safeParseInt(getField(fields, colIndex, "schemaVersion"));
				if (version != SCHEMA_VERSION)
				{
					// tolerate older/newer schema if columns exist; otherwise fail fast
				}

				final String gameName = getField(fields, colIndex, "gameName");
				final Row r = new Row(
						gameName,
						safeParseInt(getField(fields, colIndex, "numPlayers")),
						safeParseInt(getField(fields, colIndex, "numCells")),
						safeParseInt(getField(fields, colIndex, "numVertices")),
						safeParseInt(getField(fields, colIndex, "numEdges")),
						safeParseInt(getField(fields, colIndex, "numRows")),
						safeParseInt(getField(fields, colIndex, "numColumns")),
						safeParseInt(getField(fields, colIndex, "numCorners")),
						safeParseInt(getField(fields, colIndex, "numComponents")),
						safeParseInt(getField(fields, colIndex, "numPhases")),
						safeParseInt(getField(fields, colIndex, "numPlayableSites")),
						safeParseDouble(getField(fields, colIndex, "avgNumDirections")),
						safeParseDouble(getField(fields, colIndex, "avgNumOrthogonal")),
						safeParseDouble(getField(fields, colIndex, "avgNumDiagonal")),
						safeParseInt(getField(fields, colIndex, "isStacking")),
						safeParseInt(getField(fields, colIndex, "isStochastic")),
						safeParseInt(getField(fields, colIndex, "isAlternating")),
						safeParseInt(getField(fields, colIndex, "hasHiddenInfo")),
						safeParseInt(getField(fields, colIndex, "requiresTeams")),
						safeParseInt(getField(fields, colIndex, "hasTrack")),
						safeParseInt(getField(fields, colIndex, "hasCard")),
						safeParseInt(getField(fields, colIndex, "hasHandDice")),
						safeParseInt(getField(fields, colIndex, "hasHeuristics")),
						safeParseInt(getField(fields, colIndex, "isVertexGame")),
						safeParseInt(getField(fields, colIndex, "isEdgeGame")),
						safeParseInt(getField(fields, colIndex, "isCellGame")),
						safeParseInt(getField(fields, colIndex, "isDeductionPuzzle"))
				);
				rows.add(r);
			}

			return new Table(rows);
		}
	}

	public static void save(final Table table, final Path csvPath) throws IOException
	{
		final List<String> cols = columns();
		try (BufferedWriter bw = Files.newBufferedWriter(csvPath, StandardCharsets.UTF_8))
		{
			bw.write(Csv.toLine(cols));
			bw.newLine();

			for (final Row r : table.rows())
			{
				final List<String> fields = new ArrayList<>(cols.size());
				for (final String col : cols)
				{
					if ("schemaVersion".equals(col))
						fields.add(Integer.toString(SCHEMA_VERSION));
					else
						fields.add(r.get(col));
				}
				bw.write(Csv.toLine(fields));
				bw.newLine();
			}
		}
	}

	private static boolean isValid(final Game game, final Validity validity)
	{
		if (validity.disallowStochastic && game.isStochasticGame())
			return false;
		if (validity.requireAlternatingMove && !game.isAlternatingMoveGame())
			return false;
		return true;
	}

	private static Row extractRow(final Game game)
	{
		// Use Ludii's canonical runtime objects for feature extraction.
		// This may trigger Ludii warnings for a small number of games; those are captured in the build report.
		final Trial trial = new Trial(game);
		final Context context = new Context(game, trial);

		final int numPlayers = game.players().count();

		int numCells = 0;
		int numVertices = 0;
		int numEdges = 0;
		int numRows = 0;
		int numColumns = 0;
		int numCorners = 0;

		final Board board = context.board();
		if (board != null && board.topology() != null)
		{
			numCells = board.topology().cells().size();
			numVertices = board.topology().vertices().size();
			numEdges = board.topology().edges().size();
			try
			{
				numRows = board.topology().rows(board.defaultSite()).size();
				numColumns = board.topology().columns(board.defaultSite()).size();
				numCorners = board.topology().corners(board.defaultSite()).size();
			}
			catch (final Exception ignored)
			{
				// keep 0 defaults
			}
		}

		final int numComponents = context.equipment().components().length - 1;
		final int numPhases = context.rules().phases().length;

		final int numPlayableSites = readIntConcept(game, Concept.NumPlayableSites.id(), numCells + numVertices + numEdges);
		final double avgNumDirections = readDoubleConcept(game, Concept.NumDirections.id(), 4.0);
		final double avgNumOrthogonal = readDoubleConcept(game, Concept.NumOrthogonalDirections.id(), 2.0);
		final double avgNumDiagonal = readDoubleConcept(game, Concept.NumDiagonalDirections.id(), 2.0);

		final int isStacking = game.isStacking() ? 1 : 0;
		final int isStochastic = game.isStochasticGame() ? 1 : 0;
		final int isAlternating = game.isAlternatingMoveGame() ? 1 : 0;
		final int hasHiddenInfo = game.hiddenInformation() ? 1 : 0;
		final int requiresTeams = game.requiresTeams() ? 1 : 0;

		int hasTrack = 0;
		try
		{
			hasTrack = game.hasTrack() ? 1 : 0;
		}
		catch (final Throwable ignored)
		{
			// keep 0
		}

		final int hasCard = game.hasCard() ? 1 : 0;

		int hasHandDice = 0;
		try
		{
			hasHandDice = game.hasHandDice() ? 1 : 0;
		}
		catch (final Throwable ignored)
		{
			// keep 0
		}

		final int hasHeuristics = detectHeuristics(game) ? 1 : 0;

		final int isVertexGame = context.isVertexGame() ? 1 : 0;
		final int isEdgeGame = context.isEdgeGame() ? 1 : 0;
		final int isCellGame = context.isCellGame() ? 1 : 0;
		final int isDeductionPuzzle = game.isDeductionPuzzle() ? 1 : 0;

		return new Row(
				game.name(),
				numPlayers,
				numCells,
				numVertices,
				numEdges,
				numRows,
				numColumns,
				numCorners,
				numComponents,
				numPhases,
				numPlayableSites,
				avgNumDirections,
				avgNumOrthogonal,
				avgNumDiagonal,
				isStacking,
				isStochastic,
				isAlternating,
				hasHiddenInfo,
				requiresTeams,
				hasTrack,
				hasCard,
				hasHandDice,
				hasHeuristics,
				isVertexGame,
				isEdgeGame,
				isCellGame,
				isDeductionPuzzle
		);
	}

	/**
	 * Detects whether the game provides heuristic(s) in Ludii metadata.
	 *
	 * Conservative: returns false if the API is unavailable or ambiguous.
	 */
	private static boolean detectHeuristics(final Game game)
	{
		if (game == null)
			return false;

		try
		{
			final Object metadata = invokeNoArg(game, "metadata");
			final Object ai = invokeNoArg(metadata, "ai");
			final Object heuristics = invokeNoArg(ai, "heuristics");
			if (heuristics == null)
				return false;

			// Some versions nest a list inside heuristics.heuristics()
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
			return false;
		}
	}

	private static Object invokeNoArg(final Object target, final String method)
	{
		if (target == null)
			return null;
		try
		{
			final java.lang.reflect.Method m = target.getClass().getMethod(method);
			m.setAccessible(true);
			return m.invoke(target);
		}
		catch (final Throwable t)
		{
			return null;
		}
	}

	private static int readIntConcept(final Game game, final int conceptId, final int defaultValue)
	{
		final String value = game.nonBooleanConcepts().get(conceptId);
		if (value == null)
			return defaultValue;
		String s = value.trim();
		if (s.endsWith(".0"))
			s = s.substring(0, s.length() - 2);
		try
		{
			return Integer.parseInt(s);
		}
		catch (final NumberFormatException e)
		{
			return defaultValue;
		}
	}

	private static double readDoubleConcept(final Game game, final int conceptId, final double defaultValue)
	{
		final String value = game.nonBooleanConcepts().get(conceptId);
		if (value == null)
			return defaultValue;
		try
		{
			return Double.parseDouble(value.trim());
		}
		catch (final NumberFormatException e)
		{
			return defaultValue;
		}
	}

	private static String[] listAllGames()
	{
		try
		{
			return FileHandling.listGames();
		}
		catch (final Throwable t)
		{
			throw new IllegalStateException(
					"Unable to list games. Ensure Ludii is on the classpath (main.FileHandling.listGames).",
					t
			);
		}
	}

	private static String normalizeColumn(final String col)
	{
		return col == null ? "" : col.replaceAll("\\s+", "").toLowerCase(Locale.ROOT);
	}

	private static int safeParseInt(final String s)
	{
		try
		{
			return Integer.parseInt(s.trim());
		}
		catch (final Exception e)
		{
			return 0;
		}
	}

	private static double safeParseDouble(final String s)
	{
		try
		{
			return Double.parseDouble(s.trim());
		}
		catch (final Exception e)
		{
			return 0.0;
		}
	}

	private static String getField(
			final List<String> fields,
			final Map<String, Integer> colIndex,
			final String column)
	{
		final Integer idx = colIndex.get(normalizeColumn(column));
		if (idx == null || idx < 0 || idx >= fields.size())
			return "";
		return fields.get(idx);
	}

	/** Minimal CSV helper (quotes + commas supported). */
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

	/**
	 * Captures System.out/System.err output (lines) to attribute parser messages to a specific game.
	 *
	 * Assumes the builder is single-threaded.
	 */
	private static final class CapturedOutput
	{
		private final java.io.PrintStream originalOut;
		private final java.io.PrintStream originalErr;
		private final java.io.ByteArrayOutputStream buffer;
		private final java.io.PrintStream captureStream;
		private boolean closed;

		private CapturedOutput(
				final java.io.PrintStream originalOut,
				final java.io.PrintStream originalErr,
				final java.io.ByteArrayOutputStream buffer,
				final java.io.PrintStream captureStream)
		{
			this.originalOut = originalOut;
			this.originalErr = originalErr;
			this.buffer = buffer;
			this.captureStream = captureStream;
			this.closed = false;
		}

		static CapturedOutput start()
		{
			final java.io.PrintStream out = System.out;
			final java.io.PrintStream err = System.err;
			final java.io.ByteArrayOutputStream baos = new java.io.ByteArrayOutputStream(8 * 1024);
			final java.io.PrintStream ps;
			try
			{
				ps = new java.io.PrintStream(baos, true, java.nio.charset.StandardCharsets.UTF_8);
			}
			catch (final Exception e)
			{
				throw new RuntimeException(e);
			}

			System.setOut(ps);
			System.setErr(ps);
			return new CapturedOutput(out, err, baos, ps);
		}

		void close()
		{
			if (closed)
				return;
			closed = true;
			System.setOut(originalOut);
			System.setErr(originalErr);
			captureStream.flush();
		}

		int lineCount()
		{
			return toLines().size();
		}

		List<BuildIssue> toIssues(final String stage, final String gameName)
		{
			final List<String> lines = toLines();
			if (lines.isEmpty())
				return Collections.emptyList();
			final List<BuildIssue> out = new ArrayList<>(lines.size());
			for (final String l : lines)
				out.add(new BuildIssue("WARNING", stage, gameName, l));
			return out;
		}

		private List<String> toLines()
		{
			final String raw;
			try
			{
				raw = buffer.toString(java.nio.charset.StandardCharsets.UTF_8);
			}
			catch (final Exception e)
			{
				return Collections.emptyList();
			}
			if (raw == null || raw.trim().isEmpty())
				return Collections.emptyList();
			final String[] split = raw.split("\\R");
			final List<String> out = new ArrayList<>();
			for (final String s : split)
			{
				final String t = s == null ? "" : s.trim();
				if (!t.isEmpty())
					out.add(t);
			}
			return out;
		}
	}

	private static String safeMessage(final Throwable t)
	{
		final String m = t.getMessage();
		return m == null ? "" : m.replaceAll("\\s+", " ").trim();
	}
}
