import logging
import re

from modified_packages import Latex2PNG

_logger = logging.getLogger(__name__)
_UNKNOWN_COMPILE_ERROR = (
    "Failed to compile unsupported or unknown LaTeX code. "
    "If you are using '/' commands, remove comments."
)
_COMPILER_LOG_PREFIX = "Compilation failed with error logs:"


# Should Fork or was it pork :)


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

    if len(expr) > 2000:
        return "Too Complex"
    if dpi > 800:
        return "Too Large"
    expr = remove_hazardous_latex(expr)
    latex_code, transparent, render_dpi = _prepare_render_request(expr, dpi)

    renderer = Latex2PNG()
    try:
        png_data = renderer.compile(
            latex_code,
            transparent=transparent,
            compiler='pdflatex',
            dpi=render_dpi,
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


def _prepare_render_request(expr: str, dpi: int) -> tuple[str, bool, int]:
    if _is_full_document(expr):
        return _normalize_full_document(expr), False, dpi
    return _build_inline_document(remove_superfluous(expr)), True, dpi


def _normalize_full_document(expr: str) -> str:
    latex_code = _strip_legacy_latex_prefix(expr).strip()
    if r"\documentclass" not in latex_code:
        return (
            r"\documentclass[border=1mm]{standalone}" "\n"
            f"{latex_code}"
        )

    return re.sub(
        r"\\documentclass(?:\[[^\]]*\])?\{[^}]+\}",
        r'\\documentclass[border=1mm]{standalone}',
        latex_code,
        count=1,
    )


def _build_inline_document(expr: str) -> str:
    return (
        r"\documentclass[border=1mm]{standalone}" "\n"
        r"\usepackage{amsmath}" "\n"
        r"\usepackage{amssymb}" "\n"
        r"\usepackage{amsfonts}" "\n"
        r"\usepackage{xcolor}" "\n"
        r"\definecolor{customtext}{HTML}{FFFFFF}" "\n"
        r"\color{customtext}" "\n"
        r"\begin{document}" "\n"
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
    """Wrap plain math input in display-math delimiters when missing."""
    stripped = expr.strip()
    if not stripped:
        return stripped

    if r"\documentclass" in stripped or r"\begin{document}" in stripped:
        return stripped

    if _has_explicit_math_delimiters(stripped):
        return stripped

    return rf"\[{stripped}\]"


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
