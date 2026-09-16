FROM python:3.13-slim
WORKDIR /app
COPY bigpaw-app.zip /tmp/bigpaw-app.zip
RUN python3 -c "import zipfile; zipfile.ZipFile('/tmp/bigpaw-app.zip').extractall('/app')"
WORKDIR /app/BIG_PAW_v1.0_FINAL3_domain_ready_package
ENV PORT=8080
EXPOSE 8080
CMD ["python3", "backend/server.py"]
