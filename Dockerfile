FROM python:3.13-slim
WORKDIR /app
COPY app/ /app/
ENV PORT=8080
EXPOSE 8080
CMD ["python3", "backend/server.py"]
