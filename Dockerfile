# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1


# We keep 'build-essential' to help compile Python libraries if needed.
RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-latex-base \
    texlive-latex-extra \
    texlive-latex-recommended \
    texlive-fonts-recommended \
    texlive-pictures \
    texlive-plain-generic \

    
    dvipng \
    poppler-utils \
    ghostscript \
    build-essential \

    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy requirements
COPY src/requirements.txt /app/

# Use PiWheels to prevent RAM crashes during Python install
RUN pip install --no-cache-dir --extra-index-url https://www.piwheels.org/simple -r requirements.txt

# Copy source code
COPY src/ /app/src/

# Run the bot
CMD ["python", "src/bot.py"]