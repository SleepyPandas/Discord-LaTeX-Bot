import logging
import re

from modified_packages import InlineDviPngRenderer, Latex2PNG

_logger = logging.getLogger(__name__)
_UNKNOWN_COMPILE_ERROR = (
    "Failed to compile unsupported or unknown LaTeX code. "
    "If you are using '/' commands, remove comments."
)
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

    if len(expr) > 3000:
        return "Too Complex"
    if dpi > 800:
        return "Too Large"
    expr = remove_hazardous_latex(expr)
    latex_code, transparent, render_dpi = _prepare_render_request(expr, dpi)

    try:
        png_data = _render_png_request(
            expr=expr,
            latex_code=latex_code,
            transparent=transparent,
            render_dpi=render_dpi,
            output_file=output_file,
        )
    except Exception as exc:
        normalized_error = _normalize_error_log(exc)
        user_error = find_latex_error(normalized_error)

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
            if preamble:
                i += 1
            else:
                i += 1
        else:
            break
    body = "\n".join(lines[i:]).strip()
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


def _prepare_render_request(expr: str, dpi: int) -> tuple[str, bool, int]:
    stripped = _strip_legacy_latex_prefix(expr).strip()
    if _is_full_document(stripped) or _needs_standalone_document_shell(stripped):
        return _normalize_full_document(expr), False, dpi
    return _build_inline_document(remove_superfluous(expr)), True, dpi


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


def _normalize_full_document(expr: str) -> str:
    latex_code = _strip_legacy_latex_prefix(expr).strip()

    if r"\documentclass" in latex_code:
        return _normalize_first_documentclass_if_needed(latex_code)

    if r"\begin{document}" in latex_code:
        opts = _documentclass_options_for_content(latex_code)
        return rf"\documentclass{opts}{{standalone}}" "\n" f"{latex_code}"

    preamble_lines, body = _split_leading_preamble_lines(latex_code)
    body_wrapped = _maybe_wrap_raw_tikz_body(body)
    combined_for_opts = latex_code
    opts = _documentclass_options_for_content(combined_for_opts)

    preamble_block = ("\n".join(preamble_lines) + "\n") if preamble_lines else ""
    return (
        rf"\documentclass{opts}{{standalone}}" "\n"
        f"{preamble_block}"
        r"\begin{document}" "\n"
        f"{body_wrapped}\n"
        r"\end{document}"
    )


def _build_inline_document(expr: str) -> str:
    return (
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


def _extract_latex_error_details(log_text: str) -> tuple[str, int | None]:
    """Extract the most actionable LaTeX error and optional line number."""
    line_no = None
    line_match = re.search(r"[^\s:]+\.tex:(\d+):", log_text)
    if line_match:
        line_no = int(line_match.group(1))

    lines = [line.strip() for line in log_text.splitlines() if line.strip()]

    for line in lines:
        if "LaTeX Error:" in line:
            message = line[line.index("LaTeX Error:"):].lstrip("! ").strip()
            return re.sub(r"\s+", " ", message), line_no

    for line in lines:
        if line.startswith("!"):
            message = line.lstrip("! ").strip()
            if message:
                return re.sub(r"\s+", " ", message), line_no

    fallback_tokens = (
        "Emergency stop",
        "Fatal error",
        "Runaway argument",
        "Undefined control sequence",
        "Missing $ inserted",
    )
    for line in lines:
        if any(token.lower() in line.lower() for token in fallback_tokens):
            return re.sub(r"\s+", " ", line), line_no

    return "", line_no


def _format_human_latex_error(message: str, line_no: int | None) -> str:
    """Format a concise Discord-safe compile error with optional hint."""
    if line_no is not None:
        output = f"LaTeX compile error (line {line_no}): {message}"
    else:
        output = f"LaTeX compile error: {message}"

    lower_message = message.lower()
    hint = ""
    if ".sty" in lower_message and "not found" in lower_message:
        hint = " Hint: this package may be unavailable in this renderer."
    elif "missing $ inserted" in lower_message:
        hint = " Hint: check math delimiters like $...$ or \\[...\\]."
    elif "undefined control sequence" in lower_message:
        hint = " Hint: check command spelling or required package imports."

    output = f"{output}{hint}".strip()
    if len(output) > 500:
        return output[:497] + "..."
    return output


def find_latex_error(error_log: str | Exception | bytes) -> str:
    """
    Will take an exception error, and parse the error into a str

    -NOTE- | Attributes are str, exception and bytes
    for different operating system compatability issues

    Attributes
        error_log: str | Exception | bytes
    """
    normalized_log = _normalize_error_log(error_log)
    error_message, line_no = _extract_latex_error_details(normalized_log)
    if error_message:
        return _format_human_latex_error(error_message, line_no)
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
