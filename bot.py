import os
import discord
import uuid
from discord import app_commands
from discord import Color
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
@client.tree.command(name="latex", description='Complies Latex Code ~ in standalone Class')
@app_commands.user_install()
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def latex(interaction: discord.Interaction, latex_code: str):
    # noinspection PyUnresolvedReferences

    message_content = latex_code
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
@client.tree.command(name="help", description='See Features and Commands')
@app_commands.user_install()
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def help(interaction: discord.Interaction):
    name = "laTeX_Bot"
    pfp = None

    embed = discord.Embed(title="Help!", description="Commands and Features", color=Color.orange())
    embed.set_author(name=name)
    embed.set_thumbnail(url=pfp)
    embed.add_field(name="", value="Hello!,  I'm LaTeX Bot 🤖. I can convert your LaTeX code "
                                   "into PNG images To use me type 'latex' followed by your LaTeX code.")

    embed.set_footer(text=f"created by {name}")
    await interaction.response.send_message(embed=embed, ephemeral=False, silent=True)


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
