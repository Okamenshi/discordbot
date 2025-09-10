import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os

load_dotenv()
token = os.getenv('DISCORD_TOKEN')


handler = logging.FileHandler(filename='.venv/discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.messages = True

bot = commands.Bot(command_prefix='/', intents=intents)


@bot.event
async def on_ready():
    print(f'We are ready to go in, {bot.user.name}')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


@bot.event
async def on_message(message):
    channel = bot.get_channel(1410656310894268630)
    if message.author == bot.user:
        return
    # if message.content.startswith(command.prefix):

    if message.author.name == 'northuoren':
        await channel.send(f'I hope you fucking die {message.author} what kind of retard would say "{message.content}"')
        return

    if message.author.name == 'northuoren':
        await channel.send(f'Hello, {message.author}!')
        return

    await bot.process_commands(message)


@bot.tree.command(name="magick trick", description="mmmmnnngh")
async def magick(interaction: discord.Interaction):
    await interaction.response.send_message(f'{interaction.user.name} explode')


bot.run(token, log_handler=handler, log_level=logging.DEBUG)