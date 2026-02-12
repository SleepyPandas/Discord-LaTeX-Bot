import logging
import re

from sympy import preview

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
    Converts a text to LaTeX png
    returning a str if it succeeds, False otherwise.

    Precondition: The text must be properly formatted in LaTeX.

    Attributes:
     expr: str
     output_file: str
     dpi=(1000 , optional) int | sets resolution
    """

    # TODO : /Nodes has strange interaction with preview() from sympy
    # TODO : Consider using Latex2PNG from tex2img to replace all of sympy preview()

    # Latex2Png requires a full document structure a solution
    # is to always add a \begin and document class and load a standard set of packages
    #

    if len(expr) > 2000:
        return "Too Complex"
    if dpi > 800:
        return "Too Large"
    expr = remove_hazardous_latex(expr)

    if r"\documentclass" in expr and r"\begin{tikzpicture}" in expr or r"\documentclass" in expr:
        latex_code = re.sub(r"\\documentclass.*?{.*?}", r'\\documentclass[border=1mm]{standalone} ', expr)
        if 'latex' in latex_code:
            latex_code = latex_code.replace('latex', '', 1)
        renderer = Latex2PNG()
        try:
            png_data = renderer.compile(latex_code, transparent=False, compiler='pdflatex', dpi=520)
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

        # Convert png_data to bytes
        if isinstance(png_data, list):
            try:
                png_bytes = b''.join(png_data)
            except TypeError:
                _logger.warning("png_data list contains non-bytes items output_file=%s", output_file)
                png_bytes = b''.join([item if isinstance(item, bytes) else b'' for item in png_data])
        elif isinstance(png_data, bytes):
            png_bytes = png_data
        else:
            raise TypeError("png_data is neither a list nor bytes.")

        # Write to file
        with open(output_file + '.png', 'wb') as f:
            f.write(png_bytes)

        _logger.debug("PNG generated output_file=%s.png", output_file)
        return True
    else:
        expr = remove_superfluous(expr)

        extra_preamble = "\\usepackage{xcolor}\n" \
                         "\\definecolor{customtext}{HTML}{FFFFFF}\n" \
                         "\\color{customtext}\n"

        dvioptions = ('-D', str(dpi), '-bg', 'Transparent')

        # Set custom name for file

        output_file = f"{output_file}.png"

        try:
            preview(expr,
                    viewer='file',
                    filename=output_file,
                    output='png',
                    euler=False,
                    fontsize=15,
                    dvioptions=dvioptions,
                    extra_preamble=extra_preamble,
                    # document=False
                    )
            return True
        except Exception as exc:
            error = find_latex_error(exc)
            if error:
                _logger.warning(
                    "Sympy preview compile failed output_file=%s dpi=%s expr_len=%s latex_error=%s",
                    output_file,
                    dpi,
                    len(expr),
                    error,
                )
                return error
            else:
                _logger.exception(
                    "Sympy preview compile failed without parseable LaTeX error output_file=%s dpi=%s expr_len=%s",
                    output_file,
                    dpi,
                    len(expr),
                )
                return _UNKNOWN_COMPILE_ERROR


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

    if 'latex' in expr:
        expr = expr.replace('latex', '', 1)
        expr = expr.replace(r'\maketitle', "")
        expr = expr.replace(r'\author', r'\bf')
        expr = expr.replace(r'\title', r'\bf')

    if r'\fill' in expr:
        expr = expr.replace(r'\fill[', r'\draw[fill=')

    return expr


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
