import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import requests

load_dotenv()
token = os.getenv('DISCORD_TOKEN')
steam_api_key = os.getenv('STEAM_API_KEY')

# Steam API base URL
STEAM_API_BASE = "https://api.steampowered.com"

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

    if message.author.name == 'northuoren':
        await channel.send(f'I hope you fucking die {message.author} what kind of retard would say "{message.content}"')
        return

    if message.author.name == 'northuoren':
        await channel.send(f'Hello, {message.author}!')
        return

    await bot.process_commands(message)


# Steam API Commands
@bot.tree.command(name="steam_user", description="Get Steam user information")
async def steam_user(interaction: discord.Interaction, steam_id: str):
    """Get basic Steam user information"""
    try:
        # Get user summary using Steam Web API
        url = f"{STEAM_API_BASE}/ISteamUser/GetPlayerSummaries/v0002/"
        params = {
            'key': steam_api_key,
            'steamids': steam_id
        }

        response = requests.get(url, params=params)
        data = response.json()

        if not data['response']['players']:
            await interaction.response.send_message("User not found or invalid Steam ID.")
            return

        user = data['response']['players'][0]

        embed = discord.Embed(
            title=f"Steam Profile: {user['personaname']}",
            color=0x1b2838
        )

        embed.add_field(name="Steam ID", value=user['steamid'], inline=True)
        embed.add_field(name="Profile State",
                        value="Public" if user['communityvisibilitystate'] == 3 else "Private", inline=True)
        embed.add_field(name="Profile Created", value=user.get('timecreated', 'Unknown'), inline=True)

        if 'avatarfull' in user:
            embed.set_thumbnail(url=user['avatarfull'])

        if 'profileurl' in user:
            embed.add_field(name="Profile URL", value=user['profileurl'], inline=False)

        await interaction.response.send_message(embed=embed)

    except Exception as e:
        await interaction.response.send_message(f"Error fetching Steam user data: {str(e)}")


@bot.tree.command(name="steam_games", description="Get user's recently played games")
async def steam_games(interaction: discord.Interaction, steam_id: str):
    """Get recently played games for a Steam user"""
    try:
        # Get recently played games using Steam Web API
        url = f"{STEAM_API_BASE}/IPlayerService/GetRecentlyPlayedGames/v0001/"
        params = {
            'key': steam_api_key,
            'steamid': steam_id,
            'count': 5
        }

        response = requests.get(url, params=params)
        data = response.json()

        if not data['response'] or 'games' not in data['response']:
            await interaction.response.send_message("No recently played games found or profile is private.")
            return

        games = data['response']['games']

        embed = discord.Embed(
            title="Recently Played Games",
            color=0x1b2838
        )

        for game in games[:5]:  # Show top 5 games
            playtime = round(game['playtime_forever'] / 60, 1)  # Convert to hours
            recent_playtime = round(game['playtime_2weeks'] / 60, 1) if 'playtime_2weeks' in game else 0

            embed.add_field(
                name=game['name'],
                value=f"Total: {playtime}h\nRecent: {recent_playtime}h",
                inline=True
            )

        await interaction.response.send_message(embed=embed)

    except Exception as e:
        await interaction.response.send_message(f"Error fetching Steam games data: {str(e)}")


@bot.tree.command(name="steam_game_info", description="Get information about a specific game")
async def steam_game_info(interaction: discord.Interaction, app_id: str):
    """Get detailed information about a Steam game"""
    try:
        # Use Steam Store API for game details
        url = f"https://store.steampowered.com/api/appdetails"
        params = {
            'appids': app_id,
            'format': 'json'
        }

        response = requests.get(url, params=params)
        data = response.json()

        if not data or app_id not in data or not data[app_id]['success']:
            await interaction.response.send_message("Game not found or invalid App ID.")
            return

        game = data[app_id]['data']

        embed = discord.Embed(
            title=game['name'],
            description=game.get('short_description', 'No description available')[:500],
            color=0x1b2838
        )

        if 'header_image' in game:
            embed.set_image(url=game['header_image'])

        embed.add_field(name="Release Date", value=game['release_date']['date'], inline=True)
        embed.add_field(name="Developer", value=", ".join(game['developers']), inline=True)
        embed.add_field(name="Publisher", value=", ".join(game['publishers']), inline=True)

        if game.get('is_free'):
            embed.add_field(name="Price", value="Free to Play", inline=True)
        elif 'price_overview' in game:
            price = game['price_overview']
            embed.add_field(name="Price", value=f"{price['final_formatted']}", inline=True)

        await interaction.response.send_message(embed=embed)

    except Exception as e:
        await interaction.response.send_message(f"Error fetching game information: {str(e)}")


@bot.tree.command(name="steam_search", description="Search for Steam games")
async def steam_search(interaction: discord.Interaction, game_name: str):
    """Search for Steam games by name"""
    try:
        # This is a basic implementation - you might want to use a more sophisticated search
        await interaction.response.send_message(
            f"Searching for '{game_name}' - this feature needs additional implementation with Steam's search API or a game database.")

    except Exception as e:
        await interaction.response.send_message(f"Error searching for games: {str(e)}")


bot.run(token, log_handler=handler, log_level=logging.DEBUG)