import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

if "sympy" not in sys.modules:
    sympy_stub = types.ModuleType("sympy")
    sympy_stub.preview = lambda *args, **kwargs: None
    sys.modules["sympy"] = sympy_stub

if "modified_packages" not in sys.modules:
    modified_packages_stub = types.ModuleType("modified_packages")

    class _Latex2PNGStub:
        def compile(self, *args, **kwargs):
            raise NotImplementedError("Latex2PNG stub should be mocked in tests")

    modified_packages_stub.Latex2PNG = _Latex2PNGStub
    sys.modules["modified_packages"] = modified_packages_stub

import latex_module


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
FULL_DOCUMENT = r"\documentclass{article}\begin{document}x\end{document}"


class LatexModuleTestCase(unittest.TestCase):
    def test_find_latex_error_returns_human_readable_message(self):
        compiler_log = "\n \n\n\n\n\n\r\r \n\n\n\n\n\r\rCompilation failed with error logs:\n! Missing delimiter.\n \n\n\n\n\n\r\r\r\r\r\r\\"

        result = latex_module.find_latex_error(compiler_log)

        self.assertEqual(result, "LaTeX compile error: Missing delimiter.")

    def test_text_to_latex_returns_fallback_on_unknown_compile_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = str(Path(temp_dir) / "failed_render")
            with patch.object(latex_module, "Latex2PNG") as mock_latex2png:
                mock_renderer = mock_latex2png.return_value
                mock_renderer.compile.side_effect = Exception("opaque failure")

                result = latex_module.text_to_latex(FULL_DOCUMENT, output_base)

        mock_renderer.compile.assert_called_once()
        self.assertEqual(result, latex_module._UNKNOWN_COMPILE_ERROR)
        self.assertFalse(Path(f"{output_base}.png").exists())

    def test_text_to_latex_writes_png_bytes_on_success(self):
        png_payload = PNG_SIGNATURE + b"unit-test-payload"

        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = str(Path(temp_dir) / "rendered_latex")
            with patch.object(latex_module, "Latex2PNG") as mock_latex2png:
                mock_renderer = mock_latex2png.return_value
                mock_renderer.compile.return_value = png_payload

                result = latex_module.text_to_latex(FULL_DOCUMENT, output_base)

            output_path = Path(f"{output_base}.png")
            mock_renderer.compile.assert_called_once()
            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_bytes(), png_payload)
            self.assertTrue(output_path.read_bytes().startswith(PNG_SIGNATURE))
            self.assertEqual(result, True)


if __name__ == "__main__":
    unittest.main()
