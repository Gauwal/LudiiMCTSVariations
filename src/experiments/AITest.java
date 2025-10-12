package experiments;

import game.Game;
import mcts.MCTSVariations;
import other.AI;
import other.GameLoader;
import other.context.Context;
import other.move.Move;
import other.trial.Trial;

import java.util.ArrayList;
import java.util.List;



public class AITest {

    public static void main(final String[] args)
    {
        Game game = GameLoader.loadGameFromName("Amazons.lud");

        Trial trial = new Trial(game);
        Context context = new Context(game, trial);

        final int numGames = 10;

        final List<AI> agents = new ArrayList<AI>();
        agents.add(null);	// insert null at index 0, because player indices start at 1

        final int numPlayers = game.players().count();
        for (int p = 1; p <= numPlayers; ++p)
        {
            agents.add(new MCTSVariations("flat","MAST","decay"));
        }
        for (int i = 0; i < numGames; ++i) {

            game.start(context);

            for (int p = 1; p < agents.size(); ++p)
            {
                agents.get(p).initAI(game, p);
            }

            while (!context.trial().over())
            {
                final int mover = context.state().mover();
                final AI agent = agents.get(mover);
                final Move move = agent.selectAction
                        (
                                game,
                                new Context(context),
                                0.2,
                                -1,
                                -1
                        );
                game.apply(context, move);
            }
            System.out.println(context.trial().status());
        }

    }
}
