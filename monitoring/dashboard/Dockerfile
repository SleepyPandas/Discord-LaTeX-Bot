FROM python:3.12-slim

ARG APP_VERSION=unknown
ARG BUILD_DATE=unknown
ARG GIT_SHA=unknown

LABEL org.opencontainers.image.version=${APP_VERSION}
LABEL org.opencontainers.image.created=${BUILD_DATE}
LABEL org.opencontainers.image.revision=${GIT_SHA}

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_VERSION=${APP_VERSION}
ENV BUILD_DATE=${BUILD_DATE}
ENV GIT_SHA=${GIT_SHA}

WORKDIR /app

COPY monitoring/dashboard/requirements.txt /app/monitoring/dashboard/requirements.txt
RUN pip install --no-cache-dir -r /app/monitoring/dashboard/requirements.txt

COPY monitoring/dashboard /app/monitoring/dashboard

EXPOSE 8081

CMD ["python", "monitoring/dashboard/app.py"]
