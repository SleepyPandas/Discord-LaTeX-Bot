import asyncio
import os

import discord

from latex_module import *
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

# Intents are required for the bot to function properly

# Set up the bot with a prefix

bot = commands.Bot(command_prefix="?", intents=intents, help_command=None)


# MTI0MjU3MzMxNzY5MzY0MDc4OA.GIYgEU.ezkoFPrAMlCP3lgibcA3okITW7qE7nrHXmxiZQ
# TODO : Remove API key Above

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')


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
            os.remove(f'{unique_id}.png')
        else:
            await channel.send("` ❌ Failed : Check syntax or formatting`")

            return


@bot.command()
async def help(ctx):
    help_text = ("Hello! I'm LaTeX Bot 🤖. I can convert your LaTeX code into PNG images"
                 "To use me type 'latex' followed by your LaTeX code.")
    await ctx.send(help_text)


client.run('MTI0MjU3MzMxNzY5MzY0MDc4OA.GIYgEU.ezkoFPrAMlCP3lgibcA3okITW7qE7nrHXmxiZQ')
