from pprint import pprint
import discord
from discord.ext import commands, tasks
import random
import sqlite3 as sql
import logging
from utils.game import Table
import datetime


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
                        if not game.winner.isBot:
                            cur.execute('SELECT wins,losses FROM playerData WHERE playerID = ?', (game.winner.id,))
                            fa = cur.fetchall()
                            if not fa:
                                cur.execute('INSERT INTO playerData VALUES (?,?,?)', (game.winner.id, 1, 0))
                            else:
                                cur.execute('UPDATE playerData SET wins = ? WHERE playerID = ?',
                                            (fa[0][0] + 1, game.winner.id))
                                await self.bot.get_user(game.winner.id).send(
                                    f'You won the game against {", ".join([str(player.name) for player in game.players])}!',
                                    delete_after=60)
                        # update the database with the loser's stats
                        for player in game.players:
                            if not player.isBot and player != game.winner:
                                cur.execute('SELECT wins,losses FROM playerData WHERE playerID = ?', (player.id,))
                                fa = cur.fetchall()
                                if not fa:
                                    cur.execute('INSERT INTO playerData VALUES (?,?,?)', (player.id, 0, 1))
                                else:
                                    cur.execute('UPDATE playerData SET losses = ? WHERE playerID = ?',
                                                (fa[0][1] + 1, player.id))
                                    await self.bot.get_user(player.id).send(
                                        f'You lost the game against {", ".join([str(p.name) for p in game.players])}!',
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
            # row 0 = user_id, row 1 = bots, row 2 = timestamp
            queue = [(row[0], row[1], row[2]) for row in cur.fetchall()]
            # if timestamp is more than 5 minutes ago, remove the user from the queue and send them a DM
            for row in queue:
                if datetime.datetime.now().timestamp() - row[2] > 500:
                    cur.execute('DELETE FROM queue WHERE user_id=?', (row[0],))
                    await self.bot.get_user(row[0]).send(
                        'You were removed from the queue because you were inactive for too long!', delete_after=60)
                    self.logger.info(f'Removed user {row[0]} from the queue because they were inactive for too long')
            # remove the users who are already in a game from the queue
            for game in self.games:
                for player in game.players:
                    if not player.isBot and (player.id,) in queue:
                        cur.execute('DELETE FROM queue WHERE user_id=?', (player.id,))
                        self.logger.info(f'Removed user {player.id} from the queue because they are already in a game')
            playerData = {}
            # sort the queue by the number of games they've played
            for player in queue:
                cur.execute('SELECT wins,losses,playerID FROM playerData WHERE playerID = ?', (player[0],))
                fa = cur.fetchall()
                if not fa:
                    playerData[player[0]] = (0, 0)
                else:
                    playerData[player[0]] = (fa[0][0], fa[0][1])
            # organise into two lists, one with players who want to play with bots and one with players who don't
            playersWithBots = []
            playersWithoutBots = []
            for player in queue:
                if player[1] == 1:
                    playersWithBots.append((player[0], playerData[player[0]]))
                else:
                    playersWithoutBots.append((player[0], playerData[player[0]]))
            # sort the lists by the win/loss ratio
            playersWithBots.sort(key=lambda x: x[1][0] / x[1][1] if x[1][1] != 0 else x[1][0])
            playersWithoutBots.sort(key=lambda x: x[1][0] / x[1][1] if x[1][1] != 0 else x[1][0])
            players = []
            for i in range(min(len(playersWithBots), self.TableSize)):
                players.append(playersWithBots[i][0])
            if len(players) > 2 or (len(players) == 1 and players[0] == 234248229426823168):
                # create a game with the players and bots
                self.games.append(Table(players, self.bot))
                for player in players:
                    cur.execute('DELETE FROM queue WHERE user_id=?', (player,))
                    players[players.index(player)] = self.bot.get_user(player)
                con.commit()
                self.bot.loop.create_task(self.games[-1].setup(True))
                self.logger.info(f'Created a game with players {", ".join([str(player) for player in players])}')
                try:
                    self.monitorActiveGames.start()
                except RuntimeError:
                    self.logger.debug(f'Active game monitor already running')
                return True
            # take the top players from the list of players who don't want to play with bots (upto the table size)
            players = []
            for i in range(min(len(playersWithoutBots), self.TableSize)):
                players.append(playersWithoutBots[i][0])
            if len(players) > 1:  # there has to be at least 2 players to start a game
                # create a game with the players and no bots
                self.games.append(Table(players, self.bot))
                for player in players:
                    cur.execute('DELETE FROM queue WHERE user_id=?', (player,))
                    players[players.index(player)] = self.bot.get_user(player)
                con.commit()
                self.bot.loop.create_task(self.games[-1].setup(False))
                self.logger.info(f'Created a game with players {", ".join([str(player) for player in players])}')
                try:
                    self.monitorActiveGames.start()
                except RuntimeError:
                    self.logger.debug(f'Active game monitor already running')
                con.commit()
                return True


def setup(bot):
    bot.add_cog(UnoGame(bot))
