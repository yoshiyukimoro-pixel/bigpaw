FROM python:3.13-slim
WORKDIR /app
COPY bigpaw-app.zip /tmp/bigpaw-app.zip
RUN python3 -c "import zipfile; zipfile.ZipFile('/tmp/bigpaw-app.zip').extractall('/app')"
WORKDIR /app/BIG_PAW_v1.0_FINAL3_domain_ready_package
COPY breeder-register-fix.js /tmp/breeder-register-fix.js
RUN python3 -c "from pathlib import Path; p=Path('breeder-register.html'); s=p.read_text(encoding='utf-8'); tag='<script src=\"/breeder-register-fix.js\"></script>'; p.write_text(s.replace('</body>',tag+'</body>') if tag not in s else s,encoding='utf-8')"
RUN cp /tmp/breeder-register-fix.js ./breeder-register-fix.js
ENV PORT=8080
EXPOSE 8080
CMD ["python3", "backend/server.py"]
