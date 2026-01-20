# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies required for LaTeX and other libraries
# texlive-latex-base: Basic LaTeX support
# texlive-latex-extra: Additional LaTeX packages (often needed for standalone, etc.)
# texlive-fonts-recommended: Standard fonts
# poppler-utils: Required for PDF to Image conversion (likely used by pdf2image)
RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-latex-base \
    texlive-latex-extra \
    texlive-fonts-recommended \
    cm-super \
    dvipng \
    poppler-utils \
    ghostscript \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY src/requirements.txt /app/

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the source code into the container
COPY src/ /app/src/

# Run the bot
CMD ["python", "src/bot.py"]
