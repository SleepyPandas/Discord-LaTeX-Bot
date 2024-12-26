import os
import discord
import uuid
from discord import app_commands

from latex_module import *
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
intents = discord.Intents.all()
intents.message_content = True

# Intents are required for the bot to function properly
# Set up the bot with a prefix

# bot = commands.Bot(command_prefix="/", intents=intents)
client = commands.Bot(command_prefix="/", intents=intents, help_command=None)


@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')
    await client.tree.sync()


# ===== Commands =====/

@client.tree.command(name="hello", description='test')
@app_commands.user_install()
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def hello(interaction: discord.Interaction):
    # noinspection PyUnresolvedReferences
    await interaction.response.send_message("Hello World!")


# noinspection PyUnresolvedReferences
@client.tree.command(name="latex", description='test')
@app_commands.user_install()
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def latex(interaction: discord.Interaction, what: str):
    # noinspection PyUnresolvedReferences

    message_content = what
    message_id = str(uuid.uuid4())
    unique_id = message_id[7:14]

    if text_to_latex(message_content, unique_id) is True:
        await interaction.response.send_message(file=discord.File(f'{unique_id}.png'), silent=True)
        # remove extra files after
        os.remove(f'{unique_id}.png')
    else:
        await interaction.response.send_message("`❌ Failed : Check syntax or formatting`", ephemeral=True, silent=True)
        return


# noinspection PyUnresolvedReferences
@client.tree.command(name="help", description='test')
@app_commands.user_install()
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def _help(interaction: discord.Interaction):
    help_text = (">>>"
                 "Hello! I'm LaTeX Bot 🤖. I can convert your LaTeX code into PNG images"
                 "To use me type 'latex' followed by your LaTeX code.")
    await interaction.response.send_message(help_text, ephemeral=True, silent=True)


@client.command(name='help')
async def _help(ctx):
    help_text = (">>>"
                 "Hello! I'm LaTeX Bot 🤖. I can convert your LaTeX code into PNG images"
                 "To use me type 'latex' followed by your LaTeX code.")
    await ctx.send(help_text)


# ===== EVENTS =====
@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if message.content.startswith("latex") or message.content.startswith("```latex"):

        message_content = message.content
        channel = message.channel
        message_id = str(message.id)
        unique_id = message_id[7:14]

        if text_to_latex(message_content, unique_id) is True:
            await channel.send(file=discord.File(f'{unique_id}.png'))
            # remove extra files after
            os.remove(f'{unique_id}.png')
        else:
            await channel.send("` ❌ Failed : Check syntax or formatting`")

            return
    # must be used to process commands else they are overwritten by on_message
    await client.process_commands(message)


client.run(os.getenv('DISCORD_TOKEN'))
