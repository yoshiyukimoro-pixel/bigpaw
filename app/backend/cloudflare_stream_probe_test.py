#!/usr/bin/env python3
"""No-network tests for Cloudflare Stream permission probe."""
from __future__ import annotations
import io
import json
import tempfile
from pathlib import Path
from urllib.error import HTTPError
from cloudflare_stream_probe import probe_once, MARKER

class FakeResponse:
    def __init__(self, obj):
        self.raw = json.dumps(obj).encode()
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self, *_):
        return self.raw

def run():
    token = "DO_NOT_PRINT_SECRET_TOKEN_123456"
    with tempfile.TemporaryDirectory() as td:
        env = {"BIGPAW_CLOUDFLARE_STREAM_ACCOUNT_ID":"testacct","BIGPAW_CLOUDFLARE_STREAM_API_TOKEN":token,
               "BIGPAW_DATA_DIR":td,"BIGPAW_CLOUDFLARE_STREAM_API_BASE":"https://api.cloudflare.com/client/v4"}
        calls, printed = [], []
        def denied(req, timeout):
            calls.append(req)
            assert req.get_header("Authorization") == "Bearer " + token
            if req.get_method()=="GET":
                raise HTTPError(req.full_url,403,"Forbidden",{},io.BytesIO(b'{}'))
            assert req.full_url.endswith("/accounts/testacct/stream/direct_upload")
            assert json.loads(req.data)["maxDurationSeconds"] == 60
            data = b'{"success":false,"errors":[{"code":10000,"message":"Authentication error - secret credential"}]}'
            raise HTTPError(req.full_url,403,"Forbidden",{},io.BytesIO(data))
        got=probe_once(env,denied,printed.append)
        assert got["result"]=="http_rejected" and got["http_status"]==403
        assert got["codes"]==["10000"] and got["messages"]==["authentication_failed"]
        assert token not in str(printed) and "secret credential" not in str(printed)
        assert len(calls)==2 and (Path(td)/MARKER).exists()
        again=probe_once(env,denied,printed.append)
        assert again["result"]=="previously_checked" and len(calls)==2
    with tempfile.TemporaryDirectory() as td:
        env["BIGPAW_DATA_DIR"]=td
        calls=[]
        def granted(req, timeout):
            calls.append(req)
            if req.get_method()=="GET":
                return FakeResponse({"success":True,"result":[
                    {"meta":{"puppyId":"p_6a584ad3b6fb"},"status":{"state":"pendingupload"}},
                    {"meta":{"puppyId":"p_6a584ad3b6fb"},"status":{"state":"ready"}},
                    {"meta":{"puppyId":"another_puppy"},"status":{"state":"ready"}}
                ]})
            if req.get_method()=="POST":
                return FakeResponse({"success":True,"result":{"uid":"a12345678exampleabc","uploadURL":"https://upload.videodelivery.net/hidden"}})
            assert req.get_method()=="DELETE"
            assert req.full_url.endswith("/stream/a12345678exampleabc")
            return FakeResponse({"success":True,"result":None})
        got=probe_once(env,granted,printed.append)
        assert got["result"]=="ticket_created" and got["ticket_deleted"] is True
        assert got["upload_host"]=="upload.videodelivery.net" and got["upload_scheme"]=="https"
        assert len(calls)==3
        assert any("BIGPAW_STREAM_RECENT|status=ok|affected_video_tickets=2|states=pendingupload:1,ready:1" in x for x in printed)
        assert "hidden" not in str(printed)
    print("BIGPAW_STREAM_DIAGNOSTIC_TEST_OK|403_sanitized|once_only|ticket_deleted")

if __name__ == "__main__":
    run()
