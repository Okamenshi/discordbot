import discord
from discord.ext import commands
import logging
import os
import requests
import pymysql



# ---------- ENVIRONMENT VARIABLES ----------
token = os.getenv('DISCORD_TOKEN')
steam_api_key = os.getenv('STEAM_API_KEY')
STEAM_API_BASE = "https://api.steampowered.com"

# db setup

try:
    connection = pymysql.connect(
        host=os.getenv('MYSQLHOST'),
        port=int(os.getenv('MYSQLPORT')),
        user=os.getenv('MYSQLUSER'),
        password=os.getenv('MYSQLPASSWORD'),
        db=os.getenv('DATABASE_URL'),
    )
    print("Connection established")
    connection.close()
    print("Connection closed")
except Exception as e:
    print(e)


# ---------- LOGGING ----------
handler = logging.FileHandler(filename='.venv/discord.log', encoding='utf-8', mode='w')
logging.basicConfig(level=logging.DEBUG, handlers=[handler])

# ---------- DISCORD BOT SETUP ----------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.messages = True
bot = commands.Bot(command_prefix='/', intents=intents)

# ---------- HELPER FUNCTIONS ----------
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

# ---------- EVENTS ----------
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands")

        # List the synced commands
        for command in synced:
            print(f"  - /{command.name}: {command.description}")

    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")
    print(f'Bot is ready: {bot.user.name}')
    # Resume tracking users from DB

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    await bot.process_commands(message)

# ---------- COMMANDS ----------


@bot.tree.command(name="steam_user", description="Get Steam user information")
async def steam_user(interaction: discord.Interaction, steam_id: str):
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
        embed = discord.Embed(title="Recently Played Games", color=0x1b2838)
        for game in games[:5]:
            total_hours = round(game['playtime_forever'] / 60, 1)
            recent_hours = round(game.get('playtime_2weeks', 0)/60, 1)
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

# ---------- FUN COMMAND ----------

@bot.tree.command(name="thickofit", description="Im in the thick of it")
async def thickofit(interaction: discord.Interaction, user: discord.Member):
    name = user.name
    await interaction.response.send_message(f"Im in the thick of it {name} knows they know me where it snows i {name} in and they froze i dont know no nothing bout no {name} im just cold 40 something milly ive been told ")

@bot.tree.command(name="magicktrick", description="mmnnngh")
async def magicktrick(interaction: discord.Interaction):
    await interaction.response.send_message(f'{interaction.user.name} explode')

@bot.tree.command(name="balls")
async def balls(interaction: discord.Interaction, user: discord.Member):
    name = user.name
    await interaction.response.send_message(f"Okay! taking {name}'s balls")

# ---------- RUN BOT ----------
bot.run(token, log_handler=handler, log_level=logging.DEBUG)
