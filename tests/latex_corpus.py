from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ExpectedStatus = Literal["success", "error"]
@dataclass(frozen=True)
class LatexCorpusCase:
    id: str
    category: str
    input: str
    expected_status: ExpectedStatus
    expected_error_contains: tuple[str, ...] = ()
    dpi: int = 300

    def __post_init__(self) -> None:
        if self.expected_status == "error" and not self.expected_error_contains:
            raise ValueError(f"{self.id} is missing expected_error_contains")
        if self.expected_status == "success" and self.expected_error_contains:
            raise ValueError(f"{self.id} should not define expected_error_contains")


LATEX_CORPUS_CASES: tuple[LatexCorpusCase, ...] = (
    LatexCorpusCase(
        id="inline-fraction",
        category="algebra",
        input=r"\frac{1}{2}",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="inline-nested-fraction-root",
        category="algebra",
        input=r"\frac{1+\sqrt{5}}{2}",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="inline-quadratic-formula",
        category="algebra",
        input=r"x=\frac{-b\pm\sqrt{b^2-4ac}}{2a}",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="inline-gaussian-integral",
        category="calculus",
        input=r"\int_0^\infty e^{-x^2}\,dx=\frac{\sqrt{\pi}}{2}",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="inline-basel-sum",
        category="series",
        input=r"\sum_{n=1}^{\infty}\frac{1}{n^2}=\frac{\pi^2}{6}",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="inline-sine-limit",
        category="calculus",
        input=r"\lim_{x\to 0}\frac{\sin x}{x}=1",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="inline-derivative",
        category="calculus",
        input=r"\frac{d}{dx}x^3=3x^2",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="inline-partial-derivative",
        category="calculus",
        input=r"\frac{\partial}{\partial x}(x^2y)=2xy",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="inline-bmatrix",
        category="linear-algebra",
        input=r"\begin{bmatrix}1 & 2\\3 & 4\end{bmatrix}",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="inline-pmatrix",
        category="linear-algebra",
        input=r"\begin{pmatrix}a & b\\c & d\end{pmatrix}",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="inline-vmatrix",
        category="linear-algebra",
        input=r"\begin{vmatrix}a & b\\c & d\end{vmatrix}",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="modal-aligned-system",
        category="systems",
        input="\\begin{aligned}\ny&=mx+b\\\\\ny(0)&=b\n\\end{aligned}",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="inline-cases-piecewise",
        category="piecewise",
        input=r"f(x)=\begin{cases}x^2 & x\ge 0\\-x & x<0\end{cases}",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="inline-text",
        category="text",
        input=r"\text{hello world}",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="inline-greek-letters",
        category="symbols",
        input=r"\alpha+\beta=\gamma",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="inline-vector-notation",
        category="physics",
        input=r"\vec{F}=m\vec{a}",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="inline-hat-overline",
        category="symbols",
        input=r"\overline{z}+\hat{x}",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="inline-binomial-coefficient",
        category="combinatorics",
        input=r"\binom{n}{k}=\frac{n!}{k!(n-k)!}",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="inline-bayes-rule",
        category="probability",
        input=r"P(A\mid B)=\frac{P(B\mid A)P(A)}{P(B)}",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="inline-expectation",
        category="probability",
        input=r"E[X]=\sum_x x\,P(X=x)",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="inline-variance",
        category="probability",
        input=r"\mathrm{Var}(X)=E[X^2]-E[X]^2",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="inline-normal-density",
        category="probability",
        input=r"f(x)=\frac{1}{\sigma\sqrt{2\pi}}e^{-\frac{(x-\mu)^2}{2\sigma^2}}",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="inline-set-builder",
        category="sets",
        input=r"A=\{x\mid x>0\}",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="inline-floor-ceiling",
        category="discrete",
        input=r"\lfloor x\rfloor+\lceil y\rceil",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="inline-absolute-value",
        category="algebra",
        input=r"|x|=\sqrt{x^2}",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="inline-fourier-transform",
        category="analysis",
        input=r"\hat{f}(\xi)=\int_{-\infty}^{\infty}f(x)e^{-2\pi i x\xi}\,dx",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="inline-bra-ket",
        category="physics",
        input=r"\langle \psi \mid \phi \rangle",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="inline-commutator",
        category="physics",
        input=r"[A,B]=AB-BA",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="inline-contour-integral",
        category="analysis",
        input=r"\oint_C \frac{1}{z}\,dz=2\pi i",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="legacy-prefix-pythagorean",
        category="legacy-command",
        input=r"latex \alpha^2+\beta^2=\gamma^2",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="inline-taylor-series",
        category="series",
        input=r"e^x=\sum_{n=0}^{\infty}\frac{x^n}{n!}",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="modal-full-document-article",
        category="full-document",
        input=(
            "\\documentclass{article}\n"
            "\\begin{document}\n"
            "$\\int_0^1 x^2\\,dx=\\frac{1}{3}$\n"
            "\\end{document}"
        ),
        expected_status="success",
    ),
    LatexCorpusCase(
        id="modal-full-document-tikz",
        category="tikz",
        input=(
            "\\documentclass[tikz,border=6pt]{standalone}\n"
            "\\usepackage{tikz}\n"
            "\\begin{document}\n"
            "\\begin{tikzpicture}\n"
            "\\draw[->] (0,0) -- (2,0);\n"
            "\\draw[->] (0,0) -- (0,2);\n"
            "\\draw[thick] (0,0) -- (1.5,1.2);\n"
            "\\end{tikzpicture}\n"
            "\\end{document}"
        ),
        expected_status="success",
    ),
    LatexCorpusCase(
        id="tikz-environment-fragment",
        category="tikz",
        input=(
            "\\begin{tikzpicture}\n"
            "\\draw (0,0) rectangle (2,1);\n"
            "\\draw (0,0) -- (2,1);\n"
            "\\end{tikzpicture}"
        ),
        expected_status="success",
    ),
    LatexCorpusCase(
        id="raw-draw-fragment",
        category="tikz",
        input=r"\draw (0,0) -- (2,1);",
        expected_status="success",
    ),
    LatexCorpusCase(
        id="error-missing-frac-brace",
        category="syntax-error",
        input=r"\frac{1}{2",
        expected_status="error",
        expected_error_contains=("LaTeX syntax error", r"Missing `}` to finish `\frac{...}{...}`."),
    ),
    LatexCorpusCase(
        id="error-missing-sqrt-brace",
        category="syntax-error",
        input=r"\sqrt{2",
        expected_status="error",
        expected_error_contains=("LaTeX syntax error", r"Missing `}` to finish `\sqrt{...}`."),
    ),
    LatexCorpusCase(
        id="error-missing-text-brace",
        category="syntax-error",
        input=r"\text{hello",
        expected_status="error",
        expected_error_contains=("LaTeX syntax error", r"Missing `}` to finish `\text{...}`."),
    ),
    LatexCorpusCase(
        id="error-missing-end-aligned",
        category="environment-error",
        input="\\begin{aligned}\na&=b",
        expected_status="error",
        expected_error_contains=("LaTeX syntax error", r"Missing `\end{aligned}` to close the environment."),
    ),
    LatexCorpusCase(
        id="error-missing-end-bmatrix",
        category="environment-error",
        input=r"\begin{bmatrix}1 & 2",
        expected_status="error",
        expected_error_contains=("LaTeX syntax error", r"Missing `\end{bmatrix}` to close the environment."),
    ),
    LatexCorpusCase(
        id="error-mismatched-end-environment",
        category="environment-error",
        input="\\begin{aligned}\n\\end{bmatrix}",
        expected_status="error",
        expected_error_contains=("LaTeX syntax error", r"Expected `\end{aligned}`, but found `\end{bmatrix}`."),
    ),
    LatexCorpusCase(
        id="error-missing-right",
        category="delimiter-error",
        input=r"\left(x+1",
        expected_status="error",
        expected_error_contains=("LaTeX syntax error", r"Missing `\right` to match `\left`."),
    ),
    LatexCorpusCase(
        id="error-unexpected-right",
        category="delimiter-error",
        input=r"\right)",
        expected_status="error",
        expected_error_contains=("LaTeX syntax error", r"Unexpected `\right` without a matching `\left`."),
    ),
    LatexCorpusCase(
        id="error-missing-single-dollar",
        category="math-delimiter-error",
        input=r"$x+1",
        expected_status="error",
        expected_error_contains=("LaTeX syntax error", "Missing closing `$` to finish the math expression."),
    ),
    LatexCorpusCase(
        id="error-missing-double-dollar",
        category="math-delimiter-error",
        input=r"$$x+1",
        expected_status="error",
        expected_error_contains=("LaTeX syntax error", "Missing closing `$$` to finish the math block."),
    ),
    LatexCorpusCase(
        id="error-undefined-command",
        category="command-error",
        input=r"latex \foobarbaz + 1",
        expected_status="error",
        expected_error_contains=("LaTeX command error", r"`\foobarbaz` is undefined."),
    ),
    LatexCorpusCase(
        id="error-tikzcd-missing-package",
        category="dependency-error",
        input="\\begin{tikzcd}\nA \\arrow[r] & B\n\\end{tikzcd}",
        expected_status="error",
        expected_error_contains=("LaTeX environment error", r"`tikzcd` requires `\usepackage{tikz-cd}` in the preamble."),
    ),
    LatexCorpusCase(
        id="error-unsupported-minted",
        category="unsupported-feature",
        input="\\usepackage{minted}\n\\begin{document}x\\end{document}",
        expected_status="error",
        expected_error_contains=("Unsupported LaTeX feature", "package `minted` requires shell escape"),
    ),
    LatexCorpusCase(
        id="error-input-too-long",
        category="input-limit",
        input="x" * 3001,
        expected_status="error",
        expected_error_contains=("Input too long: 3001 characters. Max is 3000 characters.",),
    ),
    LatexCorpusCase(
        id="error-dpi-too-large",
        category="input-limit",
        input=r"\frac{1}{2}",
        expected_status="error",
        expected_error_contains=("DPI too large: 801. Max is 800.",),
        dpi=801,
    ),
)
