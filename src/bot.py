import asyncio
import logging
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from google.generativeai.types.generation_types import StopCandidateException

import time
import discord
import uuid
from discord import app_commands, Color

class CompileQueue:
    def __init__(self, max_concurrent: int = 3, max_queued: int = 20):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._waiting = 0
        self._max_queued = max_queued

    async def execute(self, loop, func, *args, notify_coro=None, timeout=15.0, user_id=None, source="slash", dpi=275):
        if self._waiting >= self._max_queued:
            _safe_record_latex_event(source=source, status="rejected", dpi=dpi, user_id=user_id, error_message="Queue full")
            if notify_coro:
                embed = discord.Embed(
                    title="Server Busy",
                    description="The compile queue is currently full. Please try again in a moment.",
                    color=Color.red(),
                )
                await notify_coro(embed=embed, ephemeral=True)
            return "REJECTED"

        self._waiting += 1
        position = self._waiting
        queued_msg = None
        
        if self._semaphore.locked():
            _safe_record_latex_event(source=source, status="queued", dpi=dpi, user_id=user_id)
            if notify_coro:
                embed = discord.Embed(
                    title="Queued",
                    description=f"You are #{position} in the compile queue. Estimated wait: ~{position * timeout / 3:.0f}s.",
                    color=Color.orange(),
                )
                try:
                    queued_msg = await notify_coro(embed=embed)
                except Exception:
                    pass

        await self._semaphore.acquire()
        self._waiting -= 1

        if queued_msg:
            try:
                await queued_msg.delete()
            except Exception:
                pass

        try:
            return await asyncio.wait_for(
                loop.run_in_executor(executor, func, *args),
                timeout=timeout,
            )
        finally:
            self._semaphore.release()

compile_queue = CompileQueue(max_concurrent=3, max_queued=20)

from discord.ext import commands, tasks
from latex_module import *
from logging_config import configure_logging
from metrics_store import init_metrics_db, record_latex_event
from stats import get_manual_users_count, update_stats

from dotenv import load_dotenv

from AIAPI import create_chat_session, reset_history

load_dotenv()
configure_logging()
logger = logging.getLogger(__name__)
METRICS_DB_PATH = os.getenv(
    "METRICS_DB_PATH",
    str(Path(__file__).resolve().parents[1] / "monitoring" / "data" / "metrics.db"),
)


def _safe_record_latex_event(
    source: str,
    status: str,
    dpi: int | None,
    user_id: int | None,
    error_message: str | None = None,
) -> None:
    try:
        record_latex_event(
            db_path=METRICS_DB_PATH,
            source=source,
            status=status,
            dpi=dpi,
            user_id=user_id,
            error_message=error_message,
        )
    except Exception:
        logger.exception(
            "Failed to record LaTeX metrics source=%s status=%s user_id=%s",
            source,
            status,
            user_id,
        )


def _log_command_success(
    *,
    user_id: int,
    command: str,
    source: str,
    detail: str | None = None,
) -> None:
    if detail:
        logger.info(
            "Request completed user_id=%s source=%s command=%s status=success detail=%s",
            user_id,
            source,
            command,
            detail,
        )
        return

    logger.info(
        "Request completed user_id=%s source=%s command=%s status=success",
        user_id,
        source,
        command,
    )


try:
    init_metrics_db(METRICS_DB_PATH)
    logger.info("Metrics database initialized path=%s", METRICS_DB_PATH)
except Exception:
    logger.exception("Failed to initialize metrics database path=%s", METRICS_DB_PATH)

# Allocate 3 threads to be used concurrently (tuned for Pi 3)
executor = ThreadPoolExecutor(max_workers=3)


def _create_intents():
    default_factory = getattr(discord.Intents, "default", None)
    if callable(default_factory):
        return default_factory()

    all_factory = getattr(discord.Intents, "all", None)
    if callable(all_factory):
        return all_factory()

    return discord.Intents()


intents = _create_intents()
intents.message_content = True
intents.guilds = True
activity = discord.Activity(
    type=discord.ActivityType.playing, name="/help for well, help"
)

# Intents are required for the bot to function properly

bot = commands.Bot(
    command_prefix="/",
    intents=intents,
    # Custom Help command provided
    help_command=None,
    activity=activity,
)


# ==== Rich Presence ====


async def update_presence():
    """
    Updates the bot's rich presence with some information.
    """
    activity = discord.Activity(
        type=discord.ActivityType.playing,
        name="Solo - Competitive Integrating",
        details="Competitive Integrating",
        state="Playing Solo",
        party=(1, 1),
    )
    await bot.change_presence(activity=activity)
    logger.info("Presence updated successfully")


def _collect_user_stats() -> dict[str, int]:
    guilds = list(bot.guilds)
    return {
        "users": len(bot.users),
        "guilds": len(guilds),
        "guild_users": sum((guild.member_count or 0) for guild in guilds),
        "individual_users": get_manual_users_count(),
    }


@tasks.loop(hours=1)
async def update_gist_stats_task():
    stats_snapshot = _collect_user_stats()
    success = await update_stats(**stats_snapshot)
    if success:
        logger.info(
            "Updated user stats gist users=%s guilds=%s guild_users=%s individual_users=%s",
            stats_snapshot["users"],
            stats_snapshot["guilds"],
            stats_snapshot["guild_users"],
            stats_snapshot["individual_users"],
        )
    else:
        logger.warning("Failed to update user stats gist")


@update_gist_stats_task.before_loop
async def before_update_gist_stats_task():
    await bot.wait_until_ready()


# ==== initializer ====


@bot.event
async def on_ready():
    logger.info("Logged in as %s", bot.user)
    try:
        synced = await bot.tree.sync()
        logger.info("Synced %s command(s)", len(synced))
    except Exception:
        logger.exception("Failed to sync command tree")

    await update_presence()

    if not update_gist_stats_task.is_running():
        update_gist_stats_task.start()
        logger.info("Started hourly gist stats updater")

    # Debug Check

    # # Use a set to avoid duplicate users across guilds
    # unique_members = set()
    #
    # # Loop over every guild the bot is in
    # for guild in bot.guilds:
    #     # Loop over every member in the guild
    #     for member in guild.members:
    #         unique_members.add(member)
    #
    # # Print out all unique users
    # print("Users using the bot:")
    # for member in unique_members:
    #     print(f"{member.name}#{member.discriminator} (ID: {member.id})")


# ===== UI Components & Helpers =====


DEFAULT_DPI = 300


class LatexCodeModal(discord.ui.Modal):
    latex_input = discord.ui.TextInput(
        label="LaTeX Code",
        style=discord.TextStyle.long,
        placeholder="Enter your LaTeX code here...",
        required=True,
        max_length=4000,
    )

    def __init__(
        self,
        *,
        original_code: str = "",
        dpi: int = DEFAULT_DPI,
        title: str = "Enter LaTeX Code",
    ):
        super().__init__(title=title)
        # If code prefix from on_message is included, strip it for editor
        if original_code.startswith("latex "):
            self.latex_input.default = original_code[6:]
        else:
            self.latex_input.default = original_code
        self.dpi = dpi

    async def on_submit(self, interaction: discord.Interaction):
        await handle_latex_compilation(
            interaction, self.latex_input.value, self.dpi, source="modal"
        )


class FixCodeView(discord.ui.View):
    def __init__(self, latex_code: str, dpi: int):
        super().__init__(timeout=None)
        self.latex_code = latex_code
        self.dpi = dpi

    @discord.ui.button(label="Fix Code", style=discord.ButtonStyle.danger, emoji="🔧")
    async def fix_code_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        modal = LatexCodeModal(
            original_code=self.latex_code,
            dpi=self.dpi,
            title="Fix LaTeX Code",
        )
        await interaction.response.send_modal(modal)


async def handle_latex_compilation(
    interaction: discord.Interaction, latex_code: str, dpi: int, source: str = "modal"
):
    if not interaction.response.is_done():
        await interaction.response.defer(thinking=True)

    message_id = str(uuid.uuid4())
    unique_id = message_id[7:14]
    loop = asyncio.get_running_loop()

    async def notify_slash(embed, ephemeral=False):
        return await interaction.followup.send(embed=embed, ephemeral=ephemeral, wait=True)

    try:
        output = await compile_queue.execute(
            loop, text_to_latex, latex_code, unique_id, dpi,
            notify_coro=notify_slash, timeout=15.0, user_id=interaction.user.id, source=source, dpi=dpi
        )
        if output == "REJECTED":
            return
    except asyncio.TimeoutError:
        logger.warning(
            "LaTeX compile timeout user_id=%s request_id=%s dpi=%s",
            interaction.user.id,
            unique_id,
            dpi,
        )
        _safe_record_latex_event(
            source=source,
            status="timeout",
            dpi=dpi,
            user_id=interaction.user.id,
            error_message="LaTeX compilation timed out",
        )
        embed = discord.Embed(
            title="Timeout Error",
            description="LaTeX compilation took too long. Please try again later or simplify your LaTeX code.",
            color=Color.red(),
        )
        view = FixCodeView(latex_code, dpi)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        return
    except Exception as exc:
        logger.exception(
            "LaTeX compile internal error user_id=%s request_id=%s dpi=%s",
            interaction.user.id,
            unique_id,
            dpi,
        )
        _safe_record_latex_event(
            source=source,
            status="internal_error",
            dpi=dpi,
            user_id=interaction.user.id,
            error_message=str(exc),
        )
        embed = discord.Embed(
            title="Internal Error",
            description="Unexpected compile error. Please try again in a moment.",
            color=Color.red(),
        )
        view = FixCodeView(latex_code, dpi)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        return

    if output is True:
        logger.debug(
            "LaTeX compile success user_id=%s request_id=%s",
            interaction.user.id,
            unique_id,
        )
        _safe_record_latex_event(
            source=source,
            status="success",
            dpi=dpi,
            user_id=interaction.user.id,
        )
        file = discord.File(f"{unique_id}.png", filename=f"{unique_id}.png")
        embed = discord.Embed(color=Color.blue())
        embed.set_image(url=f"attachment://{unique_id}.png")
        await interaction.followup.send(embed=embed, file=file)
        _log_command_success(
            user_id=interaction.user.id,
            command="latex",
            source=source,
            detail=f"request_id={unique_id}",
        )
        os.remove(f"{unique_id}.png")
    else:
        logger.warning(
            "LaTeX compile failed user_id=%s request_id=%s reason=%s",
            interaction.user.id,
            unique_id,
            str(output),
        )
        _safe_record_latex_event(
            source=source,
            status="compile_error",
            dpi=dpi,
            user_id=interaction.user.id,
            error_message=str(output),
        )
        embed = discord.Embed(
            title="Compilation Error",
            description=f"```yaml\n{output}\n```",
            color=Color.red(),
        )
        view = FixCodeView(latex_code, dpi)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        return


# ===== Commands =====


@bot.tree.command(name="ping")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def ping(interaction: discord.Interaction):
    # noinspection PyUnresolvedReferences
    await interaction.response.send_message("PONGGGGGGG!!!!")
    _log_command_success(user_id=interaction.user.id, command="ping", source="slash")


@bot.tree.command(name="latex", description="Open a modal to enter LaTeX code")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def latex(interaction: discord.Interaction):
    await interaction.response.send_modal(LatexCodeModal(dpi=DEFAULT_DPI))


@bot.tree.command(
    name="latex-inline",
    description="Render single-line LaTeX without opening the modal",
)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def latex_inline(interaction: discord.Interaction, latex_code: str):
    await handle_latex_compilation(
        interaction,
        latex_code,
        DEFAULT_DPI,
        source="inline",
    )


@bot.tree.command(name="help", description="See Features and Commands")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def help(interaction: discord.Interaction):
    name = "LaTeX_Bot"

    embed = discord.Embed(
        title="Help! - Commands and Features",
        description="Hello!, I'm LaTeX Bot. I can compile your LaTeX code in discord. \n"
        "Use '/latex' to open a modal editor for your code "
        "or type latex followed by latex code (server only)",
        color=Color.orange(),
    )
    embed.set_author(name=name)

    embed.add_field(
        name="Commands",
        value="```"
        "/help                         To well get help\n\n"
        "/latex                        Open the LaTeX editor modal\n\n"
        "/latex-inline                 Single-line slash command input\n\n"
        "/talk-to-me                   Talk to me\n\n"
        "/ping                         See if I'm awake!\n\n"
        "latex {$$ latex code $$}      Without Slash Commands!\n\n"
        "```",
        inline=False,
    )

    embed.add_field(
        name="Tips",
        value=r"""To get a past message press up arrow on your keyboard ↑. 
                                       A preamble is only needed if using a Tikz package otherwise 
                                       a basic structure is added by default. Missing math delimiters 
                                       are auto-added as \\[...\\] when needed.""",
    )
    embed.set_footer(text=f"created by {name}")
    # noinspection PyUnresolvedReferences
    await interaction.response.send_message(embed=embed, ephemeral=False, silent=True)
    _log_command_success(user_id=interaction.user.id, command="help", source="slash")


# =========AI======== Features
#
@bot.tree.command(name="talk-to-me", description="LaTeX Bot Sentience")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def ai_chat(interaction: discord.Interaction, user_message: str):
    # noinspection PyUnresolvedReferences
    await interaction.response.defer(thinking=True)

    loop = asyncio.get_running_loop()
    user_id = interaction.user.id

    try:
        output = await asyncio.wait_for(
            loop.run_in_executor(executor, create_chat_session, user_message, user_id),
            timeout=15.0,
        )

    except asyncio.TimeoutError:
        logger.warning("AI timeout user_id=%s", user_id)
        embed = discord.Embed(
            title="Timeout Error",
            description="AI response took too long. Please try again.",
            color=discord.Color.red(),
        )
        # Don't let a followup failure keep this coroutine hanging.
        await asyncio.wait_for(
            interaction.followup.send(embed=embed, ephemeral=True), timeout=5.0
        )
        return

    except StopCandidateException as e:
        logger.warning("AI safety filters triggered user_id=%s err=%s", user_id, e)
        # Handle safety exceptions (like when the safety filters trigger).
        embed = discord.Embed(
            title="Safety Exception",
            description=f"Safety filters triggered",
            color=discord.Color.red(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    if output == "History cleared":
        embed = discord.Embed(
            color=discord.Color.red(),
            title="Memory Automatically cleared - My Memory is Full!",
        )
        await interaction.followup.send(embed=embed)
        _log_command_success(
            user_id=user_id,
            command="talk-to-me",
            source="slash",
            detail="history_auto_cleared",
        )
        return

    embed = discord.Embed(
        title="Response" + ":woman_with_probing_cane: ",
        color=discord.Color.green(),
        description=output[:4096],
    ).set_author(name="LaTeX Bot")

    # 1024 is Max limit

    embed.add_field(name="Message", value=user_message[:1024], inline=False)

    await interaction.followup.send(embed=embed)
    _log_command_success(user_id=user_id, command="talk-to-me", source="slash")


@bot.tree.command(name="clear-history", description="clears chat history")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def clear_history(interaction: discord.Interaction):
    user_id = interaction.user.id
    embed = discord.Embed(
        color=discord.Color.red(),
        title=reset_history(user_id),
    )
    # noinspection PyUnresolvedReferences
    await interaction.response.send_message(embed=embed)
    _log_command_success(
        user_id=user_id,
        command="clear-history",
        source="slash",
    )


# ===== EVENTS =====
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if message.content.startswith("latex"):
        latex_code = message.content
        channel = message.channel
        message_id = str(message.id)
        unique_id = message_id[7:14]

        loop = asyncio.get_running_loop()

        async def notify_legacy(embed, ephemeral=False):
            return await channel.send(embed=embed, silent=True)

        # Set a timeout of 15 seconds
        try:
            output = await compile_queue.execute(
                loop, text_to_latex, latex_code, unique_id, 275,
                notify_coro=notify_legacy, timeout=15.0, user_id=message.author.id, source="legacy", dpi=275
            )
            if output == "REJECTED":
                return
        except asyncio.TimeoutError:
            logger.warning(
                "Legacy latex timeout author_id=%s request_id=%s",
                message.author.id,
                unique_id,
            )
            _safe_record_latex_event(
                source="legacy",
                status="timeout",
                dpi=275,
                user_id=message.author.id,
                error_message="LaTeX compilation timed out",
            )
            # Handle the timeout case
            embed = discord.Embed(
                title="Timeout Error",
                description="LaTeX compilation took too long. Please try again later or simplify your LaTeX code.",
                color=Color.red(),
            )
            view = FixCodeView(latex_code, 275)
            await channel.send(embed=embed, view=view, silent=True)
            return
        except Exception as exc:
            logger.exception(
                "Legacy latex internal error author_id=%s request_id=%s",
                message.author.id,
                unique_id,
            )
            _safe_record_latex_event(
                source="legacy",
                status="internal_error",
                dpi=275,
                user_id=message.author.id,
                error_message=str(exc),
            )
            embed = discord.Embed(
                title="Internal Error",
                description="Unexpected compile error. Please try again in a moment.",
                color=Color.red(),
            )
            view = FixCodeView(latex_code, 275)
            await channel.send(embed=embed, view=view, silent=True)
            return

        if output is True:
            logger.debug(
                "Legacy latex compile success author_id=%s request_id=%s",
                message.author.id,
                unique_id,
            )
            _safe_record_latex_event(
                source="legacy",
                status="success",
                dpi=275,
                user_id=message.author.id,
            )
            file = discord.File(f"{unique_id}.png", filename=f"{unique_id}.png")
            embed = discord.Embed(color=Color.blue())
            embed.set_image(url=f"attachment://{unique_id}.png")
            await channel.send(embed=embed, file=file)
            _log_command_success(
                user_id=message.author.id,
                command="latex",
                source="legacy",
                detail=f"request_id={unique_id}",
            )
            # remove extra files after
            os.remove(f"{unique_id}.png")
        else:
            logger.warning(
                "Legacy latex compile failed author_id=%s request_id=%s reason=%s",
                message.author.id,
                unique_id,
                str(output),
            )
            _safe_record_latex_event(
                source="legacy",
                status="compile_error",
                dpi=275,
                user_id=message.author.id,
                error_message=str(output),
            )
            embed = discord.Embed(
                title="Compilation Error",
                description=f"```yaml\n{output}\n```",
                color=Color.red(),
            )
            view = FixCodeView(latex_code, 275)
            await channel.send(embed=embed, view=view, silent=True)
            return
    # must be used to process commands else they are overwritten by on_message
    await bot.process_commands(message)

if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_TOKEN"))
