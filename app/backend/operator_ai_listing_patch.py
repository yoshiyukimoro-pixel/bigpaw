#!/usr/bin/env python3
"""Narrow, fail-closed route for operator AI listing drafts.

Install last in the Dockerfile, after existing audited runtime/build patches.
Never modify ordinary dog creation, media upload, or public endpoints.
"""
from pathlib import Path

server=Path(__file__).resolve().parent/"server.py"
source=server.read_text(encoding="utf-8")
anchor="""    def do_POST(self):
        if not self.mutation_origin_allowed(): return self.send_json({'error':'invalid_origin'},403)
        path=urlparse(self.path).path
"""
sentinel="OPERATOR_AI_LISTING_ROUTE_V1"
if sentinel not in source:
    assert source.count(anchor)==1, "AI_DRAFT_ROUTE_INSTALL_FAILED"
    added=anchor+"""        # OPERATOR_AI_LISTING_ROUTE_V1: preview-only; cannot publish a dog.
        if path=='/api/operator/ai-listing-draft':
            u=self.require(['operator'])
            if not u:return
            body=self.json_body()
            if body.get('consent') is not True:
                return self.send_json({'error':'ai_consent_required','message':'AI解析のため文章を送信することに同意してください。'},400)
            breeder_id=str(body.get('breederId') or '').strip()
            if not breeder_id:
                return self.send_json({'error':'breeder_required'},400)
            con=db()
            breeder=con.execute('SELECT id,review_status FROM breeders WHERE id=?',(breeder_id,)).fetchone()
            con.close()
            if not breeder:
                return self.send_json({'error':'breeder_not_found'},404)
            if breeder['review_status']!='approved':
                return self.send_json({'error':'breeder_not_approved'},403)
            notes=str(body.get('notes') or '').strip()
            if not 15<=len(notes)<=12000:
                return self.send_json({'error':'notes_invalid','message':'文章は15〜12,000文字で入力してください。'},400)
            from operator_ai_listing import generate_draft
            try:
                draft=generate_draft(notes)
            except ValueError as exc:
                return self.send_json({'error':'notes_invalid','message':str(exc)},400)
            except RuntimeError as exc:
                reason=str(exc)
                return self.send_json({'error':reason},503 if reason=='ai_not_configured' else 502)
            except Exception:
                return self.send_json({'error':'ai_provider_unavailable'},502)
            # Do not log notes or the model's draft (breeder information).
            return self.send_json(draft,200)
"""
    source=source.replace(anchor,added,1)
    # Existing UI limits new photos to ten; enforce the same limit on the API.
    upload_anchor="            ext={ 'image/jpeg':'.jpg','image/png':'.png','image/webp':'.webp'}[mime]"
    assert source.count(upload_anchor)==1, "PHOTO_LIMIT_INSTALL_FAILED"
    upload_guard="""            if puppy_id and puppy_id!='breeder-proof':
                photo_db=db()
                puppy_exists=photo_db.execute('SELECT 1 FROM puppies WHERE id=?',(puppy_id,)).fetchone()
                if not puppy_exists:
                    photo_db.close(); return self.send_json({'error':'puppy_not_found'},404)
                existing_photo_count=photo_db.execute('SELECT count(*) AS n FROM uploads WHERE puppy_id=?',(puppy_id,)).fetchone()['n']
                photo_db.close()
                if existing_photo_count>=10:
                    return self.send_json({'error':'photo_limit_reached','message':'写真は最大10枚までです。'},409)
""" + upload_anchor
    source=source.replace(upload_anchor,upload_guard,1)
    compile(source,str(server),"exec")
    server.write_text(source,encoding="utf-8")
print("OPERATOR_AI_DRAFT_ROUTE_OK|preview_only=1|operator_only=1|consent=required|no_auto_publish=1",flush=True)
