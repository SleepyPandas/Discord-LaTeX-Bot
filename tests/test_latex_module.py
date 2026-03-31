import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import latex_module


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
FULL_DOCUMENT = r"\documentclass{article}\begin{document}x\end{document}"


class LatexModuleTestCase(unittest.TestCase):
    def test_find_latex_error_returns_human_readable_message(self):
        compiler_log = "\n \n\n\n\n\n\r\r \n\n\n\n\n\r\rCompilation failed with error logs:\n! Missing delimiter.\n \n\n\n\n\n\r\r\r\r\r\r\\"

        result = latex_module.find_latex_error(compiler_log)

        self.assertEqual(result, "LaTeX compile error: Missing delimiter.")

    def test_find_latex_error_uses_line_numbers_from_local_compiler_logs(self):
        compiler_log = (
            "Compilation failed with error logs:\n"
            "[main.log]\n"
            "main.tex:7: LaTeX Error: Undefined control sequence.\n"
            "! Undefined control sequence."
        )

        result = latex_module.find_latex_error(compiler_log)

        self.assertEqual(
            result,
            "LaTeX compile error (line 7): LaTeX Error: Undefined control sequence. "
            "Hint: check command spelling or required package imports.",
        )

    def test_find_latex_error_returns_friendly_fontenc_fatal_message(self):
        compiler_log = (
            "Compilation failed with error logs:\n"
            "/usr/share/texlive/texmf-dist/tex/latex/base/fontenc.sty:111: ==> Fatal error"
        )

        result = latex_module.find_latex_error(compiler_log)

        self.assertEqual(
            result,
            "LaTeX dependency error: required fonts are unavailable in this renderer. "
            "Try standard fonts or remove custom font settings.",
        )

    def test_find_latex_error_returns_friendly_missing_font_message(self):
        compiler_log = (
            "Compilation failed with error logs:\n"
            "! LaTeX Font Error: Font family 'customfont' unknown."
        )

        result = latex_module.find_latex_error(compiler_log)

        self.assertEqual(
            result,
            "LaTeX dependency error: required fonts are unavailable in this renderer. "
            "Try standard fonts or remove custom font settings.",
        )

    def test_find_latex_error_returns_friendly_missing_package_message(self):
        compiler_log = (
            "Compilation failed with error logs:\n"
            "! LaTeX Error: File `foo.sty' not found."
        )

        result = latex_module.find_latex_error(compiler_log)

        self.assertEqual(
            result,
            "LaTeX dependency error: a required package is unavailable in this renderer. "
            "Try removing unsupported \\usepackage lines.",
        )

    def test_text_to_latex_rejects_input_over_3000_chars(self):
        result = latex_module.text_to_latex(
            "x" * (latex_module.MAX_LATEX_INPUT_CHARS + 1),
            "unused_output",
        )

        self.assertEqual(
            result,
            "Input too long: 3001 characters. Max is 3000 characters.",
        )

    def test_text_to_latex_ignores_legacy_prefix_when_counting_input_chars(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = str(Path(temp_dir) / "legacy_limit")
            with patch.object(
                latex_module,
                "_render_png_request",
                return_value=PNG_SIGNATURE,
            ):
                result = latex_module.text_to_latex(
                    "latex " + ("x" * latex_module.MAX_LATEX_INPUT_CHARS),
                    output_base,
                )

        self.assertTrue(result)

    def test_text_to_latex_rejects_legacy_prefix_input_over_3000_chars(self):
        result = latex_module.text_to_latex(
            "latex " + ("x" * (latex_module.MAX_LATEX_INPUT_CHARS + 1)),
            "unused_output",
        )

        self.assertEqual(
            result,
            "Input too long: 3001 characters. Max is 3000 characters.",
        )

    def test_remove_superfluous_wraps_plain_input_in_display_math(self):
        result = latex_module.remove_superfluous(r"\frac{1}{2}")

        self.assertEqual(result, r"$\displaystyle \frac{1}{2}$")

    def test_remove_superfluous_preserves_existing_math_delimiters(self):
        result = latex_module.remove_superfluous(r"\[\frac{1}{2}\]")

        self.assertEqual(result, r"$\displaystyle \frac{1}{2}$")

    def test_remove_superfluous_converts_double_dollar_display_math(self):
        result = latex_module.remove_superfluous(r"$$\frac{1}{2}$$")

        self.assertEqual(result, r"$\displaystyle \frac{1}{2}$")

    def test_remove_superfluous_converts_multiple_display_math_blocks(self):
        result = latex_module.remove_superfluous(
            "$$a^2 + b^2 = c^2$$\n"
            "$$\\begin{bmatrix}1 & 2\\\\3 & 4\\end{bmatrix}$$"
        )

        self.assertEqual(
            result,
            "$\\displaystyle \\begin{gathered}\n"
            "a^2 + b^2 = c^2\\\\\n"
            "\\begin{bmatrix}1 & 2\\\\3 & 4\\end{bmatrix}\n"
            "\\end{gathered}$",
        )

    def test_remove_superfluous_strips_legacy_prefix_before_wrapping(self):
        result = latex_module.remove_superfluous(r"latex \alpha + \beta")

        self.assertEqual(result, r"$\displaystyle \alpha + \beta$")

    def test_normalize_full_document_adds_standalone_class_when_missing(self):
        result = latex_module._normalize_full_document(r"\begin{document}x\end{document}")

        self.assertTrue(result.startswith(r"\documentclass[border=1mm]{standalone}"))
        self.assertIn(r"\begin{document}x\end{document}", result)

    def test_normalize_full_document_wraps_bare_tikzpicture_in_document_body(self):
        expr = r"\begin{tikzpicture}\draw (0,0) -- (1,1);\end{tikzpicture}"
        result = latex_module._normalize_full_document(expr)

        self.assertTrue(result.startswith(r"\documentclass[tikz,border=6pt]{standalone}"))
        doc_pos = result.find(r"\begin{document}")
        tikz_pos = result.find(r"\begin{tikzpicture}")
        self.assertNotEqual(doc_pos, -1)
        self.assertNotEqual(tikz_pos, -1)
        self.assertLess(doc_pos, tikz_pos)
        self.assertIn(expr, result)
        self.assertTrue(result.rstrip().endswith(r"\end{document}"))

    def test_normalize_full_document_wraps_raw_draw_in_tikzpicture_and_document(self):
        expr = r"\draw (0,0) -- (1,1);"
        result = latex_module._normalize_full_document(expr)

        self.assertTrue(result.startswith(r"\documentclass[tikz,border=6pt]{standalone}"))
        doc_pos = result.find(r"\begin{document}")
        tikz_pos = result.find(r"\begin{tikzpicture}")
        self.assertLess(doc_pos, tikz_pos)
        self.assertIn(r"\begin{tikzpicture}", result)
        self.assertIn(r"\end{tikzpicture}", result)
        self.assertIn(expr.strip(), result)

    def test_normalize_full_document_preserves_standalone_documentclass_options(self):
        src = r"\documentclass[tikz,border=10pt]{standalone}\begin{document}y\end{document}"
        result = latex_module._normalize_full_document(src)

        self.assertIn(r"\documentclass[tikz,border=10pt]{standalone}", result)

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

    def test_text_to_latex_routes_simple_math_through_dvipng_fast_path(self):
        png_payload = PNG_SIGNATURE + b"simple-math"

        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = str(Path(temp_dir) / "simple_render")
            with patch.object(latex_module, "InlineDviPngRenderer") as mock_dvipng_renderer, patch.object(
                latex_module,
                "Latex2PNG",
            ) as mock_latex2png:
                mock_renderer = mock_dvipng_renderer.return_value
                mock_renderer.compile.return_value = png_payload

                result = latex_module.text_to_latex(r"\frac{1}{2}", output_base, dpi=275)

            output_path = Path(f"{output_base}.png")
            mock_renderer.compile.assert_called_once()
            mock_latex2png.assert_not_called()
            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_bytes(), png_payload)
            self.assertEqual(result, True)

        compile_args, compile_kwargs = mock_renderer.compile.call_args
        self.assertIn(r"\documentclass[border=1mm]{standalone}", compile_args[0])
        self.assertIn(r"\begin{document}", compile_args[0])
        self.assertIn(r"$\displaystyle \frac{1}{2}$", compile_args[0])
        self.assertEqual(compile_kwargs["dpi"], 275)
        self.assertTrue(compile_kwargs["transparent"])

    def test_text_to_latex_falls_back_to_pdf_renderer_when_dvipng_fails(self):
        png_payload = PNG_SIGNATURE + b"fallback-pdf"

        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = str(Path(temp_dir) / "fallback_render")
            with patch.object(latex_module, "InlineDviPngRenderer") as mock_dvipng_renderer, patch.object(
                latex_module,
                "Latex2PNG",
            ) as mock_latex2png:
                mock_dvipng_renderer.return_value.compile.side_effect = Exception("fast path failed")
                mock_latex2png.return_value.compile.return_value = png_payload

                result = latex_module.text_to_latex(r"\frac{1}{2}", output_base, dpi=300)

        self.assertEqual(result, True)
        mock_dvipng_renderer.return_value.compile.assert_called_once()
        mock_latex2png.return_value.compile.assert_called_once()
        self.assertEqual(
            mock_latex2png.return_value.compile.call_args.kwargs["compiler"],
            "pdflatex",
        )

    def test_text_to_latex_routes_blocked_inline_commands_through_pdf_renderer(self):
        png_payload = PNG_SIGNATURE + b"blocked-inline"

        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = str(Path(temp_dir) / "blocked_render")
            expr = r"\usepackage{bm} \bm{x}"
            with patch.object(latex_module, "InlineDviPngRenderer") as mock_dvipng_renderer, patch.object(
                latex_module,
                "Latex2PNG",
            ) as mock_latex2png:
                mock_latex2png.return_value.compile.return_value = png_payload

                result = latex_module.text_to_latex(expr, output_base, dpi=300)

        self.assertEqual(result, True)
        mock_dvipng_renderer.assert_not_called()
        mock_latex2png.return_value.compile.assert_called_once()

    def test_text_to_latex_routes_math_environment_blocks_through_dvipng(self):
        png_payload = PNG_SIGNATURE + b"display-blocks"
        expr = (
            "$$a^2 + b^2 = c^2$$\n"
            "$$\\begin{bmatrix}1 & 2\\\\3 & 4\\end{bmatrix}$$"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = str(Path(temp_dir) / "display_blocks")
            with patch.object(latex_module, "InlineDviPngRenderer") as mock_dvipng_renderer, patch.object(
                latex_module,
                "Latex2PNG",
            ) as mock_latex2png:
                mock_dvipng_renderer.return_value.compile.return_value = png_payload

                result = latex_module.text_to_latex(expr, output_base, dpi=300)

        self.assertEqual(result, True)
        mock_latex2png.assert_not_called()
        mock_dvipng_renderer.return_value.compile.assert_called_once()
        compile_args, _compile_kwargs = mock_dvipng_renderer.return_value.compile.call_args
        self.assertIn(r"$\displaystyle \begin{gathered}", compile_args[0])
        self.assertIn(r"a^2 + b^2 = c^2\\", compile_args[0])
        self.assertIn(r"\begin{bmatrix}1 & 2\\3 & 4\end{bmatrix}", compile_args[0])
        self.assertIn(r"\end{gathered}$", compile_args[0])
        self.assertNotIn("$$", compile_args[0])

    def test_text_to_latex_routes_tikz_environment_through_pdf_renderer(self):
        png_payload = PNG_SIGNATURE + b"tikz-blocked"
        expr = r"\begin{tikzpicture}\draw (0,0) -- (1,1);\end{tikzpicture}"

        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = str(Path(temp_dir) / "tikz_blocked")
            with patch.object(latex_module, "InlineDviPngRenderer") as mock_dvipng_renderer, patch.object(
                latex_module,
                "Latex2PNG",
            ) as mock_latex2png:
                mock_latex2png.return_value.compile.return_value = png_payload

                result = latex_module.text_to_latex(expr, output_base, dpi=300)

        self.assertEqual(result, True)
        mock_dvipng_renderer.assert_not_called()
        mock_latex2png.return_value.compile.assert_called_once()
        compile_args, compile_kwargs = mock_latex2png.return_value.compile.call_args
        tex = compile_args[0]
        self.assertIn(r"\documentclass[tikz,border=6pt]{standalone}", tex)
        self.assertIn(r"\begin{document}", tex)
        self.assertIn(r"\end{document}", tex)
        self.assertIn(r"\begin{tikzpicture}", tex)
        self.assertIn(r"\draw (0,0) -- (1,1);", tex)
        self.assertNotIn(r"$\displaystyle", tex)
        self.assertFalse(compile_kwargs.get("transparent", True))

    def test_text_to_latex_routes_raw_draw_fragment_through_pdf_renderer(self):
        png_payload = PNG_SIGNATURE + b"raw-draw"
        expr = r"\draw (0,0) rectangle (2,1);"

        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = str(Path(temp_dir) / "raw_draw")
            with patch.object(latex_module, "InlineDviPngRenderer") as mock_dvipng_renderer, patch.object(
                latex_module,
                "Latex2PNG",
            ) as mock_latex2png:
                mock_latex2png.return_value.compile.return_value = png_payload

                result = latex_module.text_to_latex(expr, output_base, dpi=300)

        self.assertEqual(result, True)
        mock_dvipng_renderer.assert_not_called()
        mock_latex2png.return_value.compile.assert_called_once()
        compile_args, _compile_kwargs = mock_latex2png.return_value.compile.call_args
        tex = compile_args[0]
        self.assertIn(r"\documentclass[tikz,border=6pt]{standalone}", tex)
        self.assertIn(r"\begin{document}", tex)
        self.assertIn(r"\begin{tikzpicture}", tex)
        self.assertIn(expr, tex)
        self.assertNotIn(r"$\displaystyle", tex)

    def test_text_to_latex_routes_full_documents_through_local_renderer(self):
        png_payload = PNG_SIGNATURE + b"unit-test-payload"

        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = str(Path(temp_dir) / "rendered_latex")
            with patch.object(latex_module, "InlineDviPngRenderer") as mock_dvipng_renderer, patch.object(
                latex_module,
                "Latex2PNG",
            ) as mock_latex2png:
                mock_renderer = mock_latex2png.return_value
                mock_renderer.compile.return_value = png_payload

                result = latex_module.text_to_latex(FULL_DOCUMENT, output_base, dpi=410)

            output_path = Path(f"{output_base}.png")
            mock_renderer.compile.assert_called_once()
            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_bytes(), png_payload)
            self.assertTrue(output_path.read_bytes().startswith(PNG_SIGNATURE))
            self.assertEqual(result, True)

        mock_dvipng_renderer.assert_not_called()
        compile_args, compile_kwargs = mock_renderer.compile.call_args
        self.assertIn(r"\documentclass[border=1mm]{standalone}", compile_args[0])
        self.assertIn(r"\begin{document}x\end{document}", compile_args[0])
        self.assertEqual(compile_kwargs["compiler"], "pdflatex")
        self.assertEqual(compile_kwargs["dpi"], 410)
        self.assertFalse(compile_kwargs["transparent"])


if __name__ == "__main__":
    unittest.main()
