import logging
import discord
from discord import option
from discord.ext import commands
from discord.ext.pages import Paginator, Page
import sqlite3 as sql


class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('discord')

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info(f'Loaded {self.__class__.__name__}!')

    @commands.slash_command(name='stats', description='Get your stats')
    @option(name='user', description='The user to get stats for', required=False, type=discord.Member)
    async def stats(self, ctx, user: discord.Member = None):
        """This command will get the stats of a user. If no user is specified, it will get the stats of the user who ran the command."""
        if user is None:
            user = ctx.author
        with sql.connect('data/database.db') as con:
            cur = con.cursor()
            cur.execute('SELECT wins,losses FROM playerData WHERE playerID = ?', (user.id,))
            fa = cur.fetchall()
            if not fa:
                await ctx.respond(f'{user.name} has not played any games yet!', ephemeral=True, delete_after=10)
            else:
                embed = discord.Embed(title=f'{user.name} has won {fa[0][0]} games and lost {fa[0][1]} games!',
                                      description='',
                                      color=discord.Color.random())
                embed.add_field(name='Win/Loss Ratio', value=f'{round(fa[0][0] / fa[0][1], 2) if fa[0][1] != 0 else "N/A"}')
                embed.add_field(name='Win Percentage', value=f'{round(fa[0][0] / (fa[0][0] + fa[0][1]), 2)*100 if fa[0][0] + fa[0][1] != 0 else 0}%')
                embed.add_field(name='Total Games Played', value=f'{fa[0][0] + fa[0][1]}')
                embed.add_field(name='Total Games Won', value=f'{fa[0][0]}')
                embed.add_field(name='Total Games Lost', value=f'{fa[0][1]}')
                embed.set_author(name=f"{user.name}'s stats", icon_url=user.avatar.url)
                await ctx.respond(embed=embed, delete_after=120)

    @commands.slash_command(name='leaderboard', description='Get the leaderboard')
    async def leaderboard(self, ctx):
        """display top 10 players"""
        await ctx.defer()
        with sql.connect('data/database.db') as con:
            cur = con.cursor()
            cur.execute('SELECT playerID,wins,losses FROM playerData ORDER BY wins DESC LIMIT 10')
            fa = cur.fetchall()
            pages = []
            # display 10 users per page
            for i in range(0, len(fa), 10):
                embed = discord.Embed(title='Leaderboard', color=discord.Color.random())
                for j in range(i, i + 10):
                    if j < len(fa):
                        embed.add_field(name=f'{j + 1}. '
                                             f'{self.bot.get_user(fa[j][0]).name if self.bot.get_user(fa[j][0]) else "Unknown User"}'
                                             f'({fa[j][1]} wins, {fa[j][2]} losses)',
                                        value="",
                                        inline=False)
                pages.append(embed)
            paginator = Paginator(pages=pages)
            await paginator.respond(ctx.interaction)


    @commands.slash_command(name='info', description='Get info about the bot')
    async def info(self, ctx):
        """display info about the bot"""
        embed = discord.Embed(title='Info', description='Info about the bot', color=discord.Color.random())
        embed.add_field(name='Shard Count', value=f'{self.bot.shard_count}')
        embed.add_field(name='Guild Count', value=f'{len(self.bot.guilds)}')
        embed.add_field(name='User Count', value=f'{len(self.bot.users)}')
        embed.add_field(name='Latency', value=f'{round(self.bot.latency * 1000)}ms')
        # view information about the shards
        try:
            current_shard = self.bot.get_shard(ctx.guild.shard_id)
            embed.add_field(name='Shard ID', value=f'{current_shard.id}')
            embed.add_field(name='Shard Latency', value=f'{round(current_shard.latency * 1000)}ms')
        except AttributeError:
            pass
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label='Invite', url='https://discord.com/api/oauth2/authorize?client_id=1141764489532952686&permissions=826781207616&scope=bot', emoji='📨'))
        view.add_item(discord.ui.Button(label='Source', url='https://github.com/BEMZ01/DiscordUnoBot', emoji='📃'))
        view.add_item(discord.ui.Button(label='Top.gg', url='https://top.gg/bot/1141764489532952686', emoji='📈'))
        await ctx.respond(embed=embed, ephemeral=True, delete_after=30, view=view)


def setup(bot):
    bot.add_cog(Stats(bot))
