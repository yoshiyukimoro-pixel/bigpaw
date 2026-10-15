#!/usr/bin/env python3
"""Apply a narrow operator-listing UI enhancement after existing release gates.

The normal builder first applies its health, appeal-point and photo patches to
the original HTML. This late patch preserves those save/upload paths and only
adds kennel-scoped ownership and a real dog-name input.
"""
from pathlib import Path

page = Path(__file__).resolve().parents[1] / "breeder-puppy-new.html"
html = page.read_text(encoding="utf-8")
if "OPERATOR_PROXY_LISTING_UI_V1" not in html:
    def replace_once(old, new, label):
        global html
        n = html.count(old)
        if n != 1:
            raise SystemExit(f"PROXY_LISTING_UI_FAILED|{label}|expected=1|found={n}")
        html = html.replace(old, new, 1)

    replace_once(
        '<div class="field"><label>生年月日</label>',
        '<div class="field"><label>お名前（任意）</label><input id="puppyName" maxlength="100" placeholder="例：ヤンヤン"></div><div class="field"><label>生年月日</label>',
        "dog_name_field",
    )
    replace_once(
        "let editId=new URLSearchParams(location.search).get('id')||sessionStorage.getItem('bigpawEditPuppyId');",
        "let editId=new URLSearchParams(location.search).get('id')||(new URLSearchParams(location.search).has('breederId')?'':sessionStorage.getItem('bigpawEditPuppyId'));",
        "create_does_not_reuse_stale_edit_id",
    )
    replace_once(
        "const ds=await BigPawBridge.breederPuppies();",
        "const selectedScope=new URLSearchParams(location.search).get('breederId')||'';const ds=selectedScope?await BigPawAPI.breederPuppies({breederId:selectedScope}):await BigPawBridge.breederPuppies();",
        "edit_scope",
    )
    replace_once(
        "Object.entries(m).forEach(([k,v])=>{",
        "puppyName.value=d.name||'';Object.entries(m).forEach(([k,v])=>{",
        "edit_dog_name_hydration",
    )
    replace_once(
        "BigPawBridge.updatePuppy(editId,{name:color.value+'の'+gender.value,",
        "BigPawBridge.updatePuppy(editId,{name:(puppyName.value||'').trim()||(color.value+'の'+gender.value),",
        "edit_dog_name",
    )
    replace_once(
        "BigPawBridge.addPuppy({name:color.value+'の'+gender.value,",
        "BigPawBridge.addPuppy({breederId:window.bigpawProxyId||'',name:(puppyName.value||'').trim()||(color.value+'の'+gender.value),",
        "operator_target_and_dog_name",
    )
    replace_once(
        "alert(editId?'変更を保存しました。':'子犬情報を掲載しました。');location.href='admin.html'",
        "alert(editId?'変更を保存しました。':'子犬情報を掲載しました。');location.href='admin.html'+(window.bigpawProxyId?'?breederId='+encodeURIComponent(window.bigpawProxyId):'')",
        "return_to_selected_kennel",
    )
    replace_once(
        '</body>',
        '<!-- OPERATOR_PROXY_LISTING_UI_V1 --><script src="assets/operator-proxy-listing.js"></script></body>',
        "script_load",
    )
    page.write_text(html, encoding="utf-8")
print("OPERATOR_PROXY_LISTING_UI_OK|scope=selected_breeder|dog_name=optional|photo_and_health_paths=preserved", flush=True)
