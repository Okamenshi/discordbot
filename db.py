import discord
import mysql.connector
from mysql.connector import pooling, Error
from discord.ext import commands
import os
from dotenv import load_dotenv
import logging
from urllib.parse import urlparse

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_database_url(database_url):
    """Parse Railway's MySQL connection string"""
    if not database_url:
        return None

    try:
        parsed = urlparse(database_url)
        return {
            'host': parsed.hostname,
            'port': parsed.port or 3306,
            'user': parsed.username,
            'password': parsed.password,
            'database': parsed.path.lstrip('/') if parsed.path else 'railway'
        }
    except Exception as e:
        logger.error(f"Error parsing database URL: {e}")
        return None


class DatabaseManager:
    def __init__(self):
        self.pool = None
        self.create_connection_pool()
        self.create_tables()

    def create_connection_pool(self):
        """Create MySQL connection pool using Railway connection string"""
        try:
            # Try to use connection string first
            database_url = os.getenv('DATABASE_URL') or os.getenv('MYSQL_PUBLIC_URL') or os.getenv('MYSQL_URL')

            if database_url:
                logger.info("Using Railway connection string...")
                db_config = parse_database_url(database_url)
                if not db_config:
                    raise ValueError("Could not parse database URL")
            else:
                # Fallback to individual environment variables
                logger.info("Using individual environment variables...")
                db_config = {
                    'host': os.getenv('DB_HOST'),
                    'port': int(os.getenv('DB_PORT', 3306)),
                    'user': os.getenv('DB_USER'),
                    'password': os.getenv('DB_PASSWORD'),
                    'database': os.getenv('DB_NAME', 'railway')
                }

            config = {
                **db_config,
                'pool_name': 'discord_bot_pool',
                'pool_size': 3,
                'pool_reset_session': True,
                'autocommit': True,
                'connect_timeout': 30,
                'sql_mode': 'TRADITIONAL'
            }

            # Remove None values
            config = {k: v for k, v in config.items() if v is not None}

            logger.info(f"Connecting to Railway MySQL: {config['host']}:{config['port']}")
            logger.info(f"Database: {config['database']}, User: {config['user']}")

            self.pool = pooling.MySQLConnectionPool(**config)
            logger.info("✅ Railway MySQL connection pool created successfully")

        except Exception as e:
            logger.error(f"❌ Error creating connection pool: {e}")
            logger.error("Railway connection troubleshooting:")
            logger.error("1. Check your DATABASE_URL or MYSQL_PUBLIC_URL in .env")
            logger.error("2. Verify your Railway database is running")
            logger.error("3. Make sure your Railway service has public networking enabled")
            raise

    def get_connection(self):
        """Get connection from pool"""
        try:
            return self.pool.get_connection()
        except Error as e:
            logger.error(f"Error getting connection from pool: {e}")
            raise

    def execute_query(self, query, params=None):
        """Execute SELECT query and return results"""
        connection = None
        try:
            connection = self.get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, params or ())
            result = cursor.fetchall()
            return result

        except Error as e:
            logger.error(f"Database query error: {e}")
            return None

        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()

    def execute_update(self, query, params=None):
        """Execute INSERT/UPDATE/DELETE query"""
        connection = None
        try:
            connection = self.get_connection()
            cursor = connection.cursor()
            cursor.execute(query, params or ())
            affected_rows = cursor.rowcount
            return affected_rows

        except Error as e:
            logger.error(f"Database update error: {e}")
            return 0

        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()

    def create_tables(self):
        """Create necessary tables"""
        tables = {
            'users': """
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username VARCHAR(255) NOT NULL,
                    display_name VARCHAR(255),
                    points INT DEFAULT 0,
                    level INT DEFAULT 1,
                    experience INT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """,
            'guilds': """
                CREATE TABLE IF NOT EXISTS guilds (
                    guild_id BIGINT PRIMARY KEY,
                    guild_name VARCHAR(255) NOT NULL,
                    prefix VARCHAR(10) DEFAULT '!',
                    welcome_channel BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """,
            'user_activity': """
                CREATE TABLE IF NOT EXISTS user_activity (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT,
                    guild_id BIGINT,
                    activity_type VARCHAR(50),
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """
        }

        for table_name, create_query in tables.items():
            try:
                self.execute_update(create_query)
                logger.info(f"Table '{table_name}' created/verified successfully")
            except Exception as e:
                logger.error(f"Error creating table '{table_name}': {e}")


async def store_all_members():
    """Store all members from all guilds in the database"""
    total_stored = 0

    for guild in bot.guilds:
        # Store guild info
        db.execute_update(
            "INSERT IGNORE INTO guilds (guild_id, guild_name) VALUES (%s, %s)",
            (guild.id, guild.name)
        )

        # Store all members
        for member in guild.members:
            if not member.bot:  # Skip bot accounts
                result = db.execute_update(
                    """INSERT IGNORE INTO users (user_id, username, display_name) 
                       VALUES (%s, %s, %s)""",
                    (member.id, str(member), member.display_name)
                )
                if result > 0:
                    total_stored += 1

    logger.info(f"Stored {total_stored} new members in database")
    print(f"Stored {total_stored} new members in database")


# Initialize database manager
db = DatabaseManager()

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)


@bot.event
async def on_ready():
    logger.info(f'{bot.user} has connected to Discord!')
    print(f'{bot.user} has connected to Discord!')

    # Store all existing members from all guilds
    await store_all_members()


@bot.event
async def on_guild_join(guild):
    """Register guild when bot joins"""
    db.execute_update(
        "INSERT IGNORE INTO guilds (guild_id, guild_name) VALUES (%s, %s)",
        (guild.id, guild.name)
    )


@bot.event
async def on_member_join(member):
    """Register new member"""
    if not member.bot:
        db.execute_update(
            """INSERT IGNORE INTO users (user_id, username, display_name) 
               VALUES (%s, %s, %s)""",
            (member.id, str(member), member.display_name)
        )
        logger.info(f"New member stored: {member} ({member.id})")


@bot.event
async def on_member_update(before, after):
    """Update member info when they change their name/display name"""
    if not after.bot:
        if before.name != after.name or before.display_name != after.display_name:
            db.execute_update(
                """INSERT INTO users (user_id, username, display_name) 
                   VALUES (%s, %s, %s)
                   ON DUPLICATE KEY UPDATE 
                   username = VALUES(username),
                   display_name = VALUES(display_name)""",
                (after.id, str(after), after.display_name)
            )
            logger.info(f"Updated member info: {after} ({after.id})")


@bot.event
async def on_user_update(before, after):
    """Update user info when they change their global username"""
    if not after.bot:
        if before.name != after.name:
            db.execute_update(
                """UPDATE users SET username = %s WHERE user_id = %s""",
                (str(after), after.id)
            )
            logger.info(f"Updated username: {before.name} -> {after.name} ({after.id})")


# User Commands
@bot.command(name='profile')
async def user_profile(ctx, user: discord.Member = None):
    """Display user profile"""
    target_user = user or ctx.author

    result = db.execute_query(
        "SELECT * FROM users WHERE user_id = %s",
        (target_user.id,)
    )

    if not result:
        db.execute_update(
            """INSERT INTO users (user_id, username, display_name) 
               VALUES (%s, %s, %s)""",
            (target_user.id, str(target_user), target_user.display_name)
        )

        result = db.execute_query(
            "SELECT * FROM users WHERE user_id = %s",
            (target_user.id,)
        )

    user_data = result[0]

    embed = discord.Embed(
        title=f"{target_user.display_name}'s Profile",
        color=discord.Color.blue()
    )
    embed.add_field(name="Points", value=user_data['points'], inline=True)
    embed.add_field(name="Level", value=user_data['level'], inline=True)
    embed.add_field(name="Experience", value=user_data['experience'], inline=True)
    embed.add_field(name="Joined", value=user_data['created_at'].strftime("%Y-%m-%d"), inline=True)
    embed.set_thumbnail(url=target_user.avatar.url if target_user.avatar else None)

    await ctx.send(embed=embed)


@bot.command(name='addpoints')
@commands.has_permissions(administrator=True)
async def add_points(ctx, user: discord.Member, amount: int):
    """Add points to a user (Admin only)"""
    existing = db.execute_query(
        "SELECT user_id FROM users WHERE user_id = %s",
        (user.id,)
    )

    if not existing:
        db.execute_update(
            """INSERT INTO users (user_id, username, display_name) 
               VALUES (%s, %s, %s)""",
            (user.id, str(user), user.display_name)
        )

    rows_affected = db.execute_update(
        "UPDATE users SET points = points + %s WHERE user_id = %s",
        (amount, user.id)
    )

    if rows_affected > 0:
        db.execute_update(
            """INSERT INTO user_activity (user_id, guild_id, activity_type) 
               VALUES (%s, %s, %s)""",
            (user.id, ctx.guild.id, f'points_added_{amount}')
        )

        embed = discord.Embed(
            description=f"✅ Added {amount} points to {user.mention}!",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Failed to add points.")


@bot.command(name='leaderboard', aliases=['lb', 'top'])
async def leaderboard(ctx, limit: int = 10):
    """Show points leaderboard"""
    if limit > 20:
        limit = 20

    results = db.execute_query(
        """SELECT user_id, username, points, level 
           FROM users 
           ORDER BY points DESC 
           LIMIT %s""",
        (limit,)
    )

    if not results:
        await ctx.send("No users found in the database.")
        return

    embed = discord.Embed(
        title="🏆 Leaderboard",
        color=discord.Color.gold()
    )

    description = ""
    for i, user_data in enumerate(results, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        description += f"{medal} **{user_data['username']}** - {user_data['points']} points\n"

    embed.description = description
    await ctx.send(embed=embed)


@bot.command(name='dbstats')
@commands.has_permissions(administrator=True)
async def database_stats(ctx):
    """Show database statistics (Admin only)"""
    stats = {}

    result = db.execute_query("SELECT COUNT(*) as count FROM users")
    stats['users'] = result[0]['count'] if result else 0

    result = db.execute_query("SELECT COUNT(*) as count FROM guilds")
    stats['guilds'] = result[0]['count'] if result else 0

    result = db.execute_query("SELECT SUM(points) as total FROM users")
    stats['total_points'] = result[0]['total'] if result and result[0]['total'] else 0

    result = db.execute_query("SELECT COUNT(*) as count FROM users WHERE points > 0")
    stats['active_users'] = result[0]['count'] if result else 0

    embed = discord.Embed(
        title="📊 Database Statistics",
        color=discord.Color.purple()
    )
    embed.add_field(name="Total Users", value=stats['users'], inline=True)
    embed.add_field(name="Active Users", value=stats['active_users'], inline=True)
    embed.add_field(name="Total Guilds", value=stats['guilds'], inline=True)
    embed.add_field(name="Total Points", value=stats['total_points'], inline=False)

    await ctx.send(embed=embed)


# Error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Invalid argument provided.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Missing required argument.")
    else:
        logger.error(f"Unhandled error: {error}")
        await ctx.send("❌ An unexpected error occurred.")


# Run the bot
if __name__ == "__main__":
    bot.run(os.getenv('DISCORD_TOKEN'))