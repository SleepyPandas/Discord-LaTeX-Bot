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

        self.assertEqual(result, "LaTeX syntax error: Missing delimiter.")

    def test_find_latex_error_maps_generated_line_numbers_back_to_user_input(self):
        render_request = latex_module._prepare_render_request(r"\foo + 1", 300)
        compiler_log = (
            "Compilation failed with error logs:\n"
            "[main.log]\n"
            "main.tex:9: Undefined control sequence.\n"
            "l.9 $\\displaystyle \\foo + 1$"
        )

        result = latex_module.find_latex_error(compiler_log, render_request=render_request)

        self.assertEqual(
            result,
            "LaTeX command error (line 1): `\\foo` is undefined. "
            "Check the command name or add the required package.",
        )

    def test_find_latex_error_rewrites_file_ended_scanning_messages(self):
        compiler_log = (
            "Compilation failed with error logs:\n"
            "! File ended while scanning use of \\frac ."
        )

        result = latex_module.find_latex_error(compiler_log)

        self.assertEqual(
            result,
            "LaTeX syntax error: Missing `}` to finish `\\frac{...}{...}`.",
        )

    def test_find_latex_error_names_missing_environment_package(self):
        compiler_log = (
            "Compilation failed with error logs:\n"
            "main.tex:3: LaTeX Error: Environment tikzcd undefined."
        )

        result = latex_module.find_latex_error(compiler_log)

        self.assertEqual(
            result,
            "LaTeX environment error (line 3): `tikzcd` requires "
            "`\\usepackage{tikz-cd}` in the preamble.",
        )

    def test_find_latex_error_rewrites_missing_brace_inserted_with_render_request_context(self):
        render_request = latex_module._prepare_render_request(r"\sqrt{2", 300)
        compiler_log = (
            "Compilation failed with error logs:\n"
            "main.tex:9: Missing } inserted.\n"
            "l.9 $\\displaystyle \\sqrt{2$"
        )

        result = latex_module.find_latex_error(compiler_log, render_request=render_request)

        self.assertEqual(
            result,
            "LaTeX syntax error (line 1): Missing `}` to finish `\\sqrt{...}`.",
        )

    def test_find_latex_error_rewrites_missing_dollar_inserted(self):
        compiler_log = (
            "Compilation failed with error logs:\n"
            "main.tex:10: Missing $ inserted."
        )

        result = latex_module.find_latex_error(compiler_log)

        self.assertEqual(
            result,
            "LaTeX syntax error (line 10): Missing a math delimiter like `$...$` or `\\[...\\]`.",
        )

    def test_find_latex_error_handles_undefined_control_sequence_without_command_context(self):
        compiler_log = (
            "Compilation failed with error logs:\n"
            "main.tex:9: Undefined control sequence."
        )

        result = latex_module.find_latex_error(compiler_log)

        self.assertEqual(
            result,
            "LaTeX command error (line 9): An undefined command was used. "
            "Check the command name or add the required package.",
        )

    def test_find_latex_error_preserves_commands_starting_with_backslash_n(self):
        source = r"R_{\mu \nu} - \frac{1}{2}Rg_{\mu \nu} + \Lamda g_{\mu \nu} = \kappa T_{\mu \nu}"
        render_request = latex_module._prepare_render_request(source, 300)
        compiler_log = (
            "Compilation failed with error logs:\n"
            "[main.log]\n"
            "main.tex:9: Undefined control sequence.\n"
            "l.9 ...\\mu \\nu} - \\frac{1}{2}Rg_{\\mu \\nu} + \\Lamda\n"
            "                                                   g_{\\mu \\nu} = \\kappa T_{\\mu ...\n"
        )
        result = latex_module.find_latex_error(compiler_log, render_request=render_request)
        self.assertIn(r"`\Lamda` is undefined", result)
        self.assertNotIn(r"`\mu`", result)

    def test_find_latex_error_formats_plain_latex_error_messages(self):
        compiler_log = (
            "Compilation failed with error logs:\n"
            "main.tex:4: LaTeX Error: Missing delimiter."
        )

        result = latex_module.find_latex_error(compiler_log)

        self.assertEqual(
            result,
            "LaTeX syntax error (line 4): Missing delimiter.",
        )

    def test_find_latex_error_formats_bang_prefixed_messages(self):
        compiler_log = (
            "Compilation failed with error logs:\n"
            "! Extra alignment tab has been changed to \\cr"
        )

        result = latex_module.find_latex_error(compiler_log)

        self.assertEqual(
            result,
            "LaTeX syntax error: Extra alignment tab has been changed to \\cr.",
        )

    def test_find_latex_error_unwraps_79_column_wrapped_latex_error(self):
        line_79 = "main.tex:10: LaTeX Error: Long error statement that hard-wraps at column sevent"
        self.assertEqual(len(line_79), 79)
        compiler_log = (
            "Compilation failed with error logs:\n"
            f"{line_79}\n"
            "y nine.\n\n"
            "See the LaTeX manual or LaTeX Companion for explanation."
        )

        result = latex_module.find_latex_error(compiler_log)

        self.assertEqual(
            result,
            "LaTeX syntax error (line 10): Long error statement that hard-wraps at column seventy nine.",
        )

    def test_find_latex_error_recovers_multiline_cut_off_message(self):
        compiler_log = (
            "Compilation failed with error logs:\n"
            "main.tex:10: LaTeX Error: There's no line here to\n"
            "end.\n\n"
            "See the LaTeX manual or LaTeX Companion for explanation."
        )

        result = latex_module.find_latex_error(compiler_log)

        self.assertEqual(
            result,
            "LaTeX syntax error (line 10): There's no line here to end.",
        )

    def test_find_latex_error_unwraps_79_column_wrapped_package_error(self):
        line_79 = "main.tex:3: Package mypkg Error: Here is a very long error message that will de"
        self.assertEqual(len(line_79), 79)
        compiler_log = (
            "Compilation failed with error logs:\n"
            f"{line_79}\n"
            "finitely exceed seventy nine characters and wrap onto the next line.\n\n"
            "See the mypkg package documentation for explanation."
        )

        result = latex_module.find_latex_error(compiler_log)

        self.assertEqual(
            result,
            "LaTeX syntax error (line 3): [mypkg] Here is a very long error message that will definitely exceed seventy nine characters and wrap onto the next line.",
        )

    def test_find_latex_error_handles_package_continuation_lines(self):
        compiler_log = (
            "Compilation failed with error logs:\n"
            "Package hyperref Error: Wrong DVI mode driver option 'dvips',\n"
            "(hyperref)                because pdfTeX or LuaTeX is running.\n\n"
            "See the hyperref package documentation for explanation."
        )

        result = latex_module.find_latex_error(compiler_log)

        self.assertEqual(
            result,
            "LaTeX syntax error: [hyperref] Wrong DVI mode driver option 'dvips', because pdfTeX or LuaTeX is running.",
        )

    def test_find_latex_error_unwraps_79_column_wrapped_environment_error(self):
        line_79 = "main.tex:3: LaTeX Error: Environment undefinedenvironmentwithaveryveryveryveryv"
        self.assertEqual(len(line_79), 79)
        compiler_log = (
            "Compilation failed with error logs:\n"
            f"{line_79}\n"
            "eryveryveryveryveryveryveryverylongname undefined.\n\n"
            "See the LaTeX manual or LaTeX Companion for explanation."
        )

        result = latex_module.find_latex_error(compiler_log)

        self.assertIn(
            "`undefinedenvironmentwithaveryveryveryveryveryveryveryveryveryveryveryverylongname` is unavailable",
            result,
        )

    def test_find_latex_error_unwraps_79_column_wrapped_file_path(self):
        line_79 = "/var/very/long/temporary/latex/bot/working/dir/build/session/2026/09/14/main.te"
        self.assertEqual(len(line_79), 79)
        compiler_log = (
            "Compilation failed with error logs:\n"
            f"{line_79}\n"
            "x:15: LaTeX Error: Missing delimiter.\n"
        )

        result = latex_module.find_latex_error(compiler_log)

        self.assertEqual(
            result,
            "LaTeX syntax error (line 15): Missing delimiter.",
        )

    def test_find_latex_error_handles_multiline_bang_message(self):
        compiler_log = (
            "Compilation failed with error logs:\n"
            "! Something strange happened\n"
            "and continued on the next line."
        )

        result = latex_module.find_latex_error(compiler_log)

        self.assertEqual(
            result,
            "LaTeX syntax error: Something strange happened and continued on the next line.",
        )

    def test_unwrap_tex_log_preserves_non_wrapped_boundaries(self):
        mem_line = " 35i,0n,38p,202b,36s stack positions out of 10000i,1000n,20000p,200000b,200000s"
        self.assertEqual(len(mem_line), 79)
        log = (
            f"{mem_line}\n"
            "main.tex:3:  ==> Fatal error occurred, no output PDF file produced!"
        )

        unwrapped = latex_module._unwrap_tex_log(log)
        self.assertEqual(unwrapped, log)

    def test_unwrap_tex_log_handles_crlf_without_embedding_carriage_return(self):
        line_79 = "a" * 79
        log = f"{line_79}\r\ncontinuation line\r\n"
        unwrapped = latex_module._unwrap_tex_log(log)
        self.assertNotIn("\r", unwrapped)
        self.assertEqual(unwrapped, f"{line_79}continuation line\n")

    def test_unwrap_tex_log_handles_crlf_80_col_lines(self):
        line_80 = "b" * 80
        log = f"{line_80}\r\ncontinuation\r\n"
        unwrapped = latex_module._unwrap_tex_log(log)
        self.assertEqual(unwrapped, f"{line_80}continuation\n")

    def test_unwrap_tex_log_unwraps_wrapped_paths_ending_in_slash(self):
        path_prefix = "/very/long/temporary/path/to/project/directory/nested/deep/inside/subfolder/"
        self.assertIn(len(path_prefix), (79, 80) if len(path_prefix) in (79, 80) else (len(path_prefix),))
        path_prefix = path_prefix.ljust(79, "a") if len(path_prefix) < 79 else path_prefix[:79]
        self.assertEqual(len(path_prefix), 79)
        log = f"{path_prefix}\nmain.tex:12: LaTeX Error: Some error message."
        unwrapped = latex_module._unwrap_tex_log(log)
        self.assertNotIn("\nmain.tex:12:", unwrapped)
        self.assertIn(f"{path_prefix}main.tex:12:", unwrapped)

    def test_find_latex_error_strips_latex_generic_continuation_markers(self):
        compiler_log = (
            "Compilation failed with error logs:\n"
            "main.tex:3: LaTeX Error: First line of error\n"
            "(LaTeX)Second line of error.\n\n"
            "Type  H <return>  for immediate help."
        )

        result = latex_module.find_latex_error(compiler_log)

        self.assertEqual(
            result,
            "LaTeX syntax error (line 3): First line of error Second line of error.",
        )

    def test_find_latex_error_handles_class_errors(self):
        compiler_log = (
            "Compilation failed with error logs:\n"
            "main.tex:5: Class standalone Error: Margin is too small for page.\n\n"
            "Type  H <return>  for immediate help."
        )

        result = latex_module.find_latex_error(compiler_log)

        self.assertEqual(
            result,
            "LaTeX syntax error (line 5): [standalone] Margin is too small for page.",
        )

    def test_find_latex_error_handles_file_line_error_standard_tex_messages(self):
        cases = [
            ("main.tex:3: Dimension too large.\nl.3 ...", "LaTeX syntax error (line 3): Dimension too large."),
            ("main.tex:4: Too many }'s.\nl.4 }", "LaTeX syntax error (line 4): Too many }'s."),
            (
                "main.tex:7: Extra alignment tab has been changed to \\cr.\nl.7 &",
                "LaTeX syntax error (line 7): Extra alignment tab has been changed to \\cr.",
            ),
        ]
        for log_snippet, expected in cases:
            compiler_log = f"Compilation failed with error logs:\n{log_snippet}"
            result = latex_module.find_latex_error(compiler_log)
            self.assertEqual(result, expected)

    def test_find_latex_error_handles_wrapped_file_line_error_standard_tex_messages(self):
        line_79 = r"main.tex:3: Incomplete \iffalse; all text was ignored after line 50. Some extra"
        self.assertEqual(len(line_79), 79)
        compiler_log = (
            "Compilation failed with error logs:\n"
            f"{line_79}\n"
            " details on next line.\n"
        )

        result = latex_module.find_latex_error(compiler_log)

        self.assertEqual(
            result,
            "LaTeX syntax error (line 3): Incomplete \\iffalse; all text was ignored after line 50. Some extra details on next line.",
        )

    def test_extract_generated_line_number_falls_back_to_l_line(self):
        log = (
            "! LaTeX Error: Something went wrong.\n"
            "...\n"
            "l.42 \\end{document}\n"
        )
        line_no = latex_module._extract_generated_line_number(log)
        self.assertEqual(line_no, 42)

    def test_extract_generated_line_number_handles_paths_with_spaces_and_quotes(self):
        log_windows = r"C:\Users\John Doe\AppData\Local\Temp\main.tex: 22: LaTeX Error: Problem"
        log_quoted = '"/tmp/path with spaces/main.tex": 33: LaTeX Error: Problem'
        self.assertEqual(latex_module._extract_generated_line_number(log_windows), 22)
        self.assertEqual(latex_module._extract_generated_line_number(log_quoted), 33)

    def test_extract_best_command_recovers_ellipsis_truncated_command(self):
        log = (
            "main.tex:3: Undefined control sequence.\n"
            "l.3 ...eryveryveryveryverylongundefinedcommandname\n"
        )
        source = r"\frac{1}{\thisisaveryveryveryveryverylongundefinedcommandname}"
        rr = latex_module.RenderRequest(
            source_expr=source,
            latex_code="",
            transparent=False,
            render_dpi=300,
            input_kind="inline",
            generated_to_user_line={3: 1},
        )
        cmd = latex_module._extract_best_command(log, rr, 1, 3)
        self.assertEqual(cmd, r"\thisisaveryveryveryveryverylongundefinedcommandname")

    def test_extract_best_command_recovers_trailing_ellipsis_command(self):
        log = (
            "main.tex:3: Undefined control sequence.\n"
            "l.3 \\thisisaveryveryveryveryverylongundefined...\n"
        )
        source = r"\frac{1}{\thisisaveryveryveryveryverylongundefinedcommandname}"
        rr = latex_module.RenderRequest(
            source_expr=source,
            latex_code="",
            transparent=False,
            render_dpi=300,
            input_kind="inline",
            generated_to_user_line={3: 1},
        )
        cmd = latex_module._extract_best_command(log, rr, 1, 3)
        self.assertEqual(cmd, r"\thisisaveryveryveryveryverylongundefinedcommandname")

    def test_find_latex_error_uses_preflight_issue_as_fallback(self):
        render_request = latex_module.RenderRequest(
            source_expr=r"\left( x+1",
            latex_code="unused",
            transparent=True,
            render_dpi=300,
            input_kind="inline",
            generated_to_user_line={},
            preflight_issue=latex_module.PreflightIssue(
                category="LaTeX syntax error",
                message=r"Missing `\right` to match `\left`.",
                line_no=1,
            ),
        )

        result = latex_module.find_latex_error(
            "Compilation failed with error logs:\n! Emergency stop.",
            render_request=render_request,
        )

        self.assertEqual(
            result,
            r"LaTeX syntax error (line 1): Missing `\right` to match `\left`.",
        )

    def test_find_latex_error_returns_sanitized_unknown_fallback_for_fatal_log(self):
        compiler_log = (
            "Compilation failed with error logs:\n"
            "main.tex:9: ==> Fatal error occurred, no output PDF file produced!"
        )

        result = latex_module.find_latex_error(compiler_log)

        self.assertEqual(result, latex_module._UNKNOWN_COMPILE_ERROR)

    def test_helper_normalizes_command_names_and_source_lines(self):
        self.assertIsNone(latex_module._normalize_command_name(None))
        self.assertIsNone(latex_module._normalize_command_name("\\"))
        self.assertEqual(latex_module._normalize_command_name(r"\text@foo"), r"\text")
        self.assertEqual(latex_module._normalize_command_name(r"\foo@"), r"\foo")
        self.assertEqual(latex_module._extract_source_line("a\nb", None), "a\nb")
        self.assertEqual(latex_module._extract_source_line("a\nb", 4), "a\nb")

    def test_helper_extracts_user_commands_and_snippet_commands(self):
        self.assertIsNone(latex_module._extract_user_command(r"\color{white}", 1))
        self.assertEqual(latex_module._extract_user_command(r"\foo + \bar", 1), r"\foo")
        self.assertEqual(latex_module._find_snippet_line_for_generated_line("ignored", None), "")
        self.assertEqual(
            latex_module._find_snippet_line_for_generated_line("l.9 \\foo + 1", 9),
            r"\foo + 1",
        )
        self.assertEqual(latex_module._extract_command_from_snippet(r"\foo@ + 1"), r"\foo")

    def test_helper_formats_unknown_environment_errors(self):
        self.assertEqual(
            latex_module._format_environment_error("mysteryenv", 4),
            "LaTeX environment error (line 4): `mysteryenv` is unavailable in this renderer "
            "or is missing a required package import.",
        )

    def test_preflight_detects_unexpected_end_environment(self):
        issue = latex_module._run_preflight_checks(r"\end{aligned}")

        self.assertEqual(
            issue,
            latex_module.PreflightIssue(
                category="LaTeX syntax error",
                message=r"Unexpected `\end{aligned}` without a matching `\begin{aligned}`.",
                line_no=1,
            ),
        )

    def test_preflight_detects_mismatched_end_environment(self):
        issue = latex_module._run_preflight_checks(
            "\\begin{aligned}\n\\end{bmatrix}"
        )

        self.assertEqual(
            issue,
            latex_module.PreflightIssue(
                category="LaTeX syntax error",
                message=r"Expected `\end{aligned}`, but found `\end{bmatrix}`.",
                line_no=2,
            ),
        )

    def test_preflight_detects_unexpected_math_block_closer(self):
        issue = latex_module._run_preflight_checks(r"\]")

        self.assertEqual(
            issue,
            latex_module.PreflightIssue(
                category="LaTeX syntax error",
                message=r"Unexpected `\]` without a matching `\[`.",
                line_no=1,
            ),
        )

    def test_preflight_detects_missing_closing_parenthesized_math_block(self):
        issue = latex_module._run_preflight_checks(r"\(x+1")

        self.assertEqual(
            issue,
            latex_module.PreflightIssue(
                category="LaTeX syntax error",
                message=r"Missing `\)` to close the math block.",
                line_no=1,
            ),
        )

    def test_preflight_accepts_balanced_math_blocks(self):
        self.assertIsNone(latex_module._run_preflight_checks(r"\[x\]"))
        self.assertIsNone(latex_module._run_preflight_checks(r"\(x\)"))
        self.assertIsNone(latex_module._run_preflight_checks(r"$x$"))
        self.assertIsNone(
            latex_module._run_preflight_checks(
                r"\[ \begin{aligned} a \\[4pt] b \end{aligned} \]"
            )
        )
        self.assertIsNone(
            latex_module._run_preflight_checks(
                r"\[ \begin{aligned} a \\(b) \end{aligned} \]"
            )
        )

    def test_preflight_accepts_matrix_with_vertical_row_spacing(self):
        expr = (
            r"{\small\setlength{\arraycolsep}{9pt}\renewcommand{\arraystretch}{1.15}" "\n"
            r"\[" "\n"
            r"\begin{aligned}" "\n"
            r"    &\left[\begin{array}{cccc|c} 0 & 0 & 1 & 1 & 3 \\ 1 & 2 & 1 & 0 & 2 \end{array}\right] \\[4pt]" "\n"
            r"    &\left[\begin{array}{cccc|c} 1 & 2 & 1 & 0 & 2 \\ 0 & 0 & 1 & 1 & 3 \end{array}\right]" "\n"
            r"\end{aligned}" "\n"
            r"\]" "\n"
            r"}"
        )
        self.assertIsNone(latex_module._run_preflight_checks(expr))

    def test_preflight_detects_missing_closing_double_dollar_math_block(self):
        issue = latex_module._run_preflight_checks(r"$$x+1")

        self.assertEqual(
            issue,
            latex_module.PreflightIssue(
                category="LaTeX syntax error",
                message="Missing closing `$$` to finish the math block.",
                line_no=1,
            ),
        )

    def test_preflight_detects_unexpected_parenthesized_math_closer(self):
        issue = latex_module._run_preflight_checks(r"\)")

        self.assertEqual(
            issue,
            latex_module.PreflightIssue(
                category="LaTeX syntax error",
                message=r"Unexpected `\)` without a matching `\(`.",
                line_no=1,
            ),
        )

    def test_preflight_detects_unexpected_right_command(self):
        issue = latex_module._run_preflight_checks(r"\right)")

        self.assertEqual(
            issue,
            latex_module.PreflightIssue(
                category="LaTeX syntax error",
                message=r"Unexpected `\right` without a matching `\left`.",
                line_no=1,
            ),
        )

    def test_preflight_accepts_balanced_left_right_commands(self):
        self.assertIsNone(latex_module._run_preflight_checks(r"\left( x \right)"))

    def test_preflight_detects_unexpected_closing_brace(self):
        issue = latex_module._run_preflight_checks("}")

        self.assertEqual(
            issue,
            latex_module.PreflightIssue(
                category="LaTeX syntax error",
                message="Unexpected `}` without a matching `{`.",
                line_no=1,
            ),
        )

    def test_preflight_ignores_commented_unsupported_feature(self):
        issue = latex_module._run_preflight_checks("% \\usepackage{minted}")

        self.assertIsNone(issue)

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

    def test_text_to_latex_counts_literal_latex_prefix_toward_input_limit(self):
        result = latex_module.text_to_latex(
            "latex " + ("x" * latex_module.MAX_LATEX_INPUT_CHARS),
            "unused_output",
        )

        self.assertEqual(
            result,
            "Input too long: 3006 characters. Max is 3000 characters.",
        )

    def test_text_to_latex_surfaces_truncated_tikz_documents_as_length_errors(self):
        prefix = r"\begin{tikzpicture}\draw (0,0) -- (1,1);"
        expr = prefix + ("x" * (latex_module.MAX_LATEX_INPUT_CHARS - len(prefix)))

        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = str(Path(temp_dir) / "truncated_tikz")
            with patch.object(
                latex_module,
                "_render_png_request",
                side_effect=Exception("! File ended while scanning use of \\end ."),
            ):
                result = latex_module.text_to_latex(expr, output_base)

        self.assertEqual(
            result,
            "Input too long: TikZ document exceeded the 3000 character limit and was truncated.",
        )

    def test_text_to_latex_returns_friendly_missing_brace_error_before_compile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = str(Path(temp_dir) / "missing_brace")
            with patch.object(latex_module, "InlineDviPngRenderer") as mock_dvipng_renderer, patch.object(
                latex_module,
                "Latex2PNG",
            ) as mock_latex2png:
                result = latex_module.text_to_latex(r"\frac{1}{2", output_base)

        self.assertEqual(
            result,
            "LaTeX syntax error (line 1): Missing `}` to finish `\\frac{...}{...}`.",
        )
        mock_dvipng_renderer.assert_not_called()
        mock_latex2png.assert_not_called()

    def test_text_to_latex_returns_friendly_unsupported_feature_error_before_compile(self):
        expr = "\\usepackage{minted}\n\\begin{document}x\\end{document}"

        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = str(Path(temp_dir) / "minted")
            with patch.object(latex_module, "InlineDviPngRenderer") as mock_dvipng_renderer, patch.object(
                latex_module,
                "Latex2PNG",
            ) as mock_latex2png:
                result = latex_module.text_to_latex(expr, output_base)

        self.assertEqual(
            result,
            "Unsupported LaTeX feature (line 1): package `minted` requires shell escape, "
            "which this renderer disables.",
        )
        mock_dvipng_renderer.assert_not_called()
        mock_latex2png.assert_not_called()

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

    def test_remove_superfluous_treats_latex_prefix_as_literal_input(self):
        result = latex_module.remove_superfluous(r"latex \alpha + \beta")

        self.assertEqual(result, r"$\displaystyle latex \alpha + \beta$")

    def test_normalize_full_document_adds_standalone_class_when_missing(self):
        result = latex_module._normalize_full_document(r"\begin{document}x\end{document}")

        self.assertTrue(result.startswith(r"\documentclass[varwidth,border=1mm]{standalone}"))
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
        self.assertIn(r"\documentclass[varwidth,border=1mm]{standalone}", compile_args[0])
        self.assertIn(r"\begin{document}x\end{document}", compile_args[0])
        self.assertEqual(compile_kwargs["compiler"], "pdflatex")
        self.assertEqual(compile_kwargs["dpi"], 410)
        self.assertFalse(compile_kwargs["transparent"])

    def test_text_to_latex_renders_document_with_display_math_and_text(self):
        png_payload = PNG_SIGNATURE + b"doc-math-payload"
        user_snippet = (
            "\\begin{document}\n\n"
            "we can assume $\\angle POQ = \\angle OQR = 60^\\circ$\n\n"
            "\\[\n"
            "because A = (4 \\cdot 11) - \\left(\\frac{60}{360} \\cdot \\pi \\cdot 4^2\\right)\n"
            "\\]\n\n"
            "\\end{document}"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = str(Path(temp_dir) / "render_doc_math")
            with patch.object(latex_module, "InlineDviPngRenderer") as mock_dvipng_renderer, patch.object(
                latex_module,
                "Latex2PNG",
            ) as mock_latex2png:
                mock_renderer = mock_latex2png.return_value
                mock_renderer.compile.return_value = png_payload

                result = latex_module.text_to_latex(user_snippet, output_base, dpi=300)

            output_path = Path(f"{output_base}.png")
            self.assertEqual(result, True)
            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_bytes(), png_payload)
            mock_dvipng_renderer.assert_not_called()
            mock_renderer.compile.assert_called_once()
            compile_args, compile_kwargs = mock_renderer.compile.call_args
            self.assertIn(r"\documentclass[varwidth,border=1mm]{standalone}", compile_args[0])
            self.assertIn(r"we can assume $\angle POQ = \angle OQR = 60^\circ$", compile_args[0])
            self.assertEqual(compile_kwargs["compiler"], "pdflatex")
            self.assertEqual(compile_kwargs["dpi"], 300)

    def test_format_source_snippet_multiline_context(self):
        expr = "line 1\nline 2\nline 3\nline 4\nline 5"
        # 3-line context around line 3: lines 2, 3, 4
        snippet = latex_module._format_source_snippet(expr, line_no=3, context_lines=1)
        expected = "  2 | line 2\n> 3 | line 3\n  4 | line 4"
        self.assertEqual(snippet, expected)

    def test_format_source_snippet_single_line_context(self):
        expr = "line 1\nline 2\nline 3\nline 4\nline 5"
        # context_lines=0 should produce a single line snippet
        snippet = latex_module._format_source_snippet(expr, line_no=3, context_lines=0)
        self.assertEqual(snippet, "> 3 | line 3")

    def test_format_source_snippet_boundary_first_line(self):
        expr = "first line\nsecond line\nthird line"
        # At line 1, there is no line before; should show lines 1 and 2
        snippet = latex_module._format_source_snippet(expr, line_no=1, context_lines=1)
        expected = "> 1 | first line\n  2 | second line"
        self.assertEqual(snippet, expected)

    def test_format_source_snippet_boundary_last_line(self):
        expr = "first line\nsecond line\nthird line"
        # At last line (3), there is no line after; should show lines 2 and 3
        snippet = latex_module._format_source_snippet(expr, line_no=3, context_lines=1)
        expected = "  2 | second line\n> 3 | third line"
        self.assertEqual(snippet, expected)

    def test_format_source_snippet_preserves_empty_target_line(self):
        # Reproduce the user's issue: line 10 is an empty line following \\
        lines = [
            r"1 &= 1 \\",
            r"2 &= 2 \\",
            r"3 &= 3 \\",
            r"4 &= 4 \\",
            r"5 &= 5 \\",
            r"6 &= 6 \\",
            r"7 &= 7 \\",
            r"8 &= 8 \\",
            r"9 &= 9 \\",
            "",
            r"11 &= 11",
        ]
        expr = "\n".join(lines)
        snippet = latex_module._format_source_snippet(expr, line_no=10, context_lines=1)
        self.assertIsNotNone(snippet)
        expected = "   9 | 9 &= 9 \\\\\n> 10 |\n  11 | 11 &= 11"
        self.assertEqual(snippet, expected)

    def test_format_source_snippet_preserves_empty_context_lines(self):
        # Empty lines before and after target line should be preserved
        expr = "line 1\n\nline 3\n\nline 5"
        snippet = latex_module._format_source_snippet(expr, line_no=3, context_lines=1)
        expected = "  2 |\n> 3 | line 3\n  4 |"
        self.assertEqual(snippet, expected)

    def test_format_source_snippet_all_empty_lines(self):
        expr = "\n\n\n"
        snippet = latex_module._format_source_snippet(expr, line_no=2, context_lines=1)
        expected = "  1 |\n> 2 |\n  3 |"
        self.assertEqual(snippet, expected)

    def test_format_source_snippet_aligned_line_numbers_and_pointer(self):
        expr = "\\begin{align*}\na &= 1 \\\\\nb &= 2 \\\\\nc &= 3 \\\\\nd &= 4\n\\end{align*}"
        snippet = latex_module._format_source_snippet(expr, line_no=3, context_lines=1)
        self.assertIsNotNone(snippet)
        lines = snippet.splitlines()
        self.assertEqual(len(lines), 3)
        # Context lines should start with spaces without blockquotes, and error line has '>' pointer
        self.assertTrue(lines[0].startswith("  2 |"), f"Line 2 unexpected prefix: {lines[0]}")
        self.assertTrue(lines[1].startswith("> 3 |"), f"Line 3 unexpected prefix: {lines[1]}")
        self.assertTrue(lines[2].startswith("  4 |"), f"Line 4 unexpected prefix: {lines[2]}")

    def test_format_source_snippet_single_line_expression(self):
        expr = r"\frac{1}{2"
        # By default, single-line expressions return None to preserve compact formatting
        self.assertIsNone(latex_module._format_source_snippet(expr, line_no=1))
        # With require_multiline=False, it formats the single line
        snippet = latex_module._format_source_snippet(
            expr, line_no=1, require_multiline=False
        )
        self.assertEqual(snippet, r"> 1 | \frac{1}{2")

    def test_format_source_snippet_invalid_inputs_and_bounds(self):
        expr = "line 1\nline 2\nline 3"
        self.assertIsNone(latex_module._format_source_snippet(None, 1))
        self.assertIsNone(latex_module._format_source_snippet("", 1))
        self.assertIsNone(latex_module._format_source_snippet(expr, None))
        self.assertIsNone(latex_module._format_source_snippet(expr, line_no=0))
        self.assertIsNone(latex_module._format_source_snippet(expr, line_no=-1))
        self.assertIsNone(latex_module._format_source_snippet(expr, line_no=4))

    def test_format_source_snippet_truncates_long_lines(self):
        long_line = "a" * 120
        expr = f"short line 1\n{long_line}\nshort line 3"
        snippet = latex_module._format_source_snippet(
            expr, line_no=2, context_lines=1, max_line_length=50
        )
        self.assertIsNotNone(snippet)
        expected_truncated = "a" * 47 + "..."
        self.assertIn(f"> 2 | {expected_truncated}", snippet)

    def test_format_source_snippet_respects_max_total_length(self):
        expr = "line 1\nline 2\nline 3\nline 4\nline 5"
        # With context_lines=2, 5 lines would normally be formatted.
        # Restrict max_total_length so outer lines are dropped.
        snippet = latex_module._format_source_snippet(
            expr, line_no=3, context_lines=2, max_total_length=35
        )
        self.assertIsNotNone(snippet)
        self.assertLessEqual(len(snippet), 35)
        self.assertIn("> 3 | line 3", snippet)

    def test_format_user_error_with_snippet(self):
        snippet = "  2 | line 2\n> 3 | line 3\n  4 | line 4"
        error_msg = latex_module._format_user_error(
            "LaTeX syntax error",
            "Something failed.",
            line_no=3,
            snippet=snippet,
        )
        expected = (
            "LaTeX syntax error (line 3): Something failed.\n"
            "```text\n"
            "  2 | line 2\n"
            "> 3 | line 3\n"
            "  4 | line 4\n"
            "```"
        )
        self.assertEqual(error_msg, expected)

    def test_format_user_error_respects_max_length(self):
        long_message = "x" * 600
        error_msg = latex_module._format_user_error(
            "LaTeX syntax error",
            long_message,
            line_no=1,
        )
        self.assertLessEqual(len(error_msg), 500)
        self.assertTrue(error_msg.endswith("..."))

    def test_format_user_error_truncation_preserves_code_block_fence(self):
        snippet = "  2 | line 2\n> 3 | line 3\n  4 | line 4"
        error_msg = latex_module._format_user_error(
            "LaTeX syntax error",
            "Failed.",
            line_no=3,
            snippet=snippet,
            max_length=65,
        )
        self.assertLessEqual(len(error_msg), 65)
        self.assertIn("```text\n", error_msg)
        self.assertTrue(
            error_msg.endswith("\n```"),
            f"Error message did not end with closing code block fence: {error_msg}",
        )

    def test_format_user_error_truncation_drops_code_block_when_insufficient_space(self):
        snippet = "  2 | line 2\n> 3 | line 3\n  4 | line 4"
        # Header is: "LaTeX syntax error (line 3): Failed." (37 chars)
        # If max_length is 45, overhead is 13 chars (37 + 13 = 50 > 45), so code fence cannot fit
        error_msg = latex_module._format_user_error(
            "LaTeX syntax error",
            "Failed.",
            line_no=3,
            snippet=snippet,
            max_length=45,
        )
        self.assertLessEqual(len(error_msg), 45)
        self.assertNotIn("```", error_msg)
        self.assertEqual(error_msg, "LaTeX syntax error (line 3): Failed.")

    def test_format_user_error_preserves_literal_backslashes_in_snippet(self):
        # Ensure LaTeX backslashes (such as \\ linebreaks) are preserved literally
        snippet = r"   9 | 9 &= 9 \\" + "\n" + r"> 10 |" + "\n" + r"  11 | 11 &= 11"
        error_msg = latex_module._format_user_error(
            "LaTeX syntax error",
            "Missing delimiter.",
            line_no=10,
            snippet=snippet,
        )
        self.assertIn(r"   9 | 9 &= 9 \\", error_msg)
        self.assertIn("```text\n", error_msg)
        self.assertIn("\n```", error_msg)

    def test_format_source_snippet_single_line_with_trailing_newline_returns_none(self):
        # Single-line expressions with trailing newline characters (\n or \r\n)
        # must still return None when require_multiline=True
        expr_lf = r"\frac{1}{2}" + "\n"
        self.assertIsNone(latex_module._format_source_snippet(expr_lf, line_no=1))

        expr_crlf = r"\frac{1}{2}" + "\r\n"
        self.assertIsNone(latex_module._format_source_snippet(expr_crlf, line_no=1))

    def test_format_source_snippet_cr_newlines(self):
        # Multiline expression using classic CR line breaks
        expr = "line 1\rline 2\rline 3"
        snippet = latex_module._format_source_snippet(expr, line_no=2, context_lines=1)
        expected = "  1 | line 1\n> 2 | line 2\n  3 | line 3"
        self.assertEqual(snippet, expected)

    def test_format_source_snippet_small_limits_do_not_expand(self):
        # When max_line_length <= 3 or max_total_length <= 3, ensure string is clamped without expanding
        expr = "line 1\nline 2"
        snippet = latex_module._format_source_snippet(
            expr, line_no=1, context_lines=0, max_line_length=2, max_total_length=20
        )
        self.assertIsNotNone(snippet)
        # The content on line 1 ("line 1") truncated to 2 chars should be "li"
        self.assertIn("> 1 | li", snippet)

        snippet_tiny_total = latex_module._format_source_snippet(
            expr, line_no=1, context_lines=0, max_total_length=2
        )
        self.assertIsNotNone(snippet_tiny_total)
        self.assertLessEqual(len(snippet_tiny_total), 2)

    def test_format_source_snippet_invalid_line_no_types(self):
        expr = "line 1\nline 2"
        self.assertIsNone(latex_module._format_source_snippet(expr, line_no=1.5))
        self.assertIsNone(latex_module._format_source_snippet(expr, line_no=True))
        self.assertIsNone(latex_module._format_source_snippet(expr, line_no=False))
        self.assertIsNone(latex_module._format_source_snippet(expr, line_no="1"))

    def test_format_user_error_small_max_length_does_not_expand(self):
        # When max_length <= 3, ensure output does not expand due to negative slice indices
        error_msg = latex_module._format_user_error("Err", "Message", max_length=2)
        self.assertLessEqual(len(error_msg), 2)

    def test_format_user_error_invalid_line_no_types(self):
        # When line_no is a boolean or float, format without line number
        error_msg = latex_module._format_user_error("LaTeX syntax error", "Failed.", line_no=True)
        self.assertEqual(error_msg, "LaTeX syntax error: Failed.")

        error_msg = latex_module._format_user_error("LaTeX syntax error", "Failed.", line_no=1.5)
        self.assertEqual(error_msg, "LaTeX syntax error: Failed.")

    def test_format_user_error_zero_and_negative_line_no(self):
        # Line numbers <= 0 are invalid for 1-indexed source code and should be omitted
        error_msg_zero = latex_module._format_user_error("LaTeX syntax error", "Failed.", line_no=0)
        self.assertEqual(error_msg_zero, "LaTeX syntax error: Failed.")

        error_msg_neg = latex_module._format_user_error("LaTeX syntax error", "Failed.", line_no=-5)
        self.assertEqual(error_msg_neg, "LaTeX syntax error: Failed.")

    def test_format_user_error_zero_and_negative_max_length(self):
        # When max_length <= 0, return empty string
        self.assertEqual(latex_module._format_user_error("Err", "Message", max_length=0), "")
        self.assertEqual(latex_module._format_user_error("Err", "Message", max_length=-1), "")

    def test_format_user_error_sanitizes_triple_backticks_in_snippet(self):
        # Backticks inside user code (e.g. % ```) must not break Discord code block fences
        triple_bt = chr(96) * 3
        quad_bt = chr(96) * 4
        snippet = f"  2 | % {triple_bt}\n> 3 | \\badcmd\n  4 | % {quad_bt}"
        error_msg = latex_module._format_user_error(
            "LaTeX command error",
            "Undefined command.",
            line_no=3,
            snippet=snippet,
        )
        self.assertIn("```text\n", error_msg)
        self.assertTrue(error_msg.endswith("\n```"))
        # Inside the fences, raw 3-consecutive-backtick runs must be broken with zero-width spaces
        body = error_msg[len("LaTeX command error (line 3): Undefined command.\n```text\n") : -len("\n```")]
        self.assertNotIn(triple_bt, body)
        self.assertIn("> 3 | \\badcmd", body)

    def test_format_user_error_unwraps_pre_fenced_snippet(self):
        # Passing an already-fenced snippet should not produce nested ``` fences
        snippet = "```text\n  2 | line 2\n> 3 | line 3\n```"
        error_msg = latex_module._format_user_error(
            "LaTeX syntax error",
            "Failed.",
            line_no=3,
            snippet=snippet,
        )
        self.assertEqual(error_msg.count("```"), 2)
        self.assertIn("```text\n  2 | line 2\n> 3 | line 3\n```", error_msg)

    def test_format_source_snippet_as_code_block(self):
        expr = "line 1\nline 2\nline 3"
        snippet = latex_module._format_source_snippet(
            expr, line_no=2, context_lines=1, as_code_block=True
        )
        self.assertIsNotNone(snippet)
        self.assertTrue(snippet.startswith("```text\n"))
        self.assertTrue(snippet.endswith("\n```"))
        self.assertIn("  1 | line 1\n> 2 | line 2\n  3 | line 3", snippet)

    def test_format_source_snippet_as_code_block_respects_max_total_length(self):
        expr = "line 1\nline 2\nline 3\nline 4\nline 5"
        snippet = latex_module._format_source_snippet(
            expr, line_no=3, context_lines=2, max_total_length=35, as_code_block=True
        )
        self.assertIsNotNone(snippet)
        self.assertLessEqual(len(snippet), 35)
        self.assertTrue(snippet.startswith("```text\n"))
        self.assertTrue(snippet.endswith("\n```"))

    def test_format_source_snippet_zero_and_negative_limits(self):
        expr = "line 1\nline 2"
        snippet_zero_line = latex_module._format_source_snippet(
            expr, line_no=1, context_lines=0, max_line_length=0
        )
        self.assertIsNotNone(snippet_zero_line)
        self.assertEqual(snippet_zero_line, "> 1 |")

        snippet_zero_total = latex_module._format_source_snippet(
            expr, line_no=1, context_lines=0, max_total_length=0
        )
        self.assertEqual(snippet_zero_total, "")


if __name__ == "__main__":
    unittest.main()
