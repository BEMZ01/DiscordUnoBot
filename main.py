import discord
from discord.ext import commands
from dotenv import load_dotenv
import logging
import os
import sqlite3 as sql

logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
file_handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s')
handler.setFormatter(formatter)
file_handler.setFormatter(formatter)
logger.addHandler(handler)
logger.addHandler(file_handler)

load_dotenv()

intents = discord.Intents.default()
intents.members = True
intents.messages = True

logger.debug("Starting bot")
bot = commands.AutoShardedBot(owner_id=234248229426823168, intents=intents)
# Load cogs
for filename in os.listdir('./cogs'):
    if filename.endswith('.py'):
        try:
            bot.load_extension(f'cogs.{filename[:-3]}')
            logger.info(f'Loaded {filename[:-3]}')
        except discord.errors.ExtensionFailed as e:
            logger.error(msg=f'Failed to load {filename[:-3]}')
            logger.error(msg=e)


@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user.name}#{bot.user.discriminator} ({bot.user.id})')
    logger.info(f'Connected to {len(bot.guilds)} guilds')


if __name__ == '__main__':
    logger.info("Connecting to database")
    with sql.connect('data/database.db') as con:
        cur = con.cursor()
        cur.execute('CREATE TABLE IF NOT EXISTS queue (user_id INTEGER PRIMARY KEY)')
        cur.execute('CREATE TABLE IF NOT EXISTS playerData (playerID INTEGER PRIMARY KEY UNIQUE NOT NULL, '
                    'wins INTEGER DEFAULT 0, '
                    'losses INTEGER DEFAULT 0)')
        con.commit()
    logger.debug("Starting bot")
    bot.run(os.getenv('DISCORD_TOKEN'))
