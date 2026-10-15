#!/usr/bin/env python3
"""Pure tests: no external AI calls, secrets, or production data."""
import json
import os
import sys
import unittest
from io import BytesIO
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import operator_ai_listing as ai

class DraftTests(unittest.TestCase):
    def test_missing_facts_do_not_get_fabricated(self):
        result=ai.normalize_draft({"fields":{
            "name":"ヤンヤン","breed":"サモエド","gender":"男の子",
            "birth":"2024-09-04","weight":23,"price":130000,"desc":"引退犬として新しい家族を探しています。"
        },"missing":["毛色"],"warnings":["生体価格12万円、別途2種の注射費用"]})
        self.assertEqual(result["fields"]["name"],"ヤンヤン")
        self.assertEqual(result["fields"]["price"],130000)
        self.assertEqual(result["fields"]["weight"],23)
        self.assertEqual(result["fields"]["father"],"")
        self.assertEqual(result["fields"]["healthStatus"],"")
        self.assertIn("毛色",result["missing"])
        self.assertEqual(len(result["warnings"]),1)

    def test_reject_invalid_or_misleading_values(self):
        result=ai.normalize_draft({"fields":{
           "gender":"?", "birth":"2歳","price":"-500","weight":-1,
           "desc":"メール: someone@example.com を参照 https://example.com"}}
        )
        self.assertEqual(result["fields"]["gender"],"")
        self.assertEqual(result["fields"]["birth"],"")
        self.assertEqual(result["fields"]["price"],0)
        self.assertEqual(result["fields"]["weight"],0)
        self.assertNotIn("someone@example.com",result["fields"]["desc"])
        self.assertNotIn("https://example.com",result["fields"]["desc"])
        self.assertIn("生年月日",result["missing"])

    def test_provider_key_required(self):
        with patch.dict(os.environ,{"OPENAI_API_KEY":""}):
            with self.assertRaisesRegex(RuntimeError,"ai_not_configured"):
                ai.generate_draft("サモエドのヤンヤンは2024年9月4日生まれです")

    def test_model_payload_and_response_validation(self):
        calls=[]
        def mocked(req,timeout):
            payload=json.loads(req.data.decode())
            calls.append((payload,timeout,req.headers))
            return BytesIO(json.dumps({"choices":[{"message":{"content":json.dumps({
                "fields":{"name":"ヤンヤン","breed":"サモエド","birth":"2024-09-04",
                          "gender":"男の子","price":130000},
                "missing":["毛色"],"warnings":[]
            },ensure_ascii=False)}}]}).encode())
        with patch.dict(os.environ,{"OPENAI_API_KEY":"test-only-key"}):
            with patch.object(ai,"urlopen",side_effect=mocked):
                r=ai.generate_draft("サモエドのヤンヤンは2024年9月4日生まれです。総額13万円です")
        self.assertEqual(r["fields"]["price"],130000)
        self.assertEqual(calls[0][0]["response_format"]["type"],"json_object")
        self.assertEqual(calls[0][1],35)
        self.assertNotIn("test-only-key",str(r))

if __name__=="__main__":unittest.main(verbosity=2)
