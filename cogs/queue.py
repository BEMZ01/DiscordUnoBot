# A Cog for handling the queue system for multiplayer games in the bot.
import datetime
import discord
from discord import option
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

    async def test_DM(self, user: discord.User):
        # This function will check weather it is possible to DM a user.
        try:
            message = await self.bot.get_user(user.id).send("This is a test message to check if I can DM you.",
                                                            delete_after=1,
                                                            silent=True)
            await message.delete()
        except discord.errors.Forbidden:
            self.logger.error(f"Failed to DM User {user.id}")
            return False
        except discord.errors.HTTPException:
            self.logger.error(f"Failed to DM User {user.id}")
            return False
        else:
            return True

    @commands.slash_command(name='search', description='Search for a game')
    @option(name='bots', description='Whether to include bots in the game', required=False, type=bool)
    async def search(self, ctx: discord.ApplicationContext, bots: bool = True):
        if await self.test_DM(ctx.author):
            with sql.connect('data/database.db') as con:
                cur = con.cursor()
                cur.execute('SELECT * FROM queue WHERE user_id=?', (ctx.author.id,))
                if cur.fetchone() is None:
                    # get unix epoch timestamp
                    cur.execute('INSERT INTO queue VALUES (?, ?, ?)', (ctx.author.id, bots, datetime.datetime.now().timestamp()))
                    await ctx.respond(f'{ctx.author.mention} has joined the queue!', ephemeral=True, delete_after=5)
                else:
                    cur.execute('DELETE FROM queue WHERE user_id=?', (ctx.author.id, ))
                    await ctx.respond(f'{ctx.author.mention} has left the queue!', ephemeral=True, delete_after=5)
                con.commit()
        else:
            await ctx.respond('I was unable to DM you! Please allow me to send you DMs and try again.', ephemeral=True,
                              delete_after=10)


def setup(bot):
    bot.add_cog(Multiplayer(bot))
