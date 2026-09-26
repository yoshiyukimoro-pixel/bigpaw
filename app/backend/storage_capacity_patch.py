from pathlib import Path

p=Path('/app/backend/server.py')
s=p.read_text(encoding='utf-8')

HELPER_MARK='def storage_status_payload():'
if HELPER_MARK not in s:
    anchor='def run_automations_once():\n'
    if s.count(anchor)!=1:
        raise SystemExit(('storage_run_anchor_count',s.count(anchor)))
    helper=r'''STORAGE_THRESHOLDS=(70,85,95)

def storage_status_payload():
    # Prefer the mounted volume's reported capacity. An explicit limit can be
    # supplied if a host filesystem ever reports a value larger than the Railway quota.
    du=shutil.disk_usage(DATA_DIR)
    reported_total=max(1,int(du.total))
    configured_mb=int(os.environ.get('BIGPAW_STORAGE_LIMIT_MB','0') or 0)
    total=(configured_mb*1024*1024) if configured_mb>0 else reported_total
    # With an explicit quota, count actual files under DATA_DIR so the percentage
    # is based on BIG PAW data rather than the host filesystem's aggregate usage.
    if configured_mb>0:
        used=0
        for base,_dirs,files in os.walk(DATA_DIR):
            for name in files:
                try: used+=os.path.getsize(os.path.join(base,name))
                except OSError: pass
        free=max(0,total-used)
        source='configured_limit'
    else:
        used=max(0,int(du.used)); free=max(0,int(du.free)); source='filesystem'
    pct=round(min(999.9,(used/total)*100),1)
    if pct>=95:
        level='critical'; threshold=95; action='至急、Railwayの保存容量を増やしてください。'
    elif pct>=85:
        level='warning'; threshold=85; action='保存容量の増量を早めに行ってください。'
    elif pct>=70:
        level='caution'; threshold=70; action='そろそろ保存容量の増量を検討してください。'
    else:
        level='normal'; threshold=0; action='現在は容量に余裕があります。'
    return {'totalBytes':total,'usedBytes':used,'freeBytes':free,'usedPercent':pct,
            'level':level,'threshold':threshold,'source':source,
            'thresholds':{'caution':70,'warning':85,'critical':95},'action':action}

def storage_monitor_tick(con):
    st=storage_status_payload()
    if st['level']=='normal': return st
    # Send one alert per threshold for the current capacity. If the volume is
    # increased, totalBytes changes and future alerts can fire again normally.
    event_key='storage_capacity:'+str(st['totalBytes'])+':'+st['level']
    if not claim_automation_event(con,event_key,'storage_capacity','storage',st['level']):
        return st
    ops=con.execute("SELECT id,email FROM users WHERE role='operator'").fetchall()
    mb=lambda n: round(n/1024/1024,1)
    title='BIG PAW 保存容量 '+str(st['threshold'])+'% アラート'
    detail=f"使用率 {st['usedPercent']}% / {mb(st['usedBytes'])}MB / {mb(st['totalBytes'])}MB。{st['action']}"
    t=now()
    for op in ops:
        con.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?,?)',
                    (make_id('n_'),op['id'],'storage_capacity',title,detail,0,t))
    con.commit()
    for op in ops:
        try:
            send_mail(op['email'],'[BIG PAW] '+title,detail+'\n\n運営ダッシュボードでも現在の容量を確認できます。')
        except Exception as exc:
            print('STORAGE_ALERT_MAIL_ERROR|'+type(exc).__name__,flush=True)
    print('STORAGE_CAPACITY_ALERT|level='+st['level']+'|used_pct='+str(st['usedPercent']),flush=True)
    return st

'''
    s=s.replace(anchor,helper+anchor,1)

call_old="def run_automations_once():\n    con=db()\n    try:\n        reminders=process_billing_reminders(con)"
call_new="def run_automations_once():\n    con=db()\n    try:\n        storage_monitor_tick(con)\n        reminders=process_billing_reminders(con)"
if 'storage_monitor_tick(con)\n        reminders=' not in s:
    if s.count(call_old)!=1:
        raise SystemExit(('storage_automation_anchor_count',s.count(call_old)))
    s=s.replace(call_old,call_new,1)

route_mark="if path=='/api/operator/storage-status':"
if route_mark not in s:
    route_anchor="        if path=='/api/operator/automations':\n"
    if s.count(route_anchor)!=1:
        raise SystemExit(('storage_route_anchor_count',s.count(route_anchor)))
    route="        if path=='/api/operator/storage-status':\n            u=self.require(['operator'])\n            if not u:return\n            return self.send_json(storage_status_payload())\n"
    s=s.replace(route_anchor,route+route_anchor,1)

boot_mark='STORAGE_CAPACITY_DIAG|total_mb='
if boot_mark not in s:
    boot_anchor="print(f'BIG PAW v1.0 server running on port {port} ({APP_ENV})')"
    if s.count(boot_anchor)!=1:
        raise SystemExit(('storage_boot_anchor_count',s.count(boot_anchor)))
    boot="""try:\n    _ss=storage_status_payload()\n    print('STORAGE_CAPACITY_DIAG|total_mb='+str(round(_ss['totalBytes']/1024/1024,1))+'|used_mb='+str(round(_ss['usedBytes']/1024/1024,1))+'|used_pct='+str(_ss['usedPercent'])+'|level='+_ss['level']+'|source='+_ss['source'],flush=True)\nexcept Exception as _se:\n    print('STORAGE_CAPACITY_DIAG_ERROR|'+type(_se).__name__,flush=True)\n"""
    s=s.replace(boot_anchor,boot+boot_anchor,1)

required=(HELPER_MARK,"storage_monitor_tick(con)\n        reminders=",route_mark,'STORAGE_CAPACITY_DIAG|total_mb=',"self.require(['operator'])")
missing=[x for x in required if x not in s]
if missing:
    raise SystemExit(('storage_capacity_gate_missing',missing))
p.write_text(s,encoding='utf-8')
print('STORAGE_CAPACITY_MONITOR_OK|interval=automation_loop|thresholds=70_85_95|operator_route=protected|dashboard_api=enabled|email=threshold_once',flush=True)
