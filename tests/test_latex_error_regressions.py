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
        )

        for expr in cases:
            with self.subTest(expr=expr):
                with tempfile.TemporaryDirectory() as temp_dir:
                    output_base = str(Path(temp_dir) / "success")
                    result = latex_module.text_to_latex(expr, output_base)

                self.assertIs(result, True)


if __name__ == "__main__":
    unittest.main()
