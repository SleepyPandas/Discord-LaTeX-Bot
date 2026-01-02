<div align="center">
  <img src="https://github.com/user-attachments/assets/7679c732-1e13-4194-9dc1-b3f981146346" width="200px" alt="GitHub Readme Stats" />
  <h1 style="font-size: 28px; margin: 10px 0;">Discord-LaTeX-Bot</h1>
  <p>Discord bot designed to render LaTeX mathematical expressions into high-quality images in real-time. Built for academic servers, study groups, and STEM communities, this bot bridges the gap between complex mathematical typesetting and seamless discord communication!</p>
</div>







## Highlights
- /latex renders LaTeX or TikZ into a PNG and posts it back
- Works in servers and DMs, with timeouts to keep the bot responsive
- Optional /talk-to-me command for quick Q&A
- Async + thread pool rendering keeps the event loop free
- *Renders small full size documents or inline*

## Built with
- Python, discord.py, asyncio, ThreadPoolExecutor
- LaTeX toolchain (standalone + TikZ) for rendering
- Google Gemma API
- [YtoTech Latex to PNG HTTP](https://github.com/YtoTech/latex-on-http)

## Deployment
- Deployed on Debian

## Invite me here! (Redirect Links)
For Use in DMs -- (https://discord.com/oauth2/authorize?client_id=1242573317693640788 )

To Add to Server -- (https://discordbotlist.com/bots/latex)

## Quick commands
- /latex {code}
- latex {code} (servers only)
- /talk-to-me {question}
- /help

## Example Use
### TikZ Example (Full Document)
```
latex

\documentclass[border=1mm]{standalone}
\usepackage{tikz}
\usepackage{amsmath}
\begin{document}

\begin{tikzpicture}[scale=1.5,>=stealth]
    \draw[->] (-0.5,0) -- (3,0) node[right] {$x$};
    \draw[->] (0,-0.5) -- (0,3) node[above] {$y$};
   \draw[thick, blue] (0,0) -- (2.5,1.5) node[above right] {$\mathbf{v}$};
   \draw[thick, red] (0,0) -- (2,1.2) node[below right] {$\text{proj}_{\mathbf{u}} \mathbf{v}$};
    \draw[dashed] (2,1.2) -- (2.5,1.5);
    \draw[dashed] (2,1.2) -- (2,0);
    \draw[thick] (0,0) -- (2,1.2) node[midway, below left] {$\mathbf{u}$};
    \draw[fill] (2,1.2) circle (1pt);
    \draw[fill] (2.5,1.5) circle (1pt);
\end{tikzpicture}

\end{document}
```
&nbsp;

<div align="center">
  <img src="https://github.com/user-attachments/assets/52613cec-0d35-4f66-adcf-ec6cad236121" alt="Example tikz">
</div>

&nbsp;

### General Example (In-Line)
```
/latex \[ \hat{f}(\xi) = \int_{-\infty}^\infty f(x) e^{-2\pi i \xi x} \, dx \]
```
&nbsp;

<div align="center">
  <img src="https://github.com/user-attachments/assets/a020768e-88ff-4009-b493-aa49d1206899" alt="Example Equation">
</div>

&nbsp;

### Sentience Feature Example
```
/talk-to-me {What is the meaning of life}
```

&nbsp;

<div align="center">
  <img src="https://github.com/user-attachments/assets/9640a285-18d6-43f0-b59a-c99c8af4b006" alt="No Im missing!">
</div>

## Tips
- To get a past message press up arrow on your keyboard `.
- A preamble is only needed if using a TikZ package; otherwise a basic structure is added by default.
- You still need delimiters like "\$ ... \$", "\\[ ... \\]", or "\$$ ... \$$".
- If using /latex remove all comments.

## Credit
Yan-Zero forked his tex2img package, and friend Indy for his support.

&nbsp;
&nbsp;
&nbsp;

### Bonus
It is also Samsung fridge compatible!

&nbsp;

<div align="center">
  <img src="https://github.com/user-attachments/assets/dfa67b5b-9978-4544-bfc3-c3cba668f031" alt="Bonus">
</div>
