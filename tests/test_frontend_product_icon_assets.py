from pathlib import Path
import struct


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
PUBLIC_DIR = FRONTEND / "public"
INDEX_HTML = FRONTEND / "index.html"
APP_SHELL = FRONTEND / "src" / "shell" / "AppShell.tsx"
SHOWCASE_CHROME = FRONTEND / "src" / "views" / "home" / "ShowcaseChrome.tsx"
SITE_MANIFEST = PUBLIC_DIR / "site.webmanifest"
FAVICON_SVG = PUBLIC_DIR / "favicon.svg"
OG_COVER = PUBLIC_DIR / "og-cover.svg"


def read_png_size(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    assert header[:8] == b"\x89PNG\r\n\x1a\n"
    assert header[12:16] == b"IHDR"
    return struct.unpack(">II", header[16:24])


def test_product_icon_references_use_new_logo_assets() -> None:
    index_html = INDEX_HTML.read_text(encoding="utf-8")
    manifest = SITE_MANIFEST.read_text(encoding="utf-8")
    favicon_svg = FAVICON_SVG.read_text(encoding="utf-8")
    og_cover = OG_COVER.read_text(encoding="utf-8")
    app_shell = APP_SHELL.read_text(encoding="utf-8")
    showcase_chrome = SHOWCASE_CHROME.read_text(encoding="utf-8")
    combined = "\n".join([index_html, manifest, favicon_svg, og_cover, app_shell, showcase_chrome])

    assert 'href="/product-logo-192.png"' in index_html
    assert 'href="/product-logo-32.png"' in index_html
    assert 'href="/product-logo-180.png"' in index_html
    assert 'href="/site.webmanifest?v=3"' in index_html
    assert '"src": "/product-logo-192.png"' in manifest
    assert '"src": "/product-logo-512.png"' in manifest
    assert '<image href="/product-logo-192.png"' in favicon_svg
    assert '<image href="/product-logo-192.png"' in og_cover
    assert 'const BRAND_LOGO_SRC = "/product-logo-192.png"' in app_shell
    assert 'const BRAND_LOGO_SRC = "/product-logo-192.png"' in showcase_chrome
    assert "favicon-logo-white-v2" not in combined


def test_product_logo_assets_are_compressed_pngs() -> None:
    expected_assets = {
        "product-logo-32.png": ((32, 32), 5_000),
        "product-logo-180.png": ((180, 180), 35_000),
        "product-logo-192.png": ((192, 192), 40_000),
        "product-logo-512.png": ((512, 512), 95_000),
    }

    for filename, (expected_size, max_bytes) in expected_assets.items():
        asset = PUBLIC_DIR / filename
        assert asset.exists()
        assert read_png_size(asset) == expected_size
        assert asset.stat().st_size <= max_bytes

    favicon_ico = PUBLIC_DIR / "favicon.ico"
    assert favicon_ico.exists()
    assert favicon_ico.stat().st_size <= 60_000
