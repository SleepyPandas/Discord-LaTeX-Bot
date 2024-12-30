from sympy import preview


def text_to_latex(expr: str, output_file: str, dpi=250) -> bool | str:
    """
    Converts a text to LaTeX png
    returning True if it succeeds, False otherwise.

    Precondition: The text must be properly formatted in LaTeX.

    """

    expr = remove_superfluous(expr)

    # set preamble for Latex if tikz use below else use default

    if r"\begin{tikzpicture}" in expr:
        # For generating tikz only consider tikz picture environment with restricted margins
        # Active, tight-page restricts the generation to margin
        extra_preamble = "\\usepackage{xcolor, amsmath, amssymb, amsthm, tikz}\n" \
                         "\\usepackage[active,tightpage]{preview} \n" \
                         "\\PreviewEnvironment{tikzpicture} \n " \
                         "\\setlength\\PreviewBorder{2mm}"

        dvioptions = '-D', str(dpi)


    else:
        extra_preamble = "\\usepackage{xcolor, pagecolor, amsmath, amssymb, amsthm}\n" \
                         "\\definecolor{customtext}{HTML}{FFFFFF}\n" \
                         "\\color{customtext}"

        dvioptions = '-D', str(dpi), '-bg', 'Transparent'

        # Set custom name for file
    output_file = f"{output_file}.png"

    try:
        preview(expr,
                viewer='file',
                filename=output_file,
                output='png',
                euler=False,
                fontsize=14,
                dvioptions=dvioptions,
                extra_preamble=extra_preamble,
                # document=False
                )
        return True
    except Exception as log:
        print(f'Failed to convert text to LaTeX: {log}')
        error = find_latex_error(log)
        if error:
            return error
        else:
            return "Failed to Compile Unknown Error 💀💀💀"


def find_latex_error(error_log: str | Exception | bytes) -> str:
    """
    Will take an exception error, and parse the error into a str

    -NOTE- | Attributes are str, exception and bytes
    for different operating system compatability issues

    Attributes
        error_log: str | Exception | bytes
    """
    if isinstance(error_log, Exception):
        error_log = str(error_log)
    elif isinstance(error_log, bytes):
        error_log = error_log.decode("utf-8")
    error_log = error_log.replace("\\r\\n", "\n")
    error_log = error_log.replace("\\n", "\n")
    # OR splitlines()
    for line in error_log.split("\n"):
        # Strip leading/trailing whitespace
        stripped_line = line.strip()
        # Check if it starts with '!' and ends with '.'
        if stripped_line.startswith('!') and stripped_line.endswith('.'):
            return stripped_line
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
        # I use repr to print literal string
        # Not necessary, but I wanted to try it :)
        expr = expr.replace(r'\fill[', r'\draw[fill=')

    return expr
