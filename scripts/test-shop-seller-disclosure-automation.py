"""Unit safety tests for *dormant* email-verified seller disclosure.
All seller contact data below are fictitious; provider calls are mocked.
"""
import sqlite3
import unittest
from shop_payments import seller_disclosure_automation as a

ENV = {
    "BIGPAW_ENV": "production",
    "BIGPAW_SHOP_SELLER_DISCLOSURE_AUTO_ENABLED": "1",
    "RESEND_API_KEY": "re_FAKE_FOR_OFFLINE_TEST_ONLY",
    "BIGPAW_SHOP_SELLER_NAME": "テスト販売者",
    "BIGPAW_SHOP_SELLER_POSTAL": "000-0000",
    "BIGPAW_SHOP_SELLER_ADDRESS": "テスト県テスト市TEST-ONLY",
    "BIGPAW_SHOP_SELLER_PHONE": "0300000000",
}

def fresh():
    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE support_tickets (
       id TEXT PRIMARY KEY,email TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'open',
       operator_note TEXT NOT NULL DEFAULT '',updated_at INTEGER NOT NULL)""")
    db.execute("""CREATE TABLE audit_logs (
       id TEXT PRIMARY KEY,user_id TEXT,action TEXT,target_type TEXT,
       target_id TEXT,detail TEXT,created_at INTEGER)""")
    db.execute("INSERT INTO support_tickets VALUES(?,?,'open','',?)",
               ("sup_demo","reader@example.invalid",100))
    db.commit()
    return db

def fake_outbox(outbox):
    def deliver(key, to, subject, body, idem):
        assert key == ENV["RESEND_API_KEY"]
        outbox.append((to,subject,body,idem))
        return "mail_TEST12345"
    return deliver

class DisclosureTests(unittest.TestCase):
    def test_not_enabled_by_default_and_no_mail(self):
        db=fresh(); out=[]
        self.assertFalse(a.ready({}))
        self.assertEqual(a.request_for_ticket(db,"sup_demo","reader@example.invalid",
                         env={**ENV,"BIGPAW_SHOP_SELLER_DISCLOSURE_AUTO_ENABLED":"0"},
                         sender=fake_outbox(out),clock=lambda:100),
                         "disabled")
        self.assertEqual(a.confirm_request(db,"A"*43,env={**ENV,"BIGPAW_ENV":"development"},
                         sender=fake_outbox(out)),"disabled")
        self.assertEqual(out,[])

    def test_challenge_then_private_mail_only_after_token_confirmation(self):
        db=fresh(); out=[]; token="Z"*43
        self.assertEqual(a.request_for_ticket(db,"sup_demo","reader@example.invalid",
                         env=ENV,clock=lambda:100,sender=fake_outbox(out),
                         token_factory=lambda n:token),"verification_sent")
        self.assertEqual(len(out),1)
        self.assertEqual(out[0][0],"reader@example.invalid")
        self.assertNotIn(ENV["BIGPAW_SHOP_SELLER_ADDRESS"],out[0][2])
        self.assertNotIn(ENV["BIGPAW_SHOP_SELLER_PHONE"],out[0][2])
        self.assertNotIn(token,str(list(db.execute("SELECT * FROM food_seller_disclosure"))))
        self.assertEqual(a.confirm_request(db,"Q"*43,env=ENV,clock=lambda:120,
                         sender=fake_outbox(out)),"invalid_or_expired")
        self.assertEqual(len(out),1)
        self.assertEqual(a.confirm_request(db,token,env=ENV,clock=lambda:120,
                         sender=fake_outbox(out)),"provider_accepted")
        self.assertEqual(len(out),2)
        self.assertIn(ENV["BIGPAW_SHOP_SELLER_ADDRESS"],out[1][2])
        self.assertIn(ENV["BIGPAW_SHOP_SELLER_PHONE"],out[1][2])
        self.assertEqual(db.execute("SELECT status FROM support_tickets").fetchone()[0],"reviewing")
        self.assertIn("到達未確認",db.execute("SELECT operator_note FROM support_tickets").fetchone()[0])
        self.assertEqual(a.confirm_request(db,token,env=ENV,clock=lambda:121,
                         sender=fake_outbox(out)),"invalid_or_expired")
        self.assertEqual(len(out),2,"No second disclosure email")
        self.assertEqual(db.execute("SELECT status FROM food_seller_disclosure").fetchone()[0], "provider_accepted")
        dump=str(list(db.execute("SELECT * FROM food_seller_disclosure")))+str(list(
            db.execute("SELECT * FROM audit_logs")))+str(list(db.execute("SELECT * FROM support_tickets")))
        self.assertNotIn(ENV["BIGPAW_SHOP_SELLER_ADDRESS"],dump)
        self.assertNotIn(ENV["BIGPAW_SHOP_SELLER_PHONE"],dump)

    def test_expiry_blocks_disclosure(self):
        db=fresh(); out=[]; token="A"*43
        self.assertEqual(a.request_for_ticket(db,"sup_demo","reader@example.invalid",
                         env=ENV,clock=lambda:100,sender=fake_outbox(out),
                         token_factory=lambda n:token),"verification_sent")
        self.assertEqual(a.confirm_request(db,token,env=ENV,clock=lambda:100+a.TTL,
                         sender=fake_outbox(out)),"invalid_or_expired")
        self.assertEqual(len(out),1)

    def test_ambiguous_provider_outcome_never_resends(self):
        db=fresh(); out=[]; token="B"*43
        a.request_for_ticket(db,"sup_demo","reader@example.invalid",
                         env=ENV,clock=lambda:100,sender=fake_outbox(out),
                         token_factory=lambda n:token)
        def timeout(*args):
            out.append(args)
            raise TimeoutError()
        self.assertEqual(a.confirm_request(db,token,env=ENV,clock=lambda:110,
                         sender=timeout),"delivery_unknown")
        self.assertEqual(a.confirm_request(db,token,env=ENV,clock=lambda:111,
                         sender=fake_outbox(out)),"invalid_or_expired")
        self.assertEqual(len(out),2)
        self.assertEqual(db.execute("SELECT status FROM support_tickets").fetchone()[0],"open")

    def test_bad_email_and_missing_seller_data_do_not_send(self):
        db=fresh(); out=[]
        self.assertFalse(a.ready({**ENV,"BIGPAW_SHOP_SELLER_ADDRESS":""}))
        self.assertFalse(a.ready({**ENV,"BIGPAW_SHOP_SELLER_PHONE":"not-a-phone"}))
        self.assertEqual(a.request_for_ticket(db,"sup_demo","victim@example.invalid\r\nBcc:evil@example.invalid",
                         env=ENV,sender=fake_outbox(out)),"invalid_recipient")
        self.assertEqual(out,[])

if __name__=="__main__":unittest.main()
