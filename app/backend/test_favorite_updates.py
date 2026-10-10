import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from favorite_updates import ensure_schema, queue_change, record_view, engagement, deliver_due, mail_content, picture_url

class FavoriteFeatureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'tests.sqlite3'
        with self.connect() as db:
            db.executescript("""
                PRAGMA foreign_keys=ON;
                CREATE TABLE users (
                    id TEXT PRIMARY KEY, email TEXT NOT NULL,role TEXT NOT NULL,
                    email_verified INTEGER NOT NULL, favorite_email_enabled INTEGER NOT NULL
                );
                CREATE TABLE breeders (
                    id TEXT PRIMARY KEY,review_status TEXT NOT NULL DEFAULT 'approved',
                    billing_suspended INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE puppies (
                    id TEXT PRIMARY KEY,breeder_id TEXT,review_status TEXT NOT NULL,
                    name TEXT,breed TEXT,price INTEGER,status TEXT,image_url TEXT
                );
                CREATE TABLE favorites (
                    user_id TEXT,puppy_id TEXT,
                    PRIMARY KEY(user_id,puppy_id)
                );
                INSERT INTO breeders(id) VALUES('b1'),('b2');
                INSERT INTO puppies VALUES('p1','b1','approved','ブラックの男の子','スタンダードプードル',250000,'募集中','/uploads/old.jpg');
                INSERT INTO puppies VALUES('p2','b2','approved','別の子','ラブラドールレトリバー',230000,'募集中','/uploads/other.jpg');
                INSERT INTO users VALUES('u1','one@example.com','buyer',1,1);
                INSERT INTO users VALUES('u2','two@example.com','buyer',1,0);
                INSERT INTO users VALUES('u3','three@example.com','buyer',0,1);
                INSERT INTO favorites VALUES('u1','p1'),('u2','p1'),('u3','p1');
            """)
            ensure_schema(db)
            db.commit()
        self.sent=[]

    def tearDown(self):
        self.temp.cleanup()

    def connect(self):
        c=sqlite3.connect(str(self.path))
        c.row_factory=sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        return c

    def sender(self,address,subject,plain,html):
        self.sent.append((address,subject,plain,html))
        return True

    def update_price(self,new):
        with self.connect() as db:
            db.execute('UPDATE puppies SET price=? WHERE id=?',(new,'p1'))
            db.commit()

    def test_photo_email_uses_new_picture_and_groups_edits(self):
        with self.connect() as db:
            queue_change(db,'p1','price',old_price=250000,new_price=220000,timestamp=100)
            queue_change(db,'p1','photo',photo_url='/uploads/new.jpg',timestamp=150)
            queue_change(db,'p1','description',timestamp=160)
            db.execute("UPDATE puppies SET price=220000 WHERE id='p1'")
            db.commit()
        assert deliver_due(self.connect,'https://bigpaw.site',self.sender,timestamp=760)['sent']==1
        self.assertEqual(len(self.sent),1)
        address,subject,plain,markup=self.sent[0]
        self.assertEqual(address,'one@example.com')
        self.assertIn('250,000円 → 220,000円',plain)
        self.assertIn('https://bigpaw.site/uploads/new.jpg',markup)
        self.assertNotIn('old.jpg',markup)
        self.assertIn('写真',plain)
        self.assertIn('紹介文',plain)
        self.assertIn('puppy-detail.html?id=p1',markup)
        self.assertEqual(deliver_due(self.connect,'https://bigpaw.site',self.sender,timestamp=999)['sent'],0)
        self.assertEqual(len(self.sent),1)

    def test_non_photo_change_uses_existing_main_picture(self):
        with self.connect() as db:
            queue_change(db,'p1','price',old_price=250000,new_price=240000,timestamp=100)
            db.execute('UPDATE puppies SET price=240000 WHERE id=?',('p1',))
            db.commit()
        deliver_due(self.connect,'https://bigpaw.site',self.sender,timestamp=701)
        self.assertEqual(len(self.sent),1)
        self.assertIn('/uploads/old.jpg',self.sent[0][3])

    def test_opted_out_and_unverified_buyers_never_receive_mail(self):
        with self.connect() as db:
            db.execute('UPDATE users SET favorite_email_enabled=0')
            queue_change(db,'p1','photo',photo_url='/uploads/new.jpg',timestamp=100)
            db.commit()
        result=deliver_due(self.connect,'https://bigpaw.site',self.sender,timestamp=701)
        self.assertEqual(result['sent'],0)
        self.assertEqual(self.sent,[])

    def test_no_notification_for_reverted_price(self):
        with self.connect() as db:
            queue_change(db,'p1','price',old_price=250000,new_price=210000,timestamp=100)
            db.commit()
        deliver_due(self.connect,'https://bigpaw.site',self.sender,timestamp=701)
        self.assertEqual(self.sent,[])

    def test_failure_can_retry_without_duplicate_success(self):
        count=[0]
        def flaky(*args):
            count[0]+=1
            if count[0]==1:return False
            self.sent.append(args)
            return True
        with self.connect() as db:
            queue_change(db,'p1','photo',photo_url='/uploads/new.jpg',timestamp=100)
            db.commit()
        a=deliver_due(self.connect,'https://bigpaw.site',flaky,timestamp=701)
        self.assertEqual(a['failed'],1)
        self.assertEqual(count[0],1)
        b=deliver_due(self.connect,'https://bigpaw.site',flaky,timestamp=701+1801)
        self.assertEqual(b['sent'],1)
        self.assertEqual(count[0],2)
        deliver_due(self.connect,'https://bigpaw.site',flaky,timestamp=701+3602)
        self.assertEqual(count[0],2)

    def test_aggregate_views_not_repeat_people(self):
        with self.connect() as db:
            self.assertTrue(record_view(db,'p1','visitor_a_123456',timestamp=1000))
            self.assertTrue(record_view(db,'p1','visitor_a_123456',timestamp=1300))
            self.assertTrue(record_view(db,'p1','visitor_b_123456',timestamp=1600))
            self.assertTrue(record_view(db,'p1','visitor_a_123456',timestamp=90000))
            self.assertTrue(record_view(db,'p2','visitor_a_123456',timestamp=1000))
            db.execute("INSERT INTO favorites VALUES('u1','p2')")
            db.commit()
            b1=engagement(db,'b1')
            b2=engagement(db,'b2')
        self.assertEqual(b1['p1'],{'favoriteCount':3,'viewCount':4,'viewerCount':2})
        self.assertNotIn('p2',b1)
        self.assertEqual(b2['p2'],{'favoriteCount':1,'viewCount':1,'viewerCount':1})
        self.assertNotIn('p1',b2)

    def test_hidden_puppy_not_queued(self):
        with self.connect() as db:
            db.execute("UPDATE puppies SET review_status='rejected' WHERE id='p1'")
            self.assertFalse(queue_change(db,'p1','photo',photo_url='/uploads/new.jpg',timestamp=100))
            self.assertFalse(record_view(db,'p1','visitor_a_123456',timestamp=100))
            db.commit()

    def test_image_url_is_safely_restricted(self):
        self.assertEqual(picture_url('/uploads/test.jpg','https://bigpaw.site'),'https://bigpaw.site/uploads/test.jpg')
        self.assertEqual(picture_url('javascript:alert(1)','https://bigpaw.site'),'')
        self.assertEqual(picture_url('//untrusted.example/test','https://bigpaw.site'),'')
        self.assertEqual(picture_url('/api/operator/users','https://bigpaw.site'),'')

if __name__=='__main__':
    unittest.main()
