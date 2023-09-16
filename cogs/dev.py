import logging
import discord
from discord.ext import commands
import sqlite3 as sql


class development(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('discord')

    @commands.slash_command(name="add", description="Add you and test account to the queue")
    async def search(self, ctx: discord.ApplicationContext):
        with sql.connect('data/database.db') as con:
            cur = con.cursor()
            cur.execute('INSERT INTO queue VALUES (?)', (234248229426823168,))
            cur.execute('INSERT INTO queue VALUES (?)', (234247240225390592,))
            con.commit()
            await ctx.respond("Added you and test account to the queue", ephemeral=True, delete_after=5)

def setup(bot):
    bot.add_cog(development(bot))
