#!/usr/bin/env python3
from pathlib import Path

p=Path(__file__).with_name('server.py')
s=p.read_text(encoding='utf-8')

config_old="""AUTO_BACKUP_HOURS = int(os.environ.get('BIGPAW_AUTO_BACKUP_HOURS','24'))
AUTO_BACKUP_KEEP = int(os.environ.get('BIGPAW_AUTO_BACKUP_KEEP','14'))
MAX_UPLOAD_BYTES = int(os.environ.get('BIGPAW_MAX_UPLOAD_BYTES', str(8*1024*1024)))
"""
config_new="""AUTO_BACKUP_HOURS = int(os.environ.get('BIGPAW_AUTO_BACKUP_HOURS','24'))
AUTO_BACKUP_KEEP = int(os.environ.get('BIGPAW_AUTO_BACKUP_KEEP','14'))
SUPPORT_RETENTION_DAYS = max(1, int(os.environ.get('BIGPAW_SUPPORT_RETENTION_DAYS','180')))
MAX_UPLOAD_BYTES = int(os.environ.get('BIGPAW_MAX_UPLOAD_BYTES', str(8*1024*1024)))
"""
assert s.count(config_old)==1, ('support_retention_config_marker_count',s.count(config_old))
s=s.replace(config_old,config_new,1)

helper_anchor="""def run_automations_once():
"""
helper_code="""def purge_expired_support_tickets(con):
    cutoff=now()-(SUPPORT_RETENTION_DAYS*86400)
    rows=con.execute(\"SELECT id FROM support_tickets WHERE status IN ('resolved','closed') AND updated_at<=?\",(cutoff,)).fetchall()
    ids=[r['id'] for r in rows]
    for ticket_id in ids:
        con.execute('DELETE FROM support_replies WHERE ticket_id=?',(ticket_id,))
        con.execute('DELETE FROM support_tickets WHERE id=?',(ticket_id,))
    return len(ids)

"""
assert s.count(helper_anchor)==1, ('support_retention_helper_anchor_count',s.count(helper_anchor))
s=s.replace(helper_anchor,helper_code+helper_anchor,1)

auto_old="""        changes=sync_breeder_billing_suspension(con)
        backup=create_automatic_backup(con)
        con.commit()
        return {'billingReminders':reminders,'completionNudges':nudges,'visibilityChanges':len(changes),'backup':backup}
"""
auto_new="""        changes=sync_breeder_billing_suspension(con)
        support_purged=purge_expired_support_tickets(con)
        backup=create_automatic_backup(con)
        con.commit()
        return {'billingReminders':reminders,'completionNudges':nudges,'visibilityChanges':len(changes),'supportTicketsPurged':support_purged,'backup':backup}
"""
assert s.count(auto_old)==1, ('support_retention_automation_marker_count',s.count(auto_old))
s=s.replace(auto_old,auto_new,1)

get_old="""            con=db(); rows=con.execute(\"SELECT * FROM support_tickets ORDER BY CASE status WHEN 'open' THEN 0 WHEN 'reviewing' THEN 1 ELSE 2 END, created_at DESC\").fetchall(); con.close(); return self.send_json([dict(r) for r in rows])
"""
get_new="""            con=db(); purge_expired_support_tickets(con); con.commit(); rows=con.execute(\"SELECT * FROM support_tickets ORDER BY CASE status WHEN 'open' THEN 0 WHEN 'reviewing' THEN 1 ELSE 2 END, created_at DESC\").fetchall(); con.close(); return self.send_json([dict(r) for r in rows])
"""
assert s.count(get_old)==1, ('support_retention_get_marker_count',s.count(get_old))
s=s.replace(get_old,get_new,1)

delete_anchor="""    def do_DELETE(self):
        if not self.mutation_origin_allowed(): return self.send_json({'error':'invalid_origin'},403)
        path=urlparse(self.path).path
"""
delete_route="""        msupport_delete=re.fullmatch(r'/api/operator/support/([^/]+)',path)
        if msupport_delete:
            u=self.require(['operator'])
            if not u:return
            con=db(); row=con.execute('SELECT * FROM support_tickets WHERE id=?',(msupport_delete.group(1),)).fetchone()
            if not row: con.close(); return self.send_json({'error':'not_found'},404)
            if row['status'] not in ('resolved','closed'): con.close(); return self.send_json({'error':'complete_first','message':'対応完了またはクローズした問い合わせのみ削除できます。'},409)
            con.execute('DELETE FROM support_replies WHERE ticket_id=?',(row['id'],))
            con.execute('DELETE FROM support_tickets WHERE id=?',(row['id'],))
            audit(con,u['id'],'support_ticket_deleted','support_ticket',row['id'],row['status']); con.commit(); con.close()
            return self.send_json({'ok':True,'deleted':row['id']})
"""
assert s.count(delete_anchor)==1, ('support_retention_delete_anchor_count',s.count(delete_anchor))
s=s.replace(delete_anchor,delete_anchor+delete_route,1)

p.write_text(s,encoding='utf-8')
print('OPERATOR_SUPPORT_RETENTION_OK|active=open_reviewing|completed=resolved_closed|manual_delete=completed_only|auto_delete_days=180',flush=True)
