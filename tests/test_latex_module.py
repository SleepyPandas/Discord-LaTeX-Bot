import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

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

    def test_remove_superfluous_wraps_plain_input_in_display_math(self):
        result = latex_module.remove_superfluous(r"\frac{1}{2}")

        self.assertEqual(result, r"\[\frac{1}{2}\]")

    def test_remove_superfluous_preserves_existing_math_delimiters(self):
        result = latex_module.remove_superfluous(r"\[\frac{1}{2}\]")

        self.assertEqual(result, r"\[\frac{1}{2}\]")

    def test_remove_superfluous_strips_legacy_prefix_before_wrapping(self):
        result = latex_module.remove_superfluous(r"latex \alpha + \beta")

        self.assertEqual(result, r"\[\alpha + \beta\]")

    def test_normalize_full_document_adds_standalone_class_when_missing(self):
        result = latex_module._normalize_full_document(r"\begin{document}x\end{document}")

        self.assertTrue(result.startswith(r"\documentclass[border=1mm]{standalone}"))
        self.assertIn(r"\begin{document}x\end{document}", result)

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

    def test_text_to_latex_routes_simple_math_through_local_renderer(self):
        png_payload = PNG_SIGNATURE + b"simple-math"

        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = str(Path(temp_dir) / "simple_render")
            with patch.object(latex_module, "Latex2PNG") as mock_latex2png:
                mock_renderer = mock_latex2png.return_value
                mock_renderer.compile.return_value = png_payload

                result = latex_module.text_to_latex(r"\frac{1}{2}", output_base, dpi=275)

            output_path = Path(f"{output_base}.png")
            mock_renderer.compile.assert_called_once()
            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_bytes(), png_payload)
            self.assertEqual(result, True)

        compile_args, compile_kwargs = mock_renderer.compile.call_args
        self.assertIn(r"\documentclass[border=1mm]{standalone}", compile_args[0])
        self.assertIn(r"\begin{document}", compile_args[0])
        self.assertIn(r"\[\frac{1}{2}\]", compile_args[0])
        self.assertEqual(compile_kwargs["compiler"], "pdflatex")
        self.assertEqual(compile_kwargs["dpi"], 275)
        self.assertTrue(compile_kwargs["transparent"])

    def test_text_to_latex_routes_full_documents_through_local_renderer(self):
        png_payload = PNG_SIGNATURE + b"unit-test-payload"

        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = str(Path(temp_dir) / "rendered_latex")
            with patch.object(latex_module, "Latex2PNG") as mock_latex2png:
                mock_renderer = mock_latex2png.return_value
                mock_renderer.compile.return_value = png_payload

                result = latex_module.text_to_latex(FULL_DOCUMENT, output_base, dpi=410)

            output_path = Path(f"{output_base}.png")
            mock_renderer.compile.assert_called_once()
            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_bytes(), png_payload)
            self.assertTrue(output_path.read_bytes().startswith(PNG_SIGNATURE))
            self.assertEqual(result, True)

        compile_args, compile_kwargs = mock_renderer.compile.call_args
        self.assertIn(r"\documentclass[border=1mm]{standalone}", compile_args[0])
        self.assertIn(r"\begin{document}x\end{document}", compile_args[0])
        self.assertEqual(compile_kwargs["compiler"], "pdflatex")
        self.assertEqual(compile_kwargs["dpi"], 410)
        self.assertFalse(compile_kwargs["transparent"])


if __name__ == "__main__":
    unittest.main()
