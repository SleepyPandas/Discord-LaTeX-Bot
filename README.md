# Discord-Latex-Bot
Compiles latex code in discord with /latex {code} or latex {code} (Note the latter option is only available in servers due to privacy concerns in private messages) 

## Invite me here! 

https://discord.com/oauth2/authorize?client_id=1242573317693640788 ( BOTH REDIRECT LINKS ) <br />
https://discordbotlist.com/bots/latex

## Example Use 
### Tikz Example 
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


### General Example 

```
/latex \[ \hat{f}(\xi) = \int_{-\infty}^\infty f(x) e^{-2\pi i \xi x} \, dx \]
```
&nbsp;

<div align="center">
  <img src="https://github.com/user-attachments/assets/a020768e-88ff-4009-b493-aa49d1206899" alt="Example Equation">
</div>


## Tips
To get a past message press up arrow on your keyboard ↑.

A preamble is only needed if using a Tikz package otherwise
a basic structure is added by default. However you still need
delimiters e.g. "$...$" or "\\[...\\]" or maybe "$$..$$".

If using /latex remove all comments 


## Credit 
Yan-Zero forked his tex2img package & My short friend Indy 😁

&nbsp;
&nbsp;
&nbsp;

### Bonus
It is also Samsung fridge compatable! 


&nbsp;

<div align="center">
  <img src="https://github.com/user-attachments/assets/dfa67b5b-9978-4544-bfc3-c3cba668f031" alt="Bonus">
</div>
