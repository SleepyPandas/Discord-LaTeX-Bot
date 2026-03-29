import argparse
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import latex_module
from modified_packages import InlineDviPngRenderer, Latex2PNG

BENCHMARK_CASES = [
    ("fraction", r"\frac{1}{2}"),
    ("sum_of_squares", r"\sum_{k=1}^{n} k^2 = \frac{n(n+1)(2n+1)}{6}"),
    ("gaussian_integral", r"\int_{-\infty}^{\infty} e^{-x^2}\,dx = \sqrt{\pi}"),
]


def _render_pdf(expr: str, dpi: int) -> None:
    latex_code, transparent, render_dpi = latex_module._prepare_render_request(expr, dpi)
    Latex2PNG().compile(
        latex_code,
        transparent=transparent,
        compiler="pdflatex",
        dpi=render_dpi,
    )


def _render_dvipng(expr: str, dpi: int) -> None:
    if not latex_module._is_dvipng_fast_path_eligible(expr):
        raise RuntimeError(f"Expression is not fast-path eligible: {expr}")

    latex_code, transparent, render_dpi = latex_module._prepare_render_request(expr, dpi)
    InlineDviPngRenderer().compile(
        latex_code,
        transparent=transparent,
        dpi=render_dpi,
    )


def _render_auto(expr: str, dpi: int) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_base = str(Path(temp_dir) / "inline-benchmark")
        result = latex_module.text_to_latex(expr, output_base, dpi=dpi)
        if result is not True:
            raise RuntimeError(result)


def _time_case(mode: str, expr: str, dpi: int, runs: int) -> list[float]:
    renderer = {
        "pdf": _render_pdf,
        "dvipng": _render_dvipng,
        "auto": _render_auto,
    }[mode]

    samples = []
    for _ in range(runs):
        start = time.perf_counter()
        renderer(expr, dpi)
        samples.append((time.perf_counter() - start) * 1000)
    return samples


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark representative inline LaTeX formulas.",
    )
    parser.add_argument(
        "--mode",
        choices=("pdf", "dvipng", "auto"),
        default="pdf",
        help="pdf benchmarks the legacy pdflatex->PDF->PNG path.",
    )
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--dpi", type=int, default=300)
    args = parser.parse_args()

    print(f"mode={args.mode} dpi={args.dpi} runs={args.runs}")
    for name, expr in BENCHMARK_CASES:
        samples = _time_case(args.mode, expr, args.dpi, args.runs)
        rounded = [round(sample, 2) for sample in samples]
        print(
            f"{name}: expr={expr} samples_ms={rounded} "
            f"mean_ms={round(statistics.mean(samples), 2)} "
            f"min_ms={round(min(samples), 2)} max_ms={round(max(samples), 2)}"
        )


if __name__ == "__main__":
    main()
