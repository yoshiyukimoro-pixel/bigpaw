#!/usr/bin/env python3
"""Guard visible public puppy inquiry shortcut without changing inquiry authorization."""
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / "puppy-detail.html").read_text(encoding="utf-8")
FORM = (ROOT / "inquiry.html").read_text(encoding="utf-8")

class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.nodes = []
    def handle_starttag(self, tag, attrs):
        self.nodes.append((tag, dict(attrs)))

class InquiryShortcutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p = Elements()
        p.feed(PAGE)
        cls.nodes = p.nodes

    def nodes_for(self, node_id):
        return [(tag, a) for tag, a in self.nodes if a.get("id") == node_id]

    def test_inquiry_visible_entry_point_while_preserving_original(self):
        self.assertEqual(len(self.nodes_for("bigpawPuppyContactShortcut")), 1)
        self.assertEqual(len(self.nodes_for("bigpawPuppyContactShortcutLink")), 1)
        tag, attrs = self.nodes_for("bigpawPuppyContactShortcutLink")[0]
        self.assertEqual(tag, "a")
        self.assertIn("btn-main", attrs["class"])
        self.assertEqual(attrs["href"], "inquiry.html")
        self.assertIn("この子の見学・問い合わせ", PAGE)
        self.assertEqual(len(self.nodes_for("inq")), 1, "Keep existing breeder-card inquiry link")

    def test_correct_puppy_routing_and_no_generic_id_free_link(self):
        self.assertRegex(PAGE, r"get\('id'\)")
        self.assertIn("link.href='inquiry.html?id='+encodeURIComponent(id)", PAGE)
        self.assertIn("if(!id||!box||!link)return", PAGE)
        self.assertIn("box.hidden=false", PAGE)
        self.assertIn("qp.get('id')||qp.get('puppy')", FORM)
        self.assertIn("BigPawBridge.addInquiry", FORM)

    def test_inquiry_role_denial_has_actionable_message(self):
        self.assertIn("x.status===403&&errorCode==='forbidden'", FORM)
        self.assertIn("一般会員（購入希望者）専用", FORM)
        self.assertIn("運営・ブリーダー用アカウントではなく", FORM)
        self.assertIn("x.status===401", FORM)
        self.assertIn("x.status===403&&errorCode==='invalid_origin'", FORM)
        self.assertIn("x.status===404&&errorCode==='puppy_not_found'", FORM)
        self.assertIn("BigPawBridge.addInquiry", FORM)
        self.assertIn("created&&created.id", FORM)

    def test_phone_placement_without_obscuring_content(self):
        css = re.search(r'<style id="bigpawPuppyContactShortcutStyle">(.*?)</style>', PAGE, re.S)
        self.assertIsNotNone(css)
        self.assertIn("@media(max-width:820px)", css.group(1))
        self.assertIn("position:fixed;bottom:0", css.group(1))
        self.assertIn("padding-bottom:calc(85px + env(safe-area-inset-bottom,0px))", css.group(1))
        self.assertIn("#bigpawPuppyContactShortcut[hidden]{display:none!important}", css.group(1))
        self.assertLess(PAGE.index('id="bigpawPuppyVideoSlot"'), PAGE.index('id="bigpawPuppyContactShortcut"'))
        self.assertLess(PAGE.index('id="bigpawPuppyContactShortcut"'), PAGE.index('id="inq"'))

if __name__ == "__main__":
    unittest.main(verbosity=2)
