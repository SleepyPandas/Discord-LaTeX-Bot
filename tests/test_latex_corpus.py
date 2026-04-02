import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import latex_module
from tests.latex_corpus import LATEX_CORPUS_CASES


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
RAW_ERROR_LEAK_SUBSTRINGS = (
    "Fatal error occurred",
    "File ended while scanning",
    "Emergency stop",
    "Runaway argument",
    "main.tex:",
    "[main.log]",
)


def _toolchain_available() -> bool:
    return bool(shutil.which("pdflatex"))


class LatexCorpusRegressionTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not _toolchain_available():
            raise unittest.SkipTest("pdflatex is unavailable")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = str(Path(temp_dir) / "smoke")
            result = latex_module.text_to_latex(r"\frac{1}{2}", output_base)
            if result is not True:
                raise unittest.SkipTest(f"renderer unavailable: {result}")

    def test_corpus_metadata_matches_workflow_contract(self):
        self.assertEqual(len(LATEX_CORPUS_CASES), 50)

        success_cases = [case for case in LATEX_CORPUS_CASES if case.expected_status == "success"]
        error_cases = [case for case in LATEX_CORPUS_CASES if case.expected_status == "error"]

        self.assertEqual(len(success_cases), 35)
        self.assertEqual(len(error_cases), 15)
        self.assertEqual(len({case.id for case in LATEX_CORPUS_CASES}), len(LATEX_CORPUS_CASES))

    def test_corpus_cases_match_expected_renderer_outcomes(self):
        for case in LATEX_CORPUS_CASES:
            with self.subTest(case=case.id):
                with tempfile.TemporaryDirectory() as temp_dir:
                    output_base = str(Path(temp_dir) / case.id)
                    output_path = Path(f"{output_base}.png")
                    result = latex_module.text_to_latex(case.input, output_base, dpi=case.dpi)
                    output_exists = output_path.exists()
                    output_bytes = output_path.read_bytes() if output_exists else b""

                if case.expected_status == "success":
                    self.assertIs(
                        result,
                        True,
                        msg=f"{case.id} should render successfully but returned: {result}",
                    )
                    self.assertTrue(output_exists, msg=f"{case.id} did not produce a PNG")
                    self.assertTrue(
                        output_bytes.startswith(PNG_SIGNATURE),
                        msg=f"{case.id} produced a non-PNG payload",
                    )
                    continue

                self.assertIsInstance(
                    result,
                    str,
                    msg=f"{case.id} should return a friendly error string",
                )
                for substring in case.expected_error_contains:
                    self.assertIn(
                        substring,
                        result,
                        msg=f"{case.id} did not contain expected substring: {substring}",
                    )
                for banned_phrase in RAW_ERROR_LEAK_SUBSTRINGS:
                    self.assertNotIn(
                        banned_phrase,
                        result,
                        msg=f"{case.id} leaked raw compiler output: {banned_phrase}",
                    )
                self.assertFalse(
                    output_exists,
                    msg=f"{case.id} should not leave behind a PNG on failure",
                )


if __name__ == "__main__":
    unittest.main()
