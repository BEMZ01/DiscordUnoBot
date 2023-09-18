from pprint import pprint
import discord
from discord.ext import commands, tasks
import random
import sqlite3 as sql
import logging
from utils.game import Table


class UnoGame(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot
        self.logger = logging.getLogger('discord')
        self.games = []
        self.TableSize = 2

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info(f'Loaded {self.__class__.__name__}!')
        self.logger.debug(f'Starting matchmaking controller')
        self.matchmaking_controller.start()

    @tasks.loop(seconds=5)
    async def monitorActiveGames(self):
        for i, game in enumerate(self.games):
            if game.status == 'ended':
                if game.winner is not None:
                    # update the database with the winner's stats
                    with sql.connect('data/database.db') as con:
                        cur = con.cursor()
                        cur.execute('SELECT wins,losses FROM playerData WHERE playerID = ?', (game.winner.id,))
                        fa = cur.fetchall()
                        if not fa:
                            cur.execute('INSERT INTO playerData VALUES (?,?,?)', (game.winner.id, 1, 0))
                        else:
                            cur.execute('UPDATE playerData SET wins = ? WHERE playerID = ?',
                                        (fa[0][0] + 1, game.winner.id))
                            await self.bot.get_user(game.winner.id).send(f'You won the game against {", ".join([str(player.name) for player in game.players if player != game.winner])}!', delete_after=60)
                        # update the database with the loser's stats
                        for player in game.players:
                            if player != game.winner:
                                cur.execute('SELECT wins,losses FROM playerData WHERE playerID = ?', (player.id,))
                                fa = cur.fetchall()
                                if not fa:
                                    cur.execute('INSERT INTO playerData VALUES (?,?,?)', (player.id, 0, 1))
                                else:
                                    cur.execute('UPDATE playerData SET losses = ? WHERE playerID = ?',
                                                (fa[0][1] + 1, player.id))
                                    await self.bot.get_user(player.id).send(
                                        f'You lost the game against {", ".join([str(p.name) for p in game.players if p != player])}!',
                                        delete_after=60)

                    con.commit()
                self.games.remove(game)
                self.logger.info(f'Removed game {i} from the active games list as it has ended')
            elif game.status == 'cancelled':
                self.games.remove(game)
                self.logger.info(f'Removed game {i} from the active games list as it was cancelled')

    @tasks.loop(seconds=10)
    async def matchmaking_controller(self):
        with sql.connect('data/database.db') as con:
            cur = con.cursor()
            cur.execute('SELECT * FROM queue')
            queue = [row[0] for row in cur.fetchall()]
            if len(queue) >= 2:
                playerData = {}
                # sort the queue by the number of games they've played
                for player in queue:
                    cur.execute('SELECT wins,losses,playerID FROM playerData WHERE playerID = ?', (player,))
                    fa = cur.fetchall()
                    playerData[player] = fa
                # work out a win/loss ratio for each player
                winLossRatios = {}
                pprint(playerData)
                for player in playerData:
                    try:
                        winLossRatios[player] = playerData[player][0][0] / playerData[player][0][1]
                    except ZeroDivisionError:
                        self.logger.error(f'Player {player} has no losses (ZeroDivisionError)')
                        winLossRatios[player] = 1
                    except IndexError:  # player not in DB
                        winLossRatios[player] = 1
                        self.logger.error(f'Player {player} not in database (IndexError)')
                        self.logger.info(f'Adding {player} to the database')
                        cur.execute('INSERT INTO playerData VALUES (?,?,?)', (player, 0, 0))
                # sort the queue by the win/loss ratio
                queue.sort(key=lambda x: winLossRatios[x])
                players = []
                # pop upto 7 players from the queue, stop when either the queue is empty or 7 players have been popped
                for i in range(7):
                    try:
                        players.append(queue.pop(0))
                    except IndexError:
                        break
                self.games.append(Table(players, self.bot))
                for player in players:
                    cur.execute('DELETE FROM queue WHERE user_id=?', (player,))
                    players[players.index(player)] = self.bot.get_user(player)
                self.bot.loop.create_task(self.games[-1].setup())
                self.logger.info(f'Created a game with players {", ".join([str(player) for player in players])}')
                try:
                    self.monitorActiveGames.start()
                except RuntimeError:
                    self.logger.debug(f'Active game monitor already running')
            con.commit()


def setup(bot):
    bot.add_cog(UnoGame(bot))
