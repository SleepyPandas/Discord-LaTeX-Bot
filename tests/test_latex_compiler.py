import base64
import os
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from modified_packages.exceptions import CompilationError
from modified_packages.dvipng_renderer import InlineDviPngRenderer
from modified_packages.latex_compiler import LatexCompiler
from modified_packages.tex2img import Latex2PNG

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class SuccessfulProcess:
    instances = []
    last_timeout = None
    last_tex = ""
    last_resource = b""

    def __init__(self, command, cwd=None, **kwargs):
        self.command = command
        self.cwd = Path(cwd)
        self.kwargs = kwargs
        self.pid = 12345
        self.returncode = 0
        type(self).instances.append(self)

    def communicate(self, timeout=None):
        type(self).last_timeout = timeout
        type(self).last_tex = (self.cwd / "main.tex").read_text(encoding="utf-8")
        type(self).last_resource = (self.cwd / "assets" / "resource.bin").read_bytes()
        (self.cwd / "main.pdf").write_bytes(b"%PDF-1.7\nunit-test\n")
        (self.cwd / "main.log").write_text("Transcript written", encoding="utf-8")
        return ("compiled", "")

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.returncode = -9

    def send_signal(self, _signal):
        self.returncode = -9


class FailingProcess:
    def __init__(self, command, cwd=None, **kwargs):
        self.command = command
        self.cwd = Path(cwd)
        self.kwargs = kwargs
        self.pid = 23456
        self.returncode = 1

    def communicate(self, timeout=None):
        (self.cwd / "main.log").write_text(
            "main.tex:7: LaTeX Error: Undefined control sequence.\n! Undefined control sequence.",
            encoding="utf-8",
        )
        return ("", "")

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.returncode = -9

    def send_signal(self, _signal):
        self.returncode = -9


class TimeoutProcess:
    instances = []
    wait_timeouts = []
    kill_calls = 0
    signal_calls = []

    def __init__(self, command, cwd=None, **kwargs):
        self.command = command
        self.cwd = Path(cwd)
        self.kwargs = kwargs
        self.pid = 34567
        self.returncode = None
        type(self).instances.append(self)

    def communicate(self, timeout=None):
        (self.cwd / "main.log").write_text(
            "! Emergency stop.",
            encoding="utf-8",
        )
        raise subprocess.TimeoutExpired(
            cmd=self.command,
            timeout=timeout,
            output="partial stdout",
            stderr="partial stderr",
        )

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        type(self).wait_timeouts.append(timeout)
        self.returncode = -9
        return self.returncode

    def kill(self):
        type(self).kill_calls += 1
        self.returncode = -9

    def send_signal(self, sent_signal):
        type(self).signal_calls.append(sent_signal)
        self.returncode = -9


class FakeImage:
    def save(self, buffer, _format):
        buffer.write(b"png-bytes")


class SuccessfulDviPngProcess:
    instances = []
    timeouts = []

    def __init__(self, command, cwd=None, **kwargs):
        self.command = command
        self.cwd = Path(cwd)
        self.kwargs = kwargs
        self.pid = 45678
        self.returncode = 0
        type(self).instances.append(self)

    def communicate(self, timeout=None):
        type(self).timeouts.append(timeout)
        executable = Path(self.command[0]).name.lower()
        if executable == "latex":
            (self.cwd / "main.dvi").write_bytes(b"DVI")
            (self.cwd / "main.log").write_text("latex ok", encoding="utf-8")
            return ("latex ok", "")
        if executable == "dvipng":
            (self.cwd / "output1.png").write_bytes(PNG_SIGNATURE + b"dvipng-fast-path")
            return ("dvipng ok", "")
        raise AssertionError(f"Unexpected command: {self.command}")

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.returncode = -9

    def send_signal(self, _signal):
        self.returncode = -9


class LatexCompilerTestCase(unittest.TestCase):
    def setUp(self):
        SuccessfulProcess.instances = []
        SuccessfulProcess.last_timeout = None
        SuccessfulProcess.last_tex = ""
        SuccessfulProcess.last_resource = b""
        SuccessfulDviPngProcess.instances = []
        SuccessfulDviPngProcess.timeouts = []
        TimeoutProcess.instances = []
        TimeoutProcess.wait_timeouts = []
        TimeoutProcess.kill_calls = 0
        TimeoutProcess.signal_calls = []

    def test_compile_returns_pdf_bytes_and_cleans_up_workspace(self):
        latex_code = r"\documentclass{article}\begin{document}ok\end{document}"
        resource_payload = base64.b64encode(b"resource-bytes").decode("ascii")

        with tempfile.TemporaryDirectory() as compile_root:
            compiler = LatexCompiler(compile_dir=compile_root, timeout=4)

            with patch("modified_packages.latex_compiler.subprocess.Popen", SuccessfulProcess):
                pdf_data = compiler.compile(
                    latex_code,
                    images=[("assets/resource.bin", resource_payload)],
                )

            compile_root_path = Path(compile_root)
            self.assertEqual(pdf_data, b"%PDF-1.7\nunit-test\n")
            self.assertEqual(SuccessfulProcess.last_tex, latex_code)
            self.assertEqual(SuccessfulProcess.last_resource, b"resource-bytes")
            self.assertEqual(SuccessfulProcess.last_timeout, 4)
            self.assertEqual(list(compile_root_path.iterdir()), [])

        command = SuccessfulProcess.instances[0].command
        self.assertIn("-halt-on-error", command)
        self.assertIn("-no-shell-escape", command)
        self.assertTrue(any(arg.startswith("-output-directory=") for arg in command))

    def test_compile_raises_compilation_error_with_log_output(self):
        with tempfile.TemporaryDirectory() as compile_root:
            compiler = LatexCompiler(compile_dir=compile_root, timeout=4)

            with patch("modified_packages.latex_compiler.subprocess.Popen", FailingProcess):
                with self.assertRaises(CompilationError) as ctx:
                    compiler.compile(r"\documentclass{article}\begin{document}\bad\end{document}")

            self.assertEqual(list(Path(compile_root).iterdir()), [])

        error_text = str(ctx.exception)
        self.assertIn("Compilation failed with error logs:", error_text)
        self.assertIn("Undefined control sequence", error_text)
        self.assertIn("[main.log]", error_text)

    def test_compile_timeout_terminates_process_group_and_cleans_up_workspace(self):
        with tempfile.TemporaryDirectory() as compile_root:
            compiler = LatexCompiler(compile_dir=compile_root, timeout=2)

            with patch("modified_packages.latex_compiler.subprocess.Popen", TimeoutProcess):
                if os.name == "nt":
                    with patch("modified_packages.latex_compiler.subprocess.run") as mock_taskkill:
                        mock_taskkill.return_value = subprocess.CompletedProcess(
                            args=["taskkill"],
                            returncode=0,
                        )
                        with self.assertRaises(CompilationError) as ctx:
                            compiler.compile(r"\documentclass{article}\begin{document}slow\end{document}")
                else:
                    with patch("modified_packages.latex_compiler.os.killpg") as mock_killpg:
                        with self.assertRaises(CompilationError) as ctx:
                            compiler.compile(r"\documentclass{article}\begin{document}slow\end{document}")

            self.assertEqual(list(Path(compile_root).iterdir()), [])

        process = TimeoutProcess.instances[0]
        self.assertIsNotNone(process.kwargs.get("creationflags") if os.name == "nt" else process.kwargs.get("start_new_session"))
        self.assertIn(1.0, TimeoutProcess.wait_timeouts)
        if os.name == "nt":
            self.assertTrue(mock_taskkill.called)
            self.assertIn("taskkill", mock_taskkill.call_args.args[0][0].lower())
        else:
            mock_killpg.assert_called_once_with(process.pid, signal.SIGKILL)

        error_text = str(ctx.exception)
        self.assertIn("timed out after 2.0s", error_text)
        self.assertIn("partial stdout", error_text)
        self.assertIn("partial stderr", error_text)

    def test_latex2png_defaults_to_pdflatex(self):
        renderer = Latex2PNG()

        with patch(
            "modified_packages.tex2img.LatexCompiler.compile",
            return_value=b"%PDF-1.7\nunit-test\n",
        ) as mock_compile, patch(
            "modified_packages.tex2img.pdf2image.convert_from_bytes",
            return_value=[FakeImage()],
        ):
            png_data = renderer.compile(
                r"\documentclass{article}\begin{document}ok\end{document}"
            )

        self.assertEqual(png_data, [b"png-bytes"])
        mock_compile.assert_called_once_with(
            r"\documentclass{article}\begin{document}ok\end{document}",
            None,
            "pdflatex",
        )

    def test_inline_dvipng_renderer_runs_latex_then_dvipng(self):
        latex_code = r"\documentclass{standalone}\begin{document}$x^2$\end{document}"

        with tempfile.TemporaryDirectory() as compile_root:
            renderer = InlineDviPngRenderer(compile_dir=compile_root, timeout=5)

            with patch("modified_packages.dvipng_renderer.subprocess.Popen", SuccessfulDviPngProcess):
                png_data = renderer.compile(latex_code, transparent=True, dpi=275)

            self.assertEqual(list(Path(compile_root).iterdir()), [])

        self.assertEqual(png_data, PNG_SIGNATURE + b"dvipng-fast-path")
        self.assertEqual(len(SuccessfulDviPngProcess.instances), 2)
        latex_command = SuccessfulDviPngProcess.instances[0].command
        dvipng_command = SuccessfulDviPngProcess.instances[1].command

        self.assertEqual(latex_command[0], "latex")
        self.assertIn("-halt-on-error", latex_command)
        self.assertIn("-no-shell-escape", latex_command)
        self.assertTrue(any(arg.startswith("-output-directory=") for arg in latex_command))

        self.assertEqual(dvipng_command[0], "dvipng")
        self.assertIn("-T", dvipng_command)
        self.assertIn("tight", dvipng_command)
        self.assertIn("-bg", dvipng_command)
        self.assertIn("Transparent", dvipng_command)
        self.assertIn("-D", dvipng_command)
        self.assertIn("275", dvipng_command)
        self.assertIn("main.dvi", dvipng_command)
        self.assertEqual(SuccessfulDviPngProcess.timeouts, [5, 5])


if __name__ == "__main__":
    unittest.main()
