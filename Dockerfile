FROM python:3.13-slim
WORKDIR /app
COPY app/ /app/
RUN ["python3", "-c", "from pathlib import Path; p=Path('/app/backend/server.py'); s=p.read_text(encoding='utf-8'); a=\"if path=='/api/puppies':\\n            u=self.require(['buyer','breeder','operator']);\"; b=\"if path=='/api/puppies':\\n            u=self.require(['breeder','operator']);\"; c=\"m=re.fullmatch(r'/api/puppies/([^/]+)',path)\\n        if m:\\n            u=self.require(['buyer','breeder','operator']);\"; d=\"m=re.fullmatch(r'/api/puppies/([^/]+)',path)\\n        if m:\\n            u=self.require(['breeder','operator']);\"; e=\"iq=re.fullmatch(r'/api/inquiries/([^/]+)',path)\\n        if iq:\\n            u=self.require(['buyer','breeder','operator']);\"; f=\"iq=re.fullmatch(r'/api/inquiries/([^/]+)',path)\\n        if iq:\\n            u=self.require(['breeder','operator']);\"; assert s.count(a)==1, ('create_guard_count',s.count(a)); assert s.count(c)==1, ('edit_guard_count',s.count(c)); assert s.count(e)==1, ('inquiry_guard_count',s.count(e)); s=s.replace(a,b,1).replace(c,d,1).replace(e,f,1); p.write_text(s,encoding='utf-8'); print('PERMISSION_GUARD_OK|puppy_create=breeder_operator|puppy_edit=breeder_operator|inquiry_update=breeder_operator',flush=True)"]
ENV PORT=8080
EXPOSE 8080
CMD ["python3", "backend/server.py"]
