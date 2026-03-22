ARG BOT_BASE_IMAGE=ghcr.io/sleepypandas/discord-latex-bot-base:py312-texlive
FROM ${BOT_BASE_IMAGE}

# Copy requirements
COPY src/requirements.txt /app/

# Use PiWheels to prevent RAM crashes during Python install
RUN pip install --no-cache-dir --extra-index-url https://www.piwheels.org/simple -r requirements.txt

# Copy source code
COPY src/ /app/src/

# Run the bot
CMD ["python", "src/bot.py"]
