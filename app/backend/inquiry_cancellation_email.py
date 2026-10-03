"""Optional HTML action button for inquiry cancellation emails only."""
import html
import re

def confirmation_html(text):
    match=re.search(r'https?://[^\s]+/buyer-cancellation-confirmation\.html#token=[A-Za-z0-9_-]+',text)
    if not match:return None
    link=match.group(0)
    before,after=text.split(link,1)
    return ('<!doctype html><html lang="ja"><body style="font-family:sans-serif;font-size:16px;line-height:1.8;color:#29242a">'
            '<p>'+html.escape(before).replace('\n','<br>')+'</p>'
            '<p><a href="'+html.escape(link,quote=True)+'" style="display:inline-block;padding:14px 22px;background:#be3c76;color:white;text-decoration:none;border-radius:8px">取引状況を確認する</a></p>'
            '<p>'+html.escape(after).replace('\n','<br>')+'</p></body></html>')
