import asyncio
import importlib
import os
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def _install_bot_import_stubs() -> None:
    google_module = types.ModuleType("google")
    generativeai_module = types.ModuleType("google.generativeai")
    types_module = types.ModuleType("google.generativeai.types")
    generation_types_module = types.ModuleType("google.generativeai.types.generation_types")
    generation_types_module.StopCandidateException = type(
        "StopCandidateException", (Exception,), {}
    )

    dotenv_module = types.ModuleType("dotenv")
    dotenv_module.load_dotenv = lambda: None

    logging_config_module = types.ModuleType("logging_config")
    logging_config_module.configure_logging = lambda: None

    latex_module_stub = types.ModuleType("latex_module")
    latex_module_stub.text_to_latex = lambda *args, **kwargs: True
    latex_module_stub.MAX_LATEX_INPUT_CHARS = 3000

    metrics_store_module = types.ModuleType("metrics_store")
    metrics_store_module.init_metrics_db = lambda *args, **kwargs: None
    metrics_store_module.record_latex_event = lambda *args, **kwargs: None

    aiapi_module = types.ModuleType("AIAPI")
    aiapi_module.create_chat_session = lambda *args, **kwargs: "stub"
    aiapi_module.reset_history = lambda *args, **kwargs: "cleared"

    discord_module = types.ModuleType("discord")

    class DummyTextInput:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.default = ""
            self.value = ""

    class DummyModal:
        def __init__(self, *, title=None):
            self.title = title

    class DummyView:
        def __init__(self, *, timeout=None):
            self.timeout = timeout

    class DummyButtonStyle:
        danger = "danger"

    class DummyTextStyle:
        long = "long"

    class DummyColor:
        @staticmethod
        def red():
            return "red"

        @staticmethod
        def blue():
            return "blue"

        @staticmethod
        def orange():
            return "orange"

        @staticmethod
        def green():
            return "green"

    class DummyActivityType:
        playing = "playing"

    class DummyActivity:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class DummyIntents:
        def __init__(self):
            self.message_content = False

        @staticmethod
        def all():
            return DummyIntents()

    class DummyEmbed:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            self.fields = []

        def set_image(self, **kwargs):
            self.image_kwargs = kwargs
            return self

        def set_author(self, **kwargs):
            self.author_kwargs = kwargs
            return self

        def add_field(self, **kwargs):
            self.fields.append(kwargs)
            return self

        def set_footer(self, **kwargs):
            return self

    class DummyFile:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    def dummy_button(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

    class DummyTree:
        def command(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        async def sync(self):
            return []

    class DummyLoop:
        def __init__(self, coro):
            self.coro = coro
            self._running = False
            self._before_loop = None

        def before_loop(self, func):
            self._before_loop = func
            return func

        def start(self):
            self._running = True

        def is_running(self):
            return self._running

    def dummy_loop(*args, **kwargs):
        def decorator(func):
            return DummyLoop(func)

        return decorator

    class DummyBot:
        def __init__(self, *args, **kwargs):
            self.tree = DummyTree()
            self.user = "stub-bot"
            self.guilds = []
            self.users = []

        def event(self, func):
            return func

        async def change_presence(self, *args, **kwargs):
            return None

        async def process_commands(self, *args, **kwargs):
            return None

        async def wait_until_ready(self):
            return None

        def run(self, *args, **kwargs):
            return None

    app_commands_module = types.SimpleNamespace(
        allowed_contexts=lambda **kwargs: (lambda func: func),
        allowed_installs=lambda **kwargs: (lambda func: func),
    )

    ui_module = types.SimpleNamespace(
        Modal=DummyModal,
        View=DummyView,
        TextInput=DummyTextInput,
        button=dummy_button,
        Button=object,
    )

    discord_module.ui = ui_module
    discord_module.TextStyle = DummyTextStyle
    discord_module.ButtonStyle = DummyButtonStyle
    discord_module.ActivityType = DummyActivityType
    discord_module.Activity = DummyActivity
    discord_module.Intents = DummyIntents
    discord_module.Color = DummyColor
    discord_module.Embed = DummyEmbed
    discord_module.File = DummyFile
    discord_module.Interaction = object
    discord_module.app_commands = app_commands_module

    ext_module = types.ModuleType("discord.ext")
    commands_module = types.ModuleType("discord.ext.commands")
    tasks_module = types.ModuleType("discord.ext.tasks")
    commands_module.Bot = DummyBot
    tasks_module.loop = dummy_loop

    sys.modules["google"] = google_module
    sys.modules["google.generativeai"] = generativeai_module
    sys.modules["google.generativeai.types"] = types_module
    sys.modules["google.generativeai.types.generation_types"] = generation_types_module
    sys.modules["dotenv"] = dotenv_module
    sys.modules["logging_config"] = logging_config_module
    sys.modules["latex_module"] = latex_module_stub
    sys.modules["metrics_store"] = metrics_store_module
    sys.modules["AIAPI"] = aiapi_module
    sys.modules["discord"] = discord_module
    sys.modules["discord.ext"] = ext_module
    sys.modules["discord.ext.commands"] = commands_module
    sys.modules["discord.ext.tasks"] = tasks_module


def _import_bot_module(
    *,
    env_overrides: dict[str, str] | None = None,
    env_removals: tuple[str, ...] = (),
):
    _install_bot_import_stubs()
    sys.modules.pop("bot", None)
    patched_env = dict(os.environ)
    for key in env_removals:
        patched_env.pop(key, None)
    if env_overrides:
        patched_env.update(env_overrides)

    with patch.dict(os.environ, patched_env, clear=True):
        return importlib.import_module("bot")


class BotModalFlowTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bot = _import_bot_module(
            env_removals=("LATEX_COMPILE_CONCURRENCY", "LATEX_MAX_QUEUE")
        )

    @classmethod
    def tearDownClass(cls):
        cls.bot.executor.shutdown(wait=False, cancel_futures=True)

    def test_latex_command_opens_entry_modal_with_default_dpi(self):
        interaction = SimpleNamespace(response=SimpleNamespace(send_modal=AsyncMock()))

        asyncio.run(self.bot.latex(interaction))

        interaction.response.send_modal.assert_awaited_once()
        modal = interaction.response.send_modal.await_args.args[0]
        self.assertIsInstance(modal, self.bot.LatexCodeModal)
        self.assertEqual(modal.dpi, self.bot.DEFAULT_DPI)
        self.assertEqual(modal.title, "Enter LaTeX Code")
        self.assertEqual(modal.latex_input.default, "")
        self.assertEqual(
            modal.latex_input.kwargs["max_length"],
            self.bot.DISCORD_MODAL_LATEX_INPUT_CHARS,
        )

    def test_format_compile_error_description_returns_plain_text_for_friendly_errors(self):
        message = "Input too long: Max is 3000 characters."

        result = self.bot._format_compile_error_description(message)

        self.assertEqual(result, message)

    def test_format_compile_error_description_wraps_technical_errors_in_code_block(self):
        message = "Internal compiler failure"

        result = self.bot._format_compile_error_description(message)

        self.assertEqual(result, "```yaml\nInternal compiler failure\n```")

    def test_format_compile_error_description_keeps_friendly_latex_errors_plain_text(self):
        message = "LaTeX syntax error (line 1): Missing `}` to finish `\\frac{...}{...}`."

        result = self.bot._format_compile_error_description(message)

        self.assertEqual(result, message)

    def test_modal_submit_routes_to_existing_compile_handler(self):
        interaction = SimpleNamespace()
        modal = self.bot.LatexCodeModal(original_code="", dpi=300)
        modal.latex_input.value = r"\frac{1}{2}"

        with patch.object(
            self.bot, "handle_latex_compilation", new=AsyncMock()
        ) as mock_handler:
            asyncio.run(modal.on_submit(interaction))

        mock_handler.assert_awaited_once_with(
            interaction, r"\frac{1}{2}", 300, source="modal"
        )

    def test_latex_inline_command_routes_to_compile_handler(self):
        interaction = SimpleNamespace()

        with patch.object(
            self.bot, "handle_latex_compilation", new=AsyncMock()
        ) as mock_handler:
            asyncio.run(self.bot.latex_inline(interaction, r"\alpha+\beta"))

        mock_handler.assert_awaited_once_with(
            interaction, r"\alpha+\beta", self.bot.DEFAULT_DPI, source="inline"
        )

    def test_fix_code_button_opens_prefilled_modal(self):
        view = self.bot.FixCodeView("latex \\alpha + \\beta", 350)
        interaction = SimpleNamespace(response=SimpleNamespace(send_modal=AsyncMock()))

        asyncio.run(view.fix_code_button(interaction, object()))

        interaction.response.send_modal.assert_awaited_once()
        modal = interaction.response.send_modal.await_args.args[0]
        self.assertIsInstance(modal, self.bot.LatexCodeModal)
        self.assertEqual(modal.title, "Fix LaTeX Code")
        self.assertEqual(modal.dpi, 350)
        self.assertEqual(modal.latex_input.default, r"\alpha + \beta")

    def test_help_command_describes_modal_first_latex_flow(self):
        interaction = SimpleNamespace(
            user=SimpleNamespace(id=123),
            response=SimpleNamespace(send_message=AsyncMock()),
        )

        asyncio.run(self.bot.help(interaction))

        interaction.response.send_message.assert_awaited_once()
        embed = interaction.response.send_message.await_args.kwargs["embed"]
        self.assertIn("open a modal editor", embed.kwargs["description"])
        self.assertIn(
            "/latex                        Open the LaTeX editor modal",
            embed.fields[0]["value"],
        )
        self.assertIn(
            "/latex-inline                 Single-line slash command input",
            embed.fields[0]["value"],
        )

    def test_collect_user_stats_includes_manual_users_value(self):
        self.bot.bot.guilds = [
            SimpleNamespace(member_count=5),
            SimpleNamespace(member_count=None),
            SimpleNamespace(member_count=7),
        ]
        self.bot.bot.users = [1, 2, 3, 4]

        with patch.object(self.bot, "get_manual_users_count", return_value=13):
            snapshot = self.bot._collect_user_stats()

        self.assertEqual(
            snapshot,
            {
                "users": 25,
                "guilds": 3,
                "guild_users": 12,
                "individual_users": 13,
            },
        )

    def test_on_ready_starts_hourly_task_once(self):
        sync_mock = AsyncMock(return_value=[])
        update_presence_mock = AsyncMock()
        task_mock = SimpleNamespace(
            is_running=Mock(side_effect=[False, True]),
            start=Mock(),
        )

        with patch.object(self.bot.bot.tree, "sync", sync_mock), patch.object(
            self.bot, "update_presence", update_presence_mock
        ), patch.object(self.bot, "update_gist_stats_task", task_mock):
            asyncio.run(self.bot.on_ready())
            asyncio.run(self.bot.on_ready())

        task_mock.start.assert_called_once()

    def test_bot_defaults_compile_concurrency_for_local_renderer(self):
        bot_module = _import_bot_module(
            env_removals=("LATEX_COMPILE_CONCURRENCY", "LATEX_MAX_QUEUE")
        )

        try:
            self.assertEqual(bot_module.LATEX_COMPILE_CONCURRENCY, 3)
            self.assertEqual(bot_module.compile_queue._max_concurrent, 3)
            self.assertEqual(bot_module.compile_queue._max_queued, 20)
            self.assertEqual(bot_module.executor._max_workers, 3)
        finally:
            bot_module.executor.shutdown(wait=False, cancel_futures=True)

    def test_bot_respects_compile_runtime_overrides(self):
        bot_module = _import_bot_module(
            env_overrides={
                "LATEX_COMPILE_CONCURRENCY": "4",
                "LATEX_MAX_QUEUE": "9",
            }
        )

        try:
            self.assertEqual(bot_module.LATEX_COMPILE_CONCURRENCY, 4)
            self.assertEqual(bot_module.compile_queue._max_concurrent, 4)
            self.assertEqual(bot_module.compile_queue._max_queued, 9)
            self.assertEqual(bot_module.executor._max_workers, 4)
        finally:
            bot_module.executor.shutdown(wait=False, cancel_futures=True)


if __name__ == "__main__":
    unittest.main()
