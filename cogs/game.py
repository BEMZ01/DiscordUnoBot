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
            con.commit()


def setup(bot):
    bot.add_cog(UnoGame(bot))
