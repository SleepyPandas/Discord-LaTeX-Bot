FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY monitoring/dashboard/requirements.txt /app/monitoring/dashboard/requirements.txt
RUN pip install --no-cache-dir -r /app/monitoring/dashboard/requirements.txt

COPY monitoring/dashboard /app/monitoring/dashboard

EXPOSE 8081

CMD ["python", "monitoring/dashboard/app.py"]
