import base64
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from modified_packages.exceptions import CompilationError
from modified_packages.latex_compiler import LatexCompiler


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
    def __init__(self, command, cwd=None, **kwargs):
        self.command = command
        self.cwd = Path(cwd)
        self.kwargs = kwargs
        self.pid = 34567
        self.returncode = None

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
        self.returncode = -9
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
                with patch.object(LatexCompiler, "_terminate_process_group", autospec=True) as mock_terminate:
                    with self.assertRaises(CompilationError) as ctx:
                        compiler.compile(r"\documentclass{article}\begin{document}slow\end{document}")

            self.assertEqual(list(Path(compile_root).iterdir()), [])

        mock_terminate.assert_called_once()
        error_text = str(ctx.exception)
        self.assertIn("timed out after 2.0s", error_text)
        self.assertIn("partial stdout", error_text)
        self.assertIn("partial stderr", error_text)


if __name__ == "__main__":
    unittest.main()
