import logging
import re
from dataclasses import dataclass, field

from modified_packages import InlineDviPngRenderer, Latex2PNG

_logger = logging.getLogger(__name__)
_UNKNOWN_COMPILE_ERROR = (
    "LaTeX syntax error: this code is incomplete or unsupported in this renderer."
)
MAX_LATEX_INPUT_CHARS = 3000
MAX_RENDER_DPI = 800
_COMPILER_LOG_PREFIX = "Compilation failed with error logs:"
_STRUCTURED_STANDALONE_ENV_RE = re.compile(
    r"\\begin\{(?:tikzpicture|tikzcd|circuitikz|pgfpicture|axis)\}"
)
_PREAMBLE_LINE_RE = re.compile(
    r"(?m)^\s*\\(?:usepackage|usetikzlibrary|RequirePackage|pgfplotsset|tikzset)\b"
)
_RAW_TIKZ_BODY_CMD_RE = re.compile(
    r"\\(?:draw|node|path|coordinate|filldraw|shade|fill|clip|scope|foreach)\b"
)
_TRUNCATED_COMPLEX_DOC_ERROR_RE = re.compile(
    r"file ended while scanning use of\s+\\end\b",
    re.IGNORECASE,
)
_COMMAND_TOKEN_RE = re.compile(r"\\+[A-Za-z@]+")
_ENVIRONMENT_TOKEN_RE = re.compile(r"\\(begin|end)\{([^}]+)\}")
_PACKAGE_IMPORT_RE = re.compile(
    r"\\(?:usepackage|RequirePackage)(?:\[[^\]]*\])?\{([^}]+)\}",
    re.IGNORECASE,
)
_COMMENT_RE = re.compile(r"(?<!\\)%.*$")
_SHELL_ESCAPE_PATTERNS = (
    (
        re.compile(
            r"\\usepackage(?:\[[^\]]*\])?\{[^}]*\bminted\b[^}]*\}",
            re.IGNORECASE,
        ),
        "package `minted` requires shell escape, which this renderer disables.",
    ),
    (
        re.compile(
            r"\\(?:begin\{minted\}|mintinline\b|inputminted\b)",
            re.IGNORECASE,
        ),
        "the `minted` feature requires shell escape, which this renderer disables.",
    ),
    (
        re.compile(
            r"\\usepackage(?:\[[^\]]*\])?\{[^}]*\bpythontex\b[^}]*\}",
            re.IGNORECASE,
        ),
        "package `pythontex` requires external code execution, which this renderer disables.",
    ),
    (
        re.compile(
            r"\\(?:begin\{pythontex\}|py\b|pyc\b|pyfile\b)",
            re.IGNORECASE,
        ),
        "the `pythontex` feature requires external code execution, which this renderer disables.",
    ),
)
_ENVIRONMENT_PACKAGE_HINTS = {
    "tikzcd": "tikz-cd",
    "circuitikz": "circuitikz",
    "axis": "pgfplots",
}
_COMMAND_CLOSE_HINTS = {
    r"\frac": r"Missing `}` to finish `\frac{...}{...}`.",
    r"\sqrt": r"Missing `}` to finish `\sqrt{...}`.",
    r"\text": r"Missing `}` to finish `\text{...}`.",
}
_IGNORE_WRAPPER_COMMANDS = {
    r"\displaystyle",
    r"\color",
    r"\begin",
    r"\end",
}
_FRIENDLY_ERROR_PREFIXES = (
    "input too long:",
    "dpi too large:",
    "latex dependency error:",
    "latex syntax error:",
    "latex command error:",
    "latex environment error:",
    "unsupported latex feature:",
)


@dataclass(frozen=True)
class PreflightIssue:
    category: str
    message: str
    line_no: int | None = None


@dataclass(frozen=True)
class RenderRequest:
    source_expr: str
    latex_code: str
    transparent: bool
    render_dpi: int
    input_kind: str
    generated_to_user_line: dict[int, int] = field(default_factory=dict)
    preflight_issue: PreflightIssue | None = None

_DVIPNG_FAST_PATH_BLOCKLIST = (
    r"\\documentclass\b",
    r"\\begin\{document\}",
    r"\\end\{document\}",
    r"\\usepackage\b",
    r"\\(?:re)?newcommand\b",
    r"\\providecommand\b",
    r"\\DeclareMathOperator\b",
    r"\\def\b",
    r"\\let\b",
    r"\\includegraphics\b",
    r"\\graphicspath\b",
    r"\\input\b",
    r"\\include\b",
    r"\\import\b",
    r"\\subimport\b",
    r"\\tikz\b",
    r"\\pgf(?:plots|keys)?\b",
    r"\\usetikzlibrary\b",
    r"\\begin\{(?:tikzpicture|tikzcd|circuitikz|pgfpicture|axis|figure|table|tabular\*?|tabularx|verbatim|lstlisting|minted|minipage|itemize|enumerate|description)\}",
    r"\\end\{(?:tikzpicture|tikzcd|circuitikz|pgfpicture|axis|figure|table|tabular\*?|tabularx|verbatim|lstlisting|minted|minipage|itemize|enumerate|description)\}",
)


# Should Fork or was it pork :)


def _matched_dvipng_block_pattern(expr: str) -> str | None:
    stripped = _strip_legacy_latex_prefix(expr).strip()
    for pattern in _DVIPNG_FAST_PATH_BLOCKLIST:
        if re.search(pattern, stripped):
            return pattern
    return None


def _format_user_error(prefix: str, message: str, line_no: int | None = None) -> str:
    if line_no is None:
        output = f"{prefix}: {message}"
    else:
        output = f"{prefix} (line {line_no}): {message}"
    return output if len(output) <= 500 else output[:497] + "..."


def _format_preflight_issue(issue: PreflightIssue) -> str:
    return _format_user_error(issue.category, issue.message, issue.line_no)


def _strip_comments_preserving_lines(expr: str) -> str:
    return "\n".join(_COMMENT_RE.sub("", line) for line in expr.splitlines())


def _line_number_at_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, max(offset, 0)) + 1


def _split_leading_preamble_lines_with_index(content: str) -> tuple[list[str], str, int]:
    lines = content.splitlines()
    preamble: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if re.match(
            r"^\s*\\(?:usepackage|usetikzlibrary|RequirePackage|pgfplotsset|tikzset)\b",
            line,
        ):
            preamble.append(line)
            i += 1
        elif not line.strip():
            i += 1
        else:
            break
    body = "\n".join(lines[i:]).strip()
    return preamble, body, i + 1


def _identity_line_map(text: str) -> dict[int, int]:
    lines = text.splitlines() or [text]
    return {index: index for index in range(1, len(lines) + 1)}


def _offset_line_map(text: str, generated_start_line: int, user_start_line: int = 1) -> dict[int, int]:
    lines = text.splitlines() or [text]
    return {
        generated_start_line + index: user_start_line + index
        for index in range(len(lines))
    }


def _offset_mapping(mapping: dict[int, int], line_offset: int) -> dict[int, int]:
    return {line_no + line_offset: user_line for line_no, user_line in mapping.items()}


def _normalize_command_name(command: str | None) -> str | None:
    if not command:
        return None
    stripped = command.lstrip("\\")
    if not stripped:
        return None
    normalized = "\\" + stripped
    if normalized.startswith(r"\text@"):
        return r"\text"
    if normalized.endswith("@"):
        normalized = normalized[:-1]
    return normalized


def _format_missing_closing_brace_message(command: str | None) -> str:
    normalized = _normalize_command_name(command)
    return _COMMAND_CLOSE_HINTS.get(
        normalized,
        "Missing `}` to close this group or command argument.",
    )


def _extract_source_line(expr: str, line_no: int | None) -> str:
    if line_no is None:
        return expr
    lines = expr.splitlines()
    if 1 <= line_no <= len(lines):
        return lines[line_no - 1]
    return expr


def _extract_user_command(expr: str, line_no: int | None) -> str | None:
    source_line = _extract_source_line(expr, line_no)
    commands = [_normalize_command_name(match.group(0)) for match in _COMMAND_TOKEN_RE.finditer(source_line)]
    for command in commands:
        if command and command not in _IGNORE_WRAPPER_COMMANDS:
            return command
    return None


def _parse_imported_packages(expr: str) -> set[str]:
    packages: set[str] = set()
    for match in _PACKAGE_IMPORT_RE.finditer(expr):
        for package_name in match.group(1).split(","):
            normalized = package_name.strip().lower()
            if normalized:
                packages.add(normalized)
    return packages


def _detect_unsupported_feature(expr: str) -> PreflightIssue | None:
    for pattern, message in _SHELL_ESCAPE_PATTERNS:
        match = pattern.search(expr)
        if match:
            return PreflightIssue(
                category="Unsupported LaTeX feature",
                message=message,
                line_no=_line_number_at_offset(expr, match.start()),
            )
    return None


def _detect_environment_balance_issue(expr: str) -> PreflightIssue | None:
    stack: list[tuple[str, int]] = []
    for match in _ENVIRONMENT_TOKEN_RE.finditer(expr):
        token_type = match.group(1)
        env_name = match.group(2).strip()
        line_no = _line_number_at_offset(expr, match.start())
        if token_type == "begin":
            stack.append((env_name, line_no))
            continue
        if not stack:
            return PreflightIssue(
                category="LaTeX syntax error",
                message=f"Unexpected `\\end{{{env_name}}}` without a matching `\\begin{{{env_name}}}`.",
                line_no=line_no,
            )
        open_env, open_line = stack[-1]
        if open_env != env_name:
            return PreflightIssue(
                category="LaTeX syntax error",
                message=f"Expected `\\end{{{open_env}}}`, but found `\\end{{{env_name}}}`.",
                line_no=line_no,
            )
        stack.pop()

    if stack:
        env_name, line_no = stack[-1]
        return PreflightIssue(
            category="LaTeX syntax error",
            message=f"Missing `\\end{{{env_name}}}` to close the environment.",
            line_no=line_no,
        )
    return None


def _detect_math_delimiter_issue(expr: str) -> PreflightIssue | None:
    single_dollar_open_line: int | None = None
    double_dollar_open_line: int | None = None
    bracket_stack: list[tuple[str, int]] = []
    i = 0
    line_no = 1
    while i < len(expr):
        if expr[i] == "\n":
            line_no += 1
            i += 1
            continue
        if expr.startswith(r"\[", i):
            bracket_stack.append((r"\[", line_no))
            i += 2
            continue
        if expr.startswith(r"\]", i):
            if not bracket_stack or bracket_stack[-1][0] != r"\[":
                return PreflightIssue(
                    category="LaTeX syntax error",
                    message=r"Unexpected `\]` without a matching `\[`.",
                    line_no=line_no,
                )
            bracket_stack.pop()
            i += 2
            continue
        if expr.startswith(r"\(", i):
            bracket_stack.append((r"\(", line_no))
            i += 2
            continue
        if expr.startswith(r"\)", i):
            if not bracket_stack or bracket_stack[-1][0] != r"\(":
                return PreflightIssue(
                    category="LaTeX syntax error",
                    message=r"Unexpected `\)` without a matching `\(`.",
                    line_no=line_no,
                )
            bracket_stack.pop()
            i += 2
            continue
        if expr[i] == "$" and (i == 0 or expr[i - 1] != "\\"):
            if i + 1 < len(expr) and expr[i + 1] == "$" and (i == 0 or expr[i - 1] != "\\"):
                if double_dollar_open_line is None:
                    double_dollar_open_line = line_no
                else:
                    double_dollar_open_line = None
                i += 2
                continue
            if single_dollar_open_line is None:
                single_dollar_open_line = line_no
            else:
                single_dollar_open_line = None
        i += 1

    if bracket_stack:
        opener, opener_line = bracket_stack[-1]
        closer = r"\]" if opener == r"\[" else r"\)"
        return PreflightIssue(
            category="LaTeX syntax error",
            message=f"Missing `{closer}` to close the math block.",
            line_no=opener_line,
        )
    if double_dollar_open_line is not None:
        return PreflightIssue(
            category="LaTeX syntax error",
            message="Missing closing `$$` to finish the math block.",
            line_no=double_dollar_open_line,
        )
    if single_dollar_open_line is not None:
        return PreflightIssue(
            category="LaTeX syntax error",
            message="Missing closing `$` to finish the math expression.",
            line_no=single_dollar_open_line,
        )
    return None


def _detect_left_right_issue(expr: str) -> PreflightIssue | None:
    stack: list[int] = []
    for match in re.finditer(r"\\(?:left|right)\b", expr):
        token = match.group(0)
        line_no = _line_number_at_offset(expr, match.start())
        if token == r"\left":
            stack.append(line_no)
            continue
        if not stack:
            return PreflightIssue(
                category="LaTeX syntax error",
                message=r"Unexpected `\right` without a matching `\left`.",
                line_no=line_no,
            )
        stack.pop()
    if stack:
        return PreflightIssue(
            category="LaTeX syntax error",
            message=r"Missing `\right` to match `\left`.",
            line_no=stack[-1],
        )
    return None


def _detect_brace_issue(expr: str) -> PreflightIssue | None:
    stack: list[tuple[int, int]] = []
    i = 0
    line_no = 1
    while i < len(expr):
        char = expr[i]
        if char == "\n":
            line_no += 1
            i += 1
            continue
        if char == "\\":
            i += 2
            continue
        if char == "{":
            stack.append((line_no, i))
        elif char == "}":
            if not stack:
                return PreflightIssue(
                    category="LaTeX syntax error",
                    message="Unexpected `}` without a matching `{`.",
                    line_no=line_no,
                )
            stack.pop()
        i += 1

    if not stack:
        return None

    open_line, open_offset = stack[-1]
    command = None
    for match in _COMMAND_TOKEN_RE.finditer(expr[:open_offset]):
        command = match.group(0)
    return PreflightIssue(
        category="LaTeX syntax error",
        message=_format_missing_closing_brace_message(command),
        line_no=open_line,
    )


def _detect_missing_environment_package(expr: str) -> PreflightIssue | None:
    imported_packages = _parse_imported_packages(expr)
    for match in re.finditer(r"\\begin\{([^}]+)\}", expr):
        env_name = match.group(1).strip()
        required_package = _ENVIRONMENT_PACKAGE_HINTS.get(env_name.lower())
        if required_package and required_package.lower() not in imported_packages:
            return PreflightIssue(
                category="LaTeX environment error",
                message=f"`{env_name}` requires `\\usepackage{{{required_package}}}` in the preamble.",
                line_no=_line_number_at_offset(expr, match.start()),
            )
    return None


def _run_preflight_checks(expr: str) -> PreflightIssue | None:
    checked_expr = _strip_comments_preserving_lines(expr)
    for detector in (
        _detect_unsupported_feature,
        _detect_environment_balance_issue,
        _detect_math_delimiter_issue,
        _detect_left_right_issue,
        _detect_brace_issue,
        _detect_missing_environment_package,
    ):
        issue = detector(checked_expr)
        if issue:
            return issue
    return None


def text_to_latex(expr: str, output_file: str, dpi=300) -> bool | str:
    """
    Converts LaTeX input to a PNG file.
    Returns True on success, or a user-facing error string on failure.

    Precondition: The text must be properly formatted in LaTeX.

    Attributes:
     expr: str
     output_file: str
     dpi=(1000 , optional) int | sets resolution
    """

    expr = _strip_legacy_latex_prefix(expr)

    if len(expr) > MAX_LATEX_INPUT_CHARS:
        return (
            f"Input too long: {len(expr)} characters. "
            f"Max is {MAX_LATEX_INPUT_CHARS} characters."
        )
    if dpi > MAX_RENDER_DPI:
        return f"DPI too large: {dpi}. Max is {MAX_RENDER_DPI}."
    expr = remove_hazardous_latex(expr)
    render_request = _prepare_render_request(expr, dpi)

    if render_request.preflight_issue:
        user_error = _format_preflight_issue(render_request.preflight_issue)
        _logger.warning(
            "Latex2PNG rejected invalid input output_file=%s dpi=%s expr_len=%s latex_error=%s",
            output_file,
            dpi,
            len(expr),
            user_error,
        )
        return user_error

    try:
        png_data = _render_png_request(
            expr=render_request.source_expr,
            latex_code=render_request.latex_code,
            transparent=render_request.transparent,
            render_dpi=render_request.render_dpi,
            output_file=output_file,
        )
    except Exception as exc:
        normalized_error = _normalize_error_log(exc)
        truncated_input_error = _detect_truncated_complex_input_error(
            render_request.source_expr,
            normalized_error,
        )
        if truncated_input_error:
            _logger.warning(
                "Latex2PNG rejected truncated structured input output_file=%s dpi=%s expr_len=%s",
                output_file,
                dpi,
                len(expr),
            )
            _logger.debug(
                "Latex2PNG raw compiler output output_file=%s\n%s",
                output_file,
                normalized_error,
            )
            return truncated_input_error

        user_error = find_latex_error(
            normalized_error,
            render_request=render_request,
        )

        if user_error:
            _logger.warning(
                "Latex2PNG compile failed output_file=%s dpi=%s expr_len=%s latex_error=%s",
                output_file,
                dpi,
                len(expr),
                user_error,
            )
        else:
            _logger.warning(
                "Latex2PNG compile failed output_file=%s dpi=%s expr_len=%s err=%s",
                output_file,
                dpi,
                len(expr),
                exc,
            )

        _logger.debug(
            "Latex2PNG raw compiler output output_file=%s\n%s",
            output_file,
            normalized_error,
        )
        return user_error or _UNKNOWN_COMPILE_ERROR

    png_bytes = _coerce_png_bytes(png_data, output_file)

    with open(output_file + '.png', 'wb') as f:
        f.write(png_bytes)

    _logger.debug("PNG generated output_file=%s.png", output_file)
    return True


def _is_full_document(expr: str) -> bool:
    return r"\documentclass" in expr or r"\begin{document}" in expr


def _looks_like_raw_tikz_body(expr: str) -> bool:
    """True when expr looks like TikZ drawing commands without a wrapping tikzpicture env."""
    if not expr or expr.strip() == "":
        return False
    if _STRUCTURED_STANDALONE_ENV_RE.search(expr):
        return False
    return bool(_RAW_TIKZ_BODY_CMD_RE.search(expr))


def _split_leading_preamble_lines(content: str) -> tuple[list[str], str]:
    """Split leading usepackage / tikz preamble lines from the rest of the body."""
    preamble, body, _body_start_line = _split_leading_preamble_lines_with_index(content)
    return preamble, body


def _content_suggests_tikz(latex_code: str) -> bool:
    if _STRUCTURED_STANDALONE_ENV_RE.search(latex_code):
        return True
    return _looks_like_raw_tikz_body(latex_code)


def _documentclass_options_for_content(latex_code: str) -> str:
    return "[tikz,border=6pt]" if _content_suggests_tikz(latex_code) else "[border=1mm]"


def _needs_standalone_document_shell(expr: str) -> bool:
    """
    True when input is not already a full document but needs a standalone file shell
    (TikZ / pgfplots fragments, raw TikZ commands, or leading preamble-only imports).
    """
    stripped = _strip_legacy_latex_prefix(expr).strip()
    if not stripped:
        return False
    if _is_full_document(stripped):
        return False
    if _STRUCTURED_STANDALONE_ENV_RE.search(stripped):
        return True
    if _PREAMBLE_LINE_RE.search(stripped):
        return True
    if _looks_like_raw_tikz_body(stripped):
        return True
    return False


def _is_dvipng_fast_path_eligible(expr: str) -> bool:
    stripped = _strip_legacy_latex_prefix(expr).strip()
    if not stripped or _is_full_document(stripped):
        return False

    return _matched_dvipng_block_pattern(stripped) is None


def _structured_document_kind(expr: str) -> str:
    stripped = _strip_legacy_latex_prefix(expr).strip()
    return "TikZ document" if _content_suggests_tikz(stripped) else "LaTeX document"


def _detect_truncated_complex_input_error(expr: str, log_text: str) -> str:
    stripped = _strip_legacy_latex_prefix(expr).strip()
    if len(stripped) != MAX_LATEX_INPUT_CHARS:
        return ""
    if not (_is_full_document(stripped) or _needs_standalone_document_shell(stripped)):
        return ""
    if not _TRUNCATED_COMPLEX_DOC_ERROR_RE.search(log_text):
        return ""

    return (
        f"Input too long: {_structured_document_kind(stripped)} exceeded the "
        f"{MAX_LATEX_INPUT_CHARS} character limit and was truncated."
    )


def _render_png_request(
        expr: str,
        latex_code: str,
        transparent: bool,
        render_dpi: int,
        output_file: str,
):
    if transparent and _is_dvipng_fast_path_eligible(expr):
        try:
            return InlineDviPngRenderer().compile(
                latex_code,
                transparent=transparent,
                dpi=render_dpi,
            )
        except Exception as exc:
            _logger.info(
                "InlineDviPngRenderer failed output_file=%s dpi=%s expr_len=%s; retrying pdflatex",
                output_file,
                render_dpi,
                len(expr),
            )
            _logger.debug(
                "InlineDviPngRenderer raw compiler output output_file=%s\n%s",
                output_file,
                _normalize_error_log(exc),
            )

    return Latex2PNG().compile(
        latex_code,
        transparent=transparent,
        compiler='pdflatex',
        dpi=render_dpi,
    )


def _prepare_render_request(expr: str, dpi: int) -> RenderRequest:
    stripped = _strip_legacy_latex_prefix(expr).strip()
    preflight_issue = _run_preflight_checks(stripped)
    if (
        preflight_issue
        and len(stripped) == MAX_LATEX_INPUT_CHARS
        and (_is_full_document(stripped) or _needs_standalone_document_shell(stripped))
    ):
        preflight_issue = None
    if _is_full_document(stripped) or _needs_standalone_document_shell(stripped):
        latex_code, line_map = _normalize_full_document_with_line_map(expr)
        return RenderRequest(
            source_expr=stripped,
            latex_code=latex_code,
            transparent=False,
            render_dpi=dpi,
            input_kind="structured",
            generated_to_user_line=line_map,
            preflight_issue=preflight_issue,
        )
    inline_expr = remove_superfluous(expr)
    latex_code, line_map = _build_inline_document_with_line_map(inline_expr)
    return RenderRequest(
        source_expr=stripped,
        latex_code=latex_code,
        transparent=True,
        render_dpi=dpi,
        input_kind="inline",
        generated_to_user_line=line_map,
        preflight_issue=preflight_issue,
    )


def _maybe_wrap_raw_tikz_body(body: str) -> str:
    body = body.strip()
    if not body:
        return body
    if _STRUCTURED_STANDALONE_ENV_RE.search(body):
        return body
    if _looks_like_raw_tikz_body(body):
        return "\\begin{tikzpicture}\n" + body + "\n\\end{tikzpicture}"
    return body


def _normalize_first_documentclass_if_needed(latex_code: str) -> str:
    match = re.search(r"\\documentclass(?:\[[^\]]*\])?\{([^}]+)\}", latex_code)
    if not match:
        return latex_code
    if match.group(1).strip().lower() == "standalone":
        return latex_code
    opts = _documentclass_options_for_content(latex_code)
    return re.sub(
        r"\\documentclass(?:\[[^\]]*\])?\{[^}]+\}",
        rf"\\documentclass{opts}{{standalone}}",
        latex_code,
        count=1,
    )


def _maybe_wrap_raw_tikz_body_with_line_map(
    body: str,
    body_start_line: int,
) -> tuple[str, dict[int, int]]:
    body = body.strip()
    if not body:
        return body, {}
    body_map = _offset_line_map(body, 1, body_start_line)
    if _STRUCTURED_STANDALONE_ENV_RE.search(body):
        return body, body_map
    if _looks_like_raw_tikz_body(body):
        wrapped_body = "\\begin{tikzpicture}\n" + body + "\n\\end{tikzpicture}"
        return wrapped_body, _offset_mapping(body_map, 1)
    return body, body_map


def _normalize_full_document_with_line_map(expr: str) -> tuple[str, dict[int, int]]:
    latex_code = _strip_legacy_latex_prefix(expr).strip()

    if r"\documentclass" in latex_code:
        return _normalize_first_documentclass_if_needed(latex_code), _identity_line_map(latex_code)

    if r"\begin{document}" in latex_code:
        opts = _documentclass_options_for_content(latex_code)
        return (
            rf"\documentclass{opts}{{standalone}}" "\n" f"{latex_code}",
            _offset_line_map(latex_code, 2),
        )

    preamble_lines, body, body_start_line = _split_leading_preamble_lines_with_index(latex_code)
    body_wrapped, body_map = _maybe_wrap_raw_tikz_body_with_line_map(body, body_start_line)
    opts = _documentclass_options_for_content(latex_code)

    preamble_block = ("\n".join(preamble_lines) + "\n") if preamble_lines else ""
    generated = (
        rf"\documentclass{opts}{{standalone}}" "\n"
        f"{preamble_block}"
        r"\begin{document}" "\n"
        f"{body_wrapped}\n"
        r"\end{document}"
    )
    line_map: dict[int, int] = {}
    if preamble_lines:
        line_map.update(_offset_line_map("\n".join(preamble_lines), 2, 1))
    line_map.update(_offset_mapping(body_map, len(preamble_lines) + 2))
    return generated, line_map


def _normalize_full_document(expr: str) -> str:
    return _normalize_full_document_with_line_map(expr)[0]


def _build_inline_document_with_line_map(expr: str) -> tuple[str, dict[int, int]]:
    generated = (
        r"\documentclass[border=1mm]{standalone}" "\n"
        r"\usepackage{amsmath}" "\n"
        r"\usepackage{amssymb}" "\n"
        r"\usepackage{amsfonts}" "\n"
        r"\usepackage{xcolor}" "\n"
        r"\definecolor{customtext}{HTML}{FFFFFF}" "\n"
        r"\begin{document}" "\n"
        r"\color{customtext}" "\n"
        f"{expr}\n"
        r"\end{document}"
    )
    return generated, _offset_line_map(expr, 9)


def _build_inline_document(expr: str) -> str:
    return _build_inline_document_with_line_map(expr)[0]


def _coerce_png_bytes(png_data: list[bytes] | bytes, output_file: str) -> bytes:
    if isinstance(png_data, list):
        try:
            return b''.join(png_data)
        except TypeError:
            _logger.warning("png_data list contains non-bytes items output_file=%s", output_file)
            return b''.join([item if isinstance(item, bytes) else b'' for item in png_data])
    if isinstance(png_data, bytes):
        return png_data
    raise TypeError("png_data is neither a list nor bytes.")


def _normalize_error_log(error_log: str | Exception | bytes) -> str:
    """Normalize mixed error payloads into plain newline-separated log text."""
    if isinstance(error_log, Exception):
        error_log = str(error_log)
    elif isinstance(error_log, bytes):
        error_log = error_log.decode("utf-8", errors="replace")
    elif not isinstance(error_log, str):
        error_log = str(error_log)

    error_log = error_log.replace("\\r\\n", "\n").replace("\\n", "\n")
    error_log = error_log.replace("\r\n", "\n").replace("\r", "\n")

    if _COMPILER_LOG_PREFIX in error_log:
        error_log = error_log.split(_COMPILER_LOG_PREFIX, maxsplit=1)[1]

    return error_log.strip()


def _match_known_compile_error(log_text: str) -> str:
    """Return a friendly known-error message for common dependency failures."""
    lowered = log_text.lower()
    normalized = re.sub(r"\s+", " ", lowered)

    package_missing_patterns = (
        r"latex error:\s*file\s+[`'\"]?[^\s`'\"]+\.sty[`'\"]?\s+not found",
        r"\.sty\s+not\s+found",
    )
    for pattern in package_missing_patterns:
        if re.search(pattern, normalized):
            return (
                "LaTeX dependency error: a required package is unavailable in this renderer. "
                "Try removing unsupported \\usepackage lines."
            )

    font_failure_patterns = (
        r"fontenc\.sty.*fatal error",
        r"latex font error",
        r"mktextfm",
        r"kpathsea.*font",
        r"font .* not loadable",
        r"font .* not found",
        r"metric \(tfm\) file not found",
    )
    for pattern in font_failure_patterns:
        if re.search(pattern, normalized):
            return (
                "LaTeX dependency error: required fonts are unavailable in this renderer. "
                "Try standard fonts or remove custom font settings."
            )

    return ""


def _extract_generated_line_number(log_text: str) -> int | None:
    line_match = re.search(r"[^\s:]+\.tex:(\d+):", log_text)
    return int(line_match.group(1)) if line_match else None


def _map_generated_line_number(
    generated_line_no: int | None,
    render_request: RenderRequest | None,
) -> int | None:
    if generated_line_no is None or render_request is None:
        return generated_line_no
    return render_request.generated_to_user_line.get(generated_line_no)


def _find_snippet_line_for_generated_line(log_text: str, generated_line_no: int | None) -> str:
    if generated_line_no is None:
        return ""
    match = re.search(rf"(?m)^l\.{generated_line_no}\s+(.*)$", log_text)
    return match.group(1).strip() if match else ""


def _extract_command_from_snippet(snippet_line: str) -> str | None:
    for match in _COMMAND_TOKEN_RE.finditer(snippet_line):
        command = _normalize_command_name(match.group(0))
        if command and command not in _IGNORE_WRAPPER_COMMANDS:
            return command
    return None


def _extract_best_command(
    log_text: str,
    render_request: RenderRequest | None,
    user_line_no: int | None,
    generated_line_no: int | None,
) -> str | None:
    if render_request is not None:
        command = _extract_user_command(render_request.source_expr, user_line_no)
        if command:
            return command
    return _extract_command_from_snippet(
        _find_snippet_line_for_generated_line(log_text, generated_line_no)
    )


def _format_environment_error(env_name: str, line_no: int | None) -> str:
    required_package = _ENVIRONMENT_PACKAGE_HINTS.get(env_name.lower())
    if required_package:
        return _format_user_error(
            "LaTeX environment error",
            f"`{env_name}` requires `\\usepackage{{{required_package}}}` in the preamble.",
            line_no,
        )
    return _format_user_error(
        "LaTeX environment error",
        f"`{env_name}` is unavailable in this renderer or is missing a required package import.",
        line_no,
    )


def _classify_compile_error(
    log_text: str,
    render_request: RenderRequest | None,
) -> str:
    generated_line_no = _extract_generated_line_number(log_text)
    user_line_no = _map_generated_line_number(generated_line_no, render_request)
    lowered = log_text.lower()

    file_ended_match = re.search(
        r"file ended while scanning use of\s+(\\[A-Za-z@]+)",
        log_text,
        re.IGNORECASE,
    )
    if file_ended_match:
        command = _normalize_command_name(file_ended_match.group(1))
        return _format_user_error(
            "LaTeX syntax error",
            _format_missing_closing_brace_message(command),
            user_line_no,
        )

    environment_match = re.search(
        r"environment\s+([^\s.]+)\s+undefined",
        log_text,
        re.IGNORECASE,
    )
    if environment_match:
        return _format_environment_error(environment_match.group(1), user_line_no)

    if "missing } inserted" in lowered:
        command = _extract_best_command(
            log_text,
            render_request,
            user_line_no,
            generated_line_no,
        )
        return _format_user_error(
            "LaTeX syntax error",
            _format_missing_closing_brace_message(command),
            user_line_no,
        )

    if "missing $ inserted" in lowered:
        return _format_user_error(
            "LaTeX syntax error",
            "Missing a math delimiter like `$...$` or `\\[...\\]`.",
            user_line_no,
        )

    if "undefined control sequence" in lowered:
        command = _extract_best_command(
            log_text,
            render_request,
            user_line_no,
            generated_line_no,
        )
        if command:
            return _format_user_error(
                "LaTeX command error",
                f"`{command}` is undefined. Check the command name or add the required package.",
                user_line_no,
            )
        return _format_user_error(
            "LaTeX command error",
            "An undefined command was used. Check the command name or add the required package.",
            user_line_no,
        )

    latex_error_match = re.search(r"LaTeX Error:\s*(.+)", log_text)
    if latex_error_match:
        sanitized_message = re.sub(r"\s+", " ", latex_error_match.group(1)).strip().rstrip(".")
        return _format_user_error(
            "LaTeX syntax error",
            sanitized_message + ".",
            user_line_no,
        )

    bang_match = re.search(r"(?m)^!\s+(.+)$", log_text)
    if bang_match:
        sanitized_message = re.sub(r"\s+", " ", bang_match.group(1)).strip().rstrip(".")
        if sanitized_message and not any(
            token in sanitized_message.lower()
            for token in ("fatal error", "emergency stop", "runaway argument")
        ):
            return _format_user_error(
                "LaTeX syntax error",
                sanitized_message + ".",
                user_line_no,
            )

    if render_request and render_request.preflight_issue:
        return _format_preflight_issue(render_request.preflight_issue)

    if any(
        token in lowered
        for token in (
            "fatal error occurred",
            "emergency stop",
            "runaway argument",
            "missing \\endgroup inserted",
        )
    ):
        return _UNKNOWN_COMPILE_ERROR

    return ""


def find_latex_error(
    error_log: str | Exception | bytes,
    render_request: RenderRequest | None = None,
) -> str:
    """
    Will take an exception error, and parse the error into a str

    -NOTE- | Attributes are str, exception and bytes
    for different operating system compatability issues

    Attributes
        error_log: str | Exception | bytes
    """
    normalized_log = _normalize_error_log(error_log)
    known_error = _match_known_compile_error(normalized_log)
    if known_error:
        return known_error

    classified_error = _classify_compile_error(normalized_log, render_request)
    if classified_error:
        return classified_error
    return ""


def remove_superfluous(expr: str) -> str:
    """
    Takes a raw expression string and removes
    specified strings or uses alternate LaTeX syntax for
    compatability

    Attributes
        expr: str

    """

    # Remove any comments
    # Remove any latex str
    # Replace  \fill[blue] with \draw[fill=blue]

    expr = _strip_legacy_latex_prefix(expr).strip()

    if r'\maketitle' in expr or r'\author' in expr or r'\title' in expr:
        expr = expr.replace(r'\maketitle', "")
        expr = expr.replace(r'\author', r'\bf')
        expr = expr.replace(r'\title', r'\bf')

    if r'\fill' in expr:
        expr = expr.replace(r'\fill[', r'\draw[fill=')

    return _ensure_math_delimiters(expr)


def _ensure_math_delimiters(expr: str) -> str:
    """Wrap plain math input in a broadly compatible display-style math mode."""
    stripped = expr.strip()
    display_batch_blocks = _extract_display_math_batch_blocks(stripped)
    if not stripped:
        result = stripped
    elif r"\documentclass" in stripped or r"\begin{document}" in stripped:
        result = stripped
    elif display_batch_blocks and len(display_batch_blocks) > 1:
        result = _wrap_display_math_batch(display_batch_blocks)
    elif _contains_explicit_display_math_blocks(stripped):
        result = _normalize_display_math_blocks(stripped)
    elif _has_explicit_math_delimiters(stripped):
        result = stripped
    else:
        result = rf"$\displaystyle {stripped}$"

    return result


def _contains_explicit_display_math_blocks(expr: str) -> bool:
    return bool(
        re.search(r"(?s)\$\$.+?\$\$", expr)
        or re.search(r"(?s)\\\[.+?\\\]", expr)
    )


_DISPLAY_MATH_BLOCK_RE = re.compile(r"(?s)\$\$(.+?)\$\$|\\\[(.+?)\\\]")


def _extract_display_math_batch_blocks(expr: str) -> list[str] | None:
    blocks: list[str] = []
    cursor = 0

    for match in _DISPLAY_MATH_BLOCK_RE.finditer(expr):
        if expr[cursor:match.start()].strip():
            return None
        block = match.group(1) if match.group(1) is not None else match.group(2)
        blocks.append(block.strip())
        cursor = match.end()

    if not blocks or expr[cursor:].strip():
        return None

    return blocks


def _normalize_display_math_blocks(expr: str) -> str:
    expr = re.sub(
        r"(?s)\$\$(.+?)\$\$",
        lambda match: _wrap_display_math_content(match.group(1)),
        expr,
    )
    return re.sub(
        r"(?s)\\\[(.+?)\\\]",
        lambda match: _wrap_display_math_content(match.group(1)),
        expr,
    )


def _wrap_display_math_batch(blocks: list[str]) -> str:
    return (
        "$\\displaystyle \\begin{gathered}\n"
        + "\\\\\n".join(blocks)
        + "\n\\end{gathered}$"
    )


def _wrap_display_math_content(content: str) -> str:
    return "$\\displaystyle " + content.strip() + "$"


def _strip_legacy_latex_prefix(expr: str) -> str:
    stripped = expr.lstrip()
    if not re.match(r"latex(?:\s+|$)", stripped):
        return expr
    return re.sub(r"^latex(?:\s+|$)", "", stripped, count=1).lstrip()


def _has_explicit_math_delimiters(expr: str) -> bool:
    if expr.startswith(r"\[") and expr.endswith(r"\]"):
        return True
    if expr.startswith(r"\(") and expr.endswith(r"\)"):
        return True
    if expr.startswith("$$") and expr.endswith("$$"):
        return True
    if expr.startswith("$") and expr.endswith("$"):
        return True
    return False


def remove_hazardous_latex(expr: str) -> str:
    """ Basic regex removal for hazardous commands

    Attribute:
    expr: str

    """
    patterns = [
        r'(\\write18[^}]*)',  # \write18
        r'(\\openout[^}]*)',  # \openout
        r'(\\usepackage\{shellesc\})',
        # ...
    ]
    for pat in patterns:
        expr = re.sub(pat, "", expr, flags=re.IGNORECASE)
    return expr
