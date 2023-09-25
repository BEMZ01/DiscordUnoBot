import logging
import discord
from discord.ext import commands
import sqlite3 as sql


class development(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('discord')

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info(f'Loaded {self.__class__.__name__}!')


def setup(bot):
    bot.add_cog(development(bot))
