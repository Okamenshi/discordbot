import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
from openai import OpenAI

load_dotenv()
token = os.getenv('DISCORD_TOKEN')


client_openai = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

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


# ChatGPT slash command
@bot.tree.command(name="chatgpt", description="Ask ChatGPT a question")
async def chatgpt_command(interaction: discord.Interaction, question: str):

    await interaction.response.defer()

    try:
        response = client_openai.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "user", "content": question}
            ],
        )

        # Get the response content
        answer = response.choices[0].message.content

        # Discord has a 2000 character limit for messages
        if len(answer) > 2000:
            # Split into multiple messages if needed
            chunks = [answer[i:i + 2000] for i in range(0, len(answer), 2000)]
            await interaction.followup.send(chunks[0])
            for chunk in chunks[1:]:
                await interaction.followup.send(chunk)
        else:
            await interaction.followup.send(answer)

    except Exception as e:
        await interaction.followup.send(f"Sorry, I encountered an error: {str(e)}")



@bot.command(name='ask')
async def ask_chatgpt(ctx, *, question):
    """Regular command version: /ask your question here"""
    try:
        async with ctx.typing():
            response = client_openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "user", "content": question}
                ],
                max_tokens=1000,
                temperature=0.7
            )

            answer = response.choices[0].message.content

            if len(answer) > 2000:
                chunks = [answer[i:i + 2000] for i in range(0, len(answer), 2000)]
                await ctx.send(chunks[0])
                for chunk in chunks[1:]:
                    await ctx.send(chunk)
            else:
                await ctx.send(answer)

    except Exception as e:
        await ctx.send(f"Error: {str(e)}")


bot.run(token, log_handler=handler, log_level=logging.DEBUG)