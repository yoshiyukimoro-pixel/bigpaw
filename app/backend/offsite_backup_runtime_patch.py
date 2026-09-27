#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / 'backend' / 'server.py'
server = SERVER.read_text(encoding='utf-8')

marker = """        if path=='/api/operator/backups':
            u=self.require(['operator']);
            if not u:return
            con=db(); rows=con.execute('SELECT * FROM backup_runs ORDER BY created_at DESC LIMIT 100').fetchall(); con.close(); return self.send_json([dict(r) for r in rows])
"""
route = """        mb=re.fullmatch(r'/api/operator/backups/([^/]+)/download',path)
        if mb:
            u=self.require(['operator'])
            if not u:return
            filename=Path(mb.group(1)).name
            if filename!=mb.group(1) or not filename.endswith('.sqlite3'):
                return self.send_json({'error':'invalid_backup_name'},400)
            src=BACKUPS/filename
            if not src.exists() or not src.is_file():
                return self.send_json({'error':'backup_not_found'},404)
            data=src.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type','application/octet-stream')
            self.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+quote(filename))
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','private, no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers(); self.wfile.write(data); return
"""

if route not in server:
    if marker not in server:
        raise RuntimeError('OFFSITE_BACKUP_PATCH_FAIL|backup_list_marker_missing')
    server = server.replace(marker, route + marker, 1)

SERVER.write_text(server, encoding='utf-8')
compile(server, str(SERVER), 'exec')
assert "/api/operator/backups/([^/]+)/download" in server
print('OFFSITE_BACKUP_DOWNLOAD_OK|operator_only=1|sqlite3_only=1|cache=no_store', flush=True)
