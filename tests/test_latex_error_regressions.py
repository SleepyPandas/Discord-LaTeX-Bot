import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import latex_module


_BANNED_ERROR_PHRASES = (
    "Fatal error occurred",
    "File ended while scanning",
    "Emergency stop",
    "Runaway argument",
    "main.tex:",
)


def _toolchain_available() -> bool:
    return bool(shutil.which("pdflatex"))


class LatexFriendlyRegressionTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not _toolchain_available():
            raise unittest.SkipTest("pdflatex is unavailable")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = str(Path(temp_dir) / "smoke")
            result = latex_module.text_to_latex(r"\frac{1}{2}", output_base)
            if result is not True:
                raise unittest.SkipTest(f"renderer unavailable: {result}")

    def assertFriendlyFailure(self, expr: str, expected_substrings: tuple[str, ...]) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = str(Path(temp_dir) / "failure")
            result = latex_module.text_to_latex(expr, output_base)

        self.assertIsInstance(result, str)
        for substring in expected_substrings:
            self.assertIn(substring, result)
        for banned_phrase in _BANNED_ERROR_PHRASES:
            self.assertNotIn(banned_phrase, result)

    def test_common_failure_messages_are_friendly(self):
        cases = (
            (
                r"\frac{1}{2",
                ("LaTeX syntax error (line 1):", r"Missing `}` to finish `\frac{...}{...}`."),
            ),
            (
                r"\text{hello",
                ("LaTeX syntax error (line 1):", r"Missing `}` to finish `\text{...}`."),
            ),
            (
                r"\sqrt{2",
                ("LaTeX syntax error (line 1):", r"Missing `}` to finish `\sqrt{...}`."),
            ),
            (
                "\\begin{aligned}\na&=b",
                ("LaTeX syntax error (line 1):", r"Missing `\end{aligned}` to close the environment."),
            ),
            (
                r"\begin{bmatrix}1 & 2",
                ("LaTeX syntax error (line 1):", r"Missing `\end{bmatrix}` to close the environment."),
            ),
            (
                r"\left( x+1",
                ("LaTeX syntax error (line 1):", r"Missing `\right` to match `\left`."),
            ),
            (
                r"$x+1",
                ("LaTeX syntax error (line 1):", "Missing closing `$` to finish the math expression."),
            ),
            (
                r"\foo + 1",
                ("LaTeX command error (line 1):", r"`\foo` is undefined."),
            ),
            (
                "\\begin{tikzcd}\nA \\arrow[r] & B\n\\end{tikzcd}",
                ("LaTeX environment error (line 1):", r"`tikzcd` requires `\usepackage{tikz-cd}` in the preamble."),
            ),
            (
                "\\usepackage{minted}\n\\begin{document}x\\end{document}",
                ("Unsupported LaTeX feature (line 1):", "package `minted` requires shell escape"),
            ),
            (
                r"\frac{\foo}{2}",
                ("LaTeX command error (line 1):", r"`\foo` is undefined."),
            ),
            (
                r"\alpha + \beta + \unknowncmd + \gamma",
                ("LaTeX command error (line 1):", r"`\unknowncmd` is undefined."),
            ),
        )

        for expr, expected_substrings in cases:
            with self.subTest(expr=expr):
                self.assertFriendlyFailure(expr, expected_substrings)

    def test_common_success_cases_still_render(self):
        cases = (
            r"\frac{1}{2}",
            r"\text{hello}",
            r"\begin{aligned}a&=b\end{aligned}",
            r"\begin{bmatrix}1 & 2\\3 & 4\end{bmatrix}",
            r"\begin{align*} 1 &= 1 \\ \implies 1 &= (1 + 1) - 1 \end{align*}",
            r"\begin{gather*} x = 1 \end{gather*}",
        )

        for expr in cases:
            with self.subTest(expr=expr):
                with tempfile.TemporaryDirectory() as temp_dir:
                    output_base = str(Path(temp_dir) / "success")
                    result = latex_module.text_to_latex(expr, output_base)

                self.assertIs(result, True)

    def test_nested_command_does_not_blame_outer_command(self):
        expr = r"\frac{\foo}{2}"
        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = str(Path(temp_dir) / "failure_nested")
            result = latex_module.text_to_latex(expr, output_base)

        self.assertIsInstance(result, str)
        self.assertIn(r"`\foo` is undefined", result)
        self.assertNotIn(r"`\frac`", result)

    def test_multiline_failure_shows_snippet(self):
        expr = "\\begin{align*}\n1 &= 1 \\\\\n\\badcmd &= 2\n\\end{align*}"
        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = str(Path(temp_dir) / "failure_multiline")
            result = latex_module.text_to_latex(expr, output_base)

        self.assertIsInstance(result, str)
        self.assertIn("LaTeX command error (line 3):", result)
        self.assertIn("`\\badcmd` is undefined.", result)
        # Verify 3-line context inside text code block: line before (2), target line (3), line after (4)
        self.assertIn("```text\n", result)
        self.assertIn("  2 | 1 &= 1 \\\\", result)
        self.assertIn("> 3 | \\badcmd &= 2", result)
        self.assertIn("  4 | \\end{align*}", result)
        self.assertIn("\n```", result)

    def test_multiline_failure_on_empty_line_shows_context_snippet(self):
        # Empty line following \\ causes a syntax error; verify empty line is preserved in snippet
        expr = "\\begin{align*}\n1 &= 1 \\\\\n\n2 &= 2\n\\end{align*}"
        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = str(Path(temp_dir) / "failure_empty_line")
            result = latex_module.text_to_latex(expr, output_base)

        self.assertIsInstance(result, str)
        self.assertIn("LaTeX syntax error (line 3):", result)
        self.assertIn("```text\n", result)
        self.assertIn("  2 | 1 &= 1 \\\\", result)
        self.assertIn("> 3 |", result)
        self.assertIn("  4 | 2 &= 2", result)
        self.assertIn("\n```", result)

    def test_undefined_command_with_nu_in_expression_identifies_correct_command(self):
        expr = r"R_{\mu \nu} - \frac{1}{2}Rg_{\mu \nu} + \Lamda g_{\mu \nu} = \kappa T_{\mu \nu}"
        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = str(Path(temp_dir) / "failure_nu_typo")
            result = latex_module.text_to_latex(expr, output_base)

        self.assertIsInstance(result, str)
        self.assertIn(r"`\Lamda` is undefined", result)
        self.assertNotIn(r"`\mu`", result)
    def test_real_compiler_no_line_to_end_error_not_truncated(self):
        expr = "\\begin{document}\n\\\\\n\\end{document}"
        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = str(Path(temp_dir) / "failure_no_line_to_end")
            result = latex_module.text_to_latex(expr, output_base)

        self.assertIsInstance(result, str)
        self.assertIn("There's no line here to end.", result)
        self.assertNotIn("There's no line here to.", result)

    def test_real_compiler_long_environment_name_error_not_truncated(self):
        env = "undefinedenvironmentwithaveryveryveryveryveryveryveryveryveryveryveryverylongname"
        expr = f"\\begin{{document}}\n\\begin{{{env}}}\n\\end{{{env}}}\n\\end{{document}}"
        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = str(Path(temp_dir) / "failure_long_env")
            result = latex_module.text_to_latex(expr, output_base)

        self.assertIsInstance(result, str)
        self.assertIn(env, result)
        self.assertIn("is unavailable in this renderer", result)

    def test_real_compiler_standard_tex_error_extracted(self):
        expr = "\\begin{document}\n\\vspace{abc}\n\\end{document}"
        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = str(Path(temp_dir) / "failure_standard_tex_error")
            result = latex_module.text_to_latex(expr, output_base)

        self.assertIsInstance(result, str)
        self.assertIn("Missing number, treated as zero.", result)
        self.assertNotIn("incomplete or unsupported in this renderer", result)

    def test_real_compiler_long_undefined_command_extracted_not_truncated(self):
        long_cmd = "\\thisisaveryveryveryveryveryveryveryveryveryverylongundefinedcommandname"
        expr = f"\\frac{{1}}{{{long_cmd}}}"
        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = str(Path(temp_dir) / "failure_long_cmd")
            result = latex_module.text_to_latex(expr, output_base)

        self.assertIsInstance(result, str)
        self.assertIn(long_cmd, result)
        self.assertIn("is undefined.", result)

    def test_real_compiler_snippet_with_backticks_preserves_code_block(self):
        # When user code contains comments or text with triple backticks, the snippet codeblock must remain valid
        triple_bt = chr(96) * 3
        expr = f"\\begin{{align*}}\n1 &= 1 \\\\\n% {triple_bt}\n\\badcmd &= 2\n\\end{{align*}}"
        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = str(Path(temp_dir) / "failure_backticks")
            result = latex_module.text_to_latex(expr, output_base)

        self.assertIsInstance(result, str)
        self.assertIn("LaTeX command error (line 4):", result)
        self.assertIn("```text\n", result)
        self.assertTrue(result.endswith("\n```"))
        # Check that the code block has not prematurely closed
        snippet_body = result[result.index("```text\n") + len("```text\n") : -len("\n```")]
        self.assertNotIn(triple_bt, snippet_body)
        self.assertIn("> 4 | \\badcmd &= 2", snippet_body)
        self.assertIn("  5 | \\end{align*}", snippet_body)


if __name__ == "__main__":
    unittest.main()
