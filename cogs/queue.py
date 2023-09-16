# A Cog for handling the queue system for multiplayer games in the bot.
import discord
from discord.ext import commands, tasks
import sqlite3 as sql
import logging


class Multiplayer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('discord')

    # event listeners
    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info(f'Loaded {self.__class__.__name__}!')
        self.update_presence.start()

    @tasks.loop(seconds=10)
    async def update_presence(self):
        with sql.connect('data/database.db') as con:
            cur = con.cursor()
            cur.execute('SELECT * FROM queue')
            queue = len(cur.fetchall())
            # update presence with the number of players in the queue and an average wait time
            await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching,
                                                                     name=f'{queue} players in queue |'
                                                                          f' {queue * 5} seconds average wait time'))

    # commands
    @commands.slash_command(name='search', description='Search for a game')
    async def search(self, ctx: discord.ApplicationContext):
        with sql.connect('data/database.db') as con:
            cur = con.cursor()
            cur.execute('SELECT * FROM queue WHERE user_id=?', (ctx.author.id,))
            if cur.fetchone() is None:
                cur.execute('INSERT INTO queue VALUES (?)', (ctx.author.id,))
                await ctx.respond(f'{ctx.author.mention} has joined the queue!', ephemeral=True, delete_after=5)
            else:
                cur.execute('DELETE FROM queue WHERE user_id=?', (ctx.author.id,))
                await ctx.respond(f'{ctx.author.mention} has left the queue!', ephemeral=True, delete_after=5)
            con.commit()


def setup(bot):
    bot.add_cog(Multiplayer(bot))
