#!/usr/bin/env python3
"""Install operator-scoped proxy puppy creation without changing breeder creation.

Run after the normal Docker build patches. Fail closed if the expected route
has changed instead of silently deploying an unsafe operator listing path.
"""
from pathlib import Path

server = Path(__file__).resolve().parent / "server.py"
source = server.read_text(encoding="utf-8")
marker = "            pid=make_id('p_'); breed=body.get('breed','その他大型犬'); gender=body.get('gender','男の子')"
sentinel = "OPERATOR_PROXY_LISTING_V1"
if sentinel not in source:
    if source.count(marker) != 1:
        raise SystemExit(f"PROXY_LISTING_PATCH_FAILED|create_route_anchor_count={source.count(marker)}")
    replacement = """            # OPERATOR_PROXY_LISTING_V1: only an approved, explicitly selected
            # breeder can own an operator-created listing. Never trust the
            # kennel name, location or ownership from the submitted form.
            if u['role']=='operator':
                selected_breeder_id=str(body.get('breederId') or '').strip()
                if not selected_breeder_id:
                    con.close(); return self.send_json({'error':'operator_breeder_selection_required'},400)
                target=con.execute('SELECT * FROM breeders WHERE id=?',(selected_breeder_id,)).fetchone()
                if not target:
                    con.close(); return self.send_json({'error':'breeder_not_found'},404)
                if target['review_status']!='approved':
                    con.close(); return self.send_json({'error':'breeder_not_approved'},403)
                breeder_id=target['id']
                breeder_name=target['kennel_name']
                area=target['prefecture']
                area_key=AREA_KEYS.get(area,'other')
""" + marker
    source = source.replace(marker, replacement, 1)
    compile(source, str(server), "exec")
    server.write_text(source, encoding="utf-8")
print("OPERATOR_PROXY_LISTING_OK|operator_explicit_breeder=required|approved_target=required|owner_location_from_db", flush=True)
