import ast
import re

from sympy import preview

from modified_packages import Latex2PNG


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
        return "Input too long (limit: 2000 characters)."
    if dpi > 800:
        return "DPI too large (limit: 800)."
    expr = remove_hazardous_latex(expr)

    if r"\documentclass" in expr and r"\begin{tikzpicture}" in expr or r"\documentclass" in expr:
        latex_code = re.sub(r"\\documentclass.*?{.*?}", r'\\documentclass[border=1mm]{standalone} ', expr)
        if 'latex' in latex_code:
            latex_code = latex_code.replace('latex', '', 1)
        renderer = Latex2PNG()
        try:
            png_data = renderer.compile(latex_code, transparent=False, compiler='pdflatex', dpi=520)
        except Exception as log:
            print(f'Failed to convert text to LaTeX: {log}')
            return format_latex_error(log)

        # Convert png_data to bytes
        if isinstance(png_data, list):
            try:
                png_bytes = b''.join(png_data)
            except TypeError:
                print("Error: png_data list contains non-bytes items.")
                png_bytes = b''.join([item if isinstance(item, bytes) else b'' for item in png_data])
        elif isinstance(png_data, bytes):
            png_bytes = png_data
        else:
            raise TypeError("png_data is neither a list nor bytes.")

        # Write to file
        with open(output_file + '.png', 'wb') as f:
            f.write(png_bytes)

        print("PNG generated: output.png")
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
        except Exception as log:
            print(f'Failed to convert text to LaTeX: {log}')
            return format_latex_error(log)


def _flatten_error_log(error_log: str | Exception | bytes | list) -> list[str]:
    if isinstance(error_log, Exception):
        error_log = str(error_log)
    elif isinstance(error_log, bytes):
        error_log = error_log.decode("utf-8", errors="replace")

    if isinstance(error_log, list):
        lines: list[str] = []
        for item in error_log:
            lines.extend(_flatten_error_log(item))
        return lines

    text = str(error_log)
    if "error logs:" in text:
        suffix = text.split("error logs:", 1)[1].strip()
        if suffix.startswith("[") and suffix.endswith("]"):
            try:
                parsed = ast.literal_eval(suffix)
            except (ValueError, SyntaxError):
                parsed = None
            if isinstance(parsed, list):
                return _flatten_error_log(parsed)

    text = text.replace("\\r\\n", "\n")
    text = text.replace("\\n", "\n")
    return text.splitlines()


def _extract_error_details(lines: list[str]) -> tuple[str, str]:
    primary = ""
    context = ""

    for idx, line in enumerate(lines):
        stripped_line = line.strip()
        if not stripped_line:
            continue
        if stripped_line.startswith("!"):
            primary = stripped_line.lstrip("!").strip()
            for look_ahead in range(idx + 1, min(idx + 4, len(lines))):
                candidate = lines[look_ahead].strip()
                if candidate.startswith("l."):
                    context = candidate
                    break
            break
        if "LaTeX Error:" in stripped_line:
            primary = stripped_line.replace("LaTeX Error:", "").strip()
            break
        if "Package" in stripped_line and "Error" in stripped_line:
            primary = stripped_line
            break

    if not primary:
        for line in lines:
            stripped_line = line.strip()
            if "error" in stripped_line.lower() or "failed" in stripped_line.lower():
                primary = stripped_line
                break

    return primary, context


def _guess_latex_hint(primary: str, raw_text: str) -> str:
    patterns = [
        (r"Missing \$ inserted", "Check for missing $...$ math delimiters."),
        (r"Missing \} inserted", "Check for unmatched braces { }."),
        (r"Extra \}, or forgotten", "Check for unmatched braces or missing \\end{...}."),
        (r"Undefined control sequence", "Unknown command. Check spelling or add the required \\usepackage{...}."),
        (r"File `.+?' not found", "Missing file or package. Ensure it exists or add the package."),
        (r"Runaway argument", "You likely have an unclosed brace or environment."),
        (r"Misplaced alignment tab character &", "Use & only inside alignment environments like align or tabular."),
        (r"Environment .+? undefined", "Unknown environment. Check spelling or add the package."),
        (r"\\begin\{.+?\} ended by \\end\{.+?\}", "Mismatched \\begin/\\end environments."),
        (r"You can't use `\\.+?' in math mode", "Use text-mode commands outside math or wrap text with \\text{...}."),
        (r"Emergency stop", "Compilation stopped after a previous error."),
        (r"Too many \}'s", "Too many closing braces }."),
    ]

    haystack = f"{primary}\n{raw_text}"
    for pattern, hint in patterns:
        if re.search(pattern, haystack, flags=re.IGNORECASE):
            return hint
    return ""


def format_latex_error(error_log: str | Exception | bytes | list) -> str:
    lines = _flatten_error_log(error_log)
    if not lines:
        return "Compilation failed. No error details were returned."

    primary, context = _extract_error_details(lines)
    hint = _guess_latex_hint(primary, "\n".join(lines))

    parts = ["Compilation failed."]
    if primary:
        parts.append(f"Error: {primary}")
    if context:
        parts.append(f"At: {context}")
    if hint:
        parts.append(f"Hint: {hint}")

    message = "\n".join(parts)
    if len(message) > 3500:
        return message[:3500].rstrip() + "..."
    return message


def find_latex_error(error_log: str | Exception | bytes) -> str:
    """
    Backwards-compatible helper that extracts the primary error line.
    """
    primary, _ = _extract_error_details(_flatten_error_log(error_log))
    return primary


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
