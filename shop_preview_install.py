"""Install a private, operator-authenticated BIG PAW shop preview.

This patches the extracted app at startup because the deployed app is shipped
inside bigpaw-app.zip. It changes only a single GET route and an operator link.
No product/payment APIs or public navigation are introduced.
"""
from pathlib import Path


MARKER = "BIGPAW_PRIVATE_SHOP_PREVIEW_V1"
ROUTE = "/operator-shop-preview.html"

PROTECTED_ROUTE = """
        # BIGPAW_PRIVATE_SHOP_PREVIEW_V1: enforced on the server, not in JS.
        if urlparse(self.path).path == '/operator-shop-preview.html':
            viewer = self.require(['operator'])
            if not viewer:
                return
            page_path = os.environ.get('BIGPAW_PRIVATE_SHOP_PREVIEW_FILE')
            if not page_path:
                self.send_error(503, 'Preview unavailable')
                return
            with open(page_path, 'rb') as page_file:
                page_bytes = page_file.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(page_bytes)))
            self.send_header('Cache-Control', 'private, no-store, max-age=0')
            self.send_header('X-Robots-Tag', 'noindex, nofollow, noarchive')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Content-Security-Policy',
                "default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(page_bytes)
            return
"""

DASHBOARD_LINK = (
    '<div class="card pad" style="margin:18px 0;background:#fff6ce;'
    'border:1px solid #efd374">'
    '<strong>🛍 大型犬ショップ（制作中）</strong>'
    '<p class="muted" style="margin:7px 0 13px">'
    '商品は未登録です。運営アカウントだけがプレビューを閲覧できます。</p>'
    '<a class="btn btn-main" style="background:#c99a32;color:#2d2612" '
    'href="/operator-shop-preview.html">非公開ショップを確認する →</a>'
    '</div>'
)


def install_private_shop_preview(repo_root: Path, app_root: Path, server_path: Path) -> None:
    repo_root = Path(repo_root)
    app_root = Path(app_root)
    server_path = Path(server_path)
    template = repo_root / "private_shop_preview.html"
    if not template.is_file():
        raise RuntimeError("Private preview template is missing.")

    server = server_path.read_text(encoding="utf-8")
    if MARKER not in server:
        anchor = "    def do_GET(self):\n"
        if server.count(anchor) != 1:
            raise RuntimeError("Cannot safely locate the sole backend GET handler.")
        server = server.replace(anchor, anchor + PROTECTED_ROUTE, 1)
        compile(server, str(server_path), "exec")  # fail before changing disk
        server_path.write_text(server, encoding="utf-8")

    operator_page = app_root / "operator-admin.html"
    page = operator_page.read_text(encoding="utf-8")
    if 'href="/operator-shop-preview.html"' not in page:
        anchor = "<h1>運営ダッシュボード</h1>"
        if page.count(anchor) != 1:
            raise RuntimeError("Cannot safely find operator dashboard heading.")
        page = page.replace(anchor, anchor + DASHBOARD_LINK, 1)
        operator_page.write_text(page, encoding="utf-8")
