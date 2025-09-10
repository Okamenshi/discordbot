import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import requests
from scripts.regsetup import description

# Load environment variables
load_dotenv()
token = os.getenv('DISCORD_TOKEN')
steam_api_key = os.getenv('STEAM_API_KEY')

# Steam API base URL
STEAM_API_BASE = "https://api.steampowered.com"

# Logging setup
handler = logging.FileHandler(filename='.venv/discord.log', encoding='utf-8', mode='w')
logging.basicConfig(level=logging.DEBUG, handlers=[handler])

# Discord intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.messages = True

bot = commands.Bot(command_prefix='/', intents=intents)


@bot.event
async def on_ready():
    print(f'Bot is ready: {bot.user.name}')
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

    # Example responses (you can customize)
    if message.author.name == 'northuoren':
        await channel.send(f'Hello, {message.author}!')
        return

    await bot.process_commands(message)


# ---------- STEAM API COMMANDS ----------

async def resolve_steam_id(steam_id_or_vanity):
    """Resolve vanity URL to SteamID64, or return SteamID64 if already numeric."""
    if steam_id_or_vanity.isdigit():
        return steam_id_or_vanity
    url = f"{STEAM_API_BASE}/ISteamUser/ResolveVanityURL/v1/"
    params = {'key': steam_api_key, 'vanityurl': steam_id_or_vanity}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data['response']['success'] != 1:
            return None
        return data['response']['steamid']
    except Exception:
        return None


@bot.tree.command(name="steam_user", description="Get Steam user information")
async def steam_user(interaction: discord.Interaction, steam_id: str):
    """Fetch Steam user info by SteamID or vanity URL."""
    try:
        steam_id = await resolve_steam_id(steam_id)
        if not steam_id:
            await interaction.response.send_message("Invalid Steam ID or vanity URL.")
            return

        url = f"{STEAM_API_BASE}/ISteamUser/GetPlayerSummaries/v0002/"
        params = {'key': steam_api_key, 'steamids': steam_id}
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        players = data.get('response', {}).get('players', [])
        if not players:
            await interaction.response.send_message("User not found or profile is private.")
            return

        user = players[0]
        embed = discord.Embed(
            title=f"Steam Profile: {user.get('personaname', 'Unknown')}",
            color=0x1b2838
        )
        embed.add_field(name="Steam ID", value=user.get('steamid', 'Unknown'), inline=True)
        embed.add_field(
            name="Profile State",
            value="Public" if user.get('communityvisibilitystate', 1) == 3 else "Private",
            inline=True
        )
        embed.add_field(name="Profile Created", value=user.get('timecreated', 'Unknown'), inline=True)
        embed.add_field(name="Profile URL", value=user.get('profileurl', 'Unknown'), inline=False)
        if 'avatarfull' in user:
            embed.set_thumbnail(url=user['avatarfull'])

        await interaction.response.send_message(embed=embed)

    except Exception as e:
        await interaction.response.send_message(f"Error fetching Steam user data: {str(e)}")


@bot.tree.command(name="steam_games", description="Get user's recently played games")
async def steam_games(interaction: discord.Interaction, steam_id: str):
    """Fetch recently played Steam games by SteamID or vanity URL."""
    try:
        steam_id = await resolve_steam_id(steam_id)
        if not steam_id:
            await interaction.response.send_message("Invalid Steam ID or vanity URL.")
            return

        url = f"{STEAM_API_BASE}/IPlayerService/GetRecentlyPlayedGames/v0001/"
        params = {'key': steam_api_key, 'steamid': steam_id, 'count': 5}
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        games = data.get('response', {}).get('games', [])
        if not games:
            await interaction.response.send_message("No recently played games found or profile is private.")
            return

        embed = discord.Embed(
            title="Recently Played Games",
            color=0x1b2838
        )
        for game in games[:5]:
            total_hours = round(game['playtime_forever'] / 60, 1)
            recent_hours = round(game.get('playtime_2weeks', 0) / 60, 1)
            embed.add_field(
                name=game['name'],
                value=f"Total: {total_hours}h\nRecent: {recent_hours}h",
                inline=True
            )

        await interaction.response.send_message(embed=embed)

    except Exception as e:
        await interaction.response.send_message(f"Error fetching Steam games data: {str(e)}")


@bot.tree.command(name="steam_game_info", description="Get information about a specific game")
async def steam_game_info(interaction: discord.Interaction, app_id: str):
    """Fetch detailed information about a Steam game using AppID."""
    try:
        url = "https://store.steampowered.com/api/appdetails"
        params = {'appids': app_id, 'format': 'json'}
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

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
        embed.add_field(name="Developer", value=", ".join(game.get('developers', [])), inline=True)
        embed.add_field(name="Publisher", value=", ".join(game.get('publishers', [])), inline=True)

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
    """Search for Steam games by name (basic placeholder)."""
    try:
        await interaction.response.send_message(
            f"Searching for '{game_name}' - feature requires Steam search API implementation."
        )
    except Exception as e:
        await interaction.response.send_message(f"Error searching for games: {str(e)}")

@bot.tree.command(name="magicktrick", description="mmnnngh")
async def magicktrick(interaction: discord.Interaction):
    await interaction.response.send_message(f'{interaction.user.name} explode')
# ---------- RUN BOT ----------
bot.run(token, log_handler=handler, log_level=logging.DEBUG)
