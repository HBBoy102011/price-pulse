"""HTML rendering for the built-in demo store (no template engine needed)."""

from __future__ import annotations

from datetime import UTC, datetime
from html import escape

from app.demo_catalog import DEMO_PRODUCTS, DemoProduct, demo_price

BASE_CSS = """
:root{--bg:#07080d;--panel:#0e1018;--line:rgba(255,255,255,.09);--text:#f4f5f7;
--muted:#9aa0b4;--lime:#c8ff4d;--violet:#8b5cf6;--radius:22px}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{background:radial-gradient(900px 500px at 15% -10%,rgba(139,92,246,.22),transparent 60%),
radial-gradient(700px 500px at 95% 0%,rgba(200,255,77,.10),transparent 55%),var(--bg);
color:var(--text);font-family:'Segoe UI',Inter,system-ui,-apple-system,sans-serif;
-webkit-font-smoothing:antialiased;min-height:100vh}
a{color:inherit;text-decoration:none}
.wrap{max-width:1180px;margin:0 auto;padding:0 24px}
header{position:sticky;top:0;z-index:10;backdrop-filter:blur(18px);
background:rgba(7,8,13,.72);border-bottom:1px solid var(--line)}
.nav{display:flex;align-items:center;justify-content:space-between;height:72px;gap:20px}
.logo{display:flex;align-items:center;gap:11px;font-weight:800;letter-spacing:-.02em;font-size:19px}
.logo-mark{width:34px;height:34px;border-radius:11px;display:grid;place-items:center;
background:linear-gradient(135deg,var(--lime),#6ee7b7);color:#08090f;font-weight:900}
.nav-links{display:flex;gap:26px;color:var(--muted);font-size:14px;font-weight:600}
.nav-links a:hover{color:var(--text)}
.nav-cta{padding:10px 18px;border-radius:999px;background:var(--lime);color:#08090f;
font-weight:800;font-size:13px}
.hero{padding:64px 0 36px}
.kicker{display:inline-flex;align-items:center;gap:8px;padding:7px 14px;border:1px solid var(--line);
border-radius:999px;color:var(--muted);font-size:12px;font-weight:700;letter-spacing:.08em;
text-transform:uppercase;background:rgba(255,255,255,.02)}
.dot{width:7px;height:7px;border-radius:50%;background:var(--lime);box-shadow:0 0 12px var(--lime)}
h1{font-size:clamp(38px,5vw,62px);line-height:1.02;letter-spacing:-.045em;margin:22px 0 14px;max-width:780px}
h1 span{background:linear-gradient(100deg,var(--lime),#7dd3fc 55%,#c4b5fd);
-webkit-background-clip:text;background-clip:text;color:transparent}
.hero p{color:var(--muted);font-size:16px;line-height:1.65;max-width:620px;margin:0}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(255px,1fr));gap:20px;padding:26px 0 72px}
.card{background:linear-gradient(180deg,rgba(255,255,255,.045),rgba(255,255,255,.015));
border:1px solid var(--line);border-radius:var(--radius);padding:16px;transition:.25s;
position:relative;overflow:hidden}
.card:hover{transform:translateY(-4px);border-color:rgba(200,255,77,.35);
box-shadow:0 24px 60px -30px rgba(0,0,0,.9)}
.card-img{background:radial-gradient(circle at 50% 30%,rgba(139,92,246,.20),rgba(255,255,255,.02));
border-radius:16px;height:190px;display:grid;place-items:center;overflow:hidden;margin-bottom:16px}
.card-img img{width:78%;height:78%;object-fit:contain;filter:drop-shadow(0 18px 30px rgba(0,0,0,.45))}
.badge{position:absolute;top:26px;left:26px;padding:6px 11px;border-radius:999px;
background:rgba(200,255,77,.14);border:1px solid rgba(200,255,77,.35);color:var(--lime);
font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.06em}
.brand{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.12em;font-weight:700}
.card h3{font-size:17px;margin:6px 0 10px;letter-spacing:-.02em}
.rating{color:#fbbf24;font-size:12px;font-weight:700}
.rating span{color:var(--muted);font-weight:500}
.price-row{display:flex;align-items:baseline;gap:10px;margin-top:12px}
.price{font-size:22px;font-weight:850;letter-spacing:-.03em}
.old{color:var(--muted);text-decoration:line-through;font-size:13px}
.off{margin-left:auto;color:var(--lime);font-size:12px;font-weight:800}
.product{padding:44px 0 80px}
.crumbs{color:var(--muted);font-size:13px;margin-bottom:26px;display:flex;gap:8px;flex-wrap:wrap}
.crumbs a:hover{color:var(--text)}
.pd{display:grid;grid-template-columns:1.05fr 1fr;gap:54px;align-items:start}
.gallery{position:sticky;top:104px;background:radial-gradient(circle at 50% 25%,rgba(139,92,246,.22),
rgba(255,255,255,.02));border:1px solid var(--line);border-radius:28px;padding:34px;
display:grid;place-items:center;min-height:470px}
.gallery img{width:88%;filter:drop-shadow(0 30px 50px rgba(0,0,0,.55))}
.pd .brand{font-size:12px}
.pd h1{font-size:clamp(30px,4vw,46px);margin:10px 0 12px}
.meta{display:flex;align-items:center;gap:14px;color:var(--muted);font-size:13px;flex-wrap:wrap}
.pill{padding:6px 11px;border:1px solid var(--line);border-radius:999px;background:rgba(255,255,255,.03)}
.big-price{display:flex;align-items:baseline;gap:14px;margin:26px 0 6px}
.big-price .price{font-size:46px}
.stock{color:var(--lime);font-size:13px;font-weight:700;display:flex;align-items:center;gap:7px}
.actions{display:flex;gap:12px;margin:24px 0 28px;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:14px 24px;
border-radius:14px;font-weight:800;font-size:14px;border:1px solid transparent;cursor:pointer}
.btn-primary{background:var(--lime);color:#08090f}
.btn-ghost{border-color:var(--line);background:rgba(255,255,255,.03);color:var(--text)}
.note{display:flex;gap:12px;padding:16px 18px;border:1px dashed rgba(200,255,77,.3);
border-radius:16px;background:rgba(200,255,77,.04);font-size:13px;line-height:1.6;color:#d9e5bf}
.desc{color:var(--muted);line-height:1.7;font-size:15px;margin:26px 0}
.specs{border-top:1px solid var(--line);padding-top:8px}
.spec{display:flex;justify-content:space-between;gap:24px;padding:13px 0;border-bottom:1px solid var(--line);
font-size:14px}
.spec span:first-child{color:var(--muted)}
.spec span:last-child{text-align:right;font-weight:600}
footer{border-top:1px solid var(--line);padding:30px 0 46px;color:var(--muted);font-size:12px;line-height:1.7}
.footer-in{display:flex;justify-content:space-between;gap:24px;flex-wrap:wrap}
@media(max-width:860px){.pd{grid-template-columns:1fr;gap:28px}.gallery{position:static;min-height:340px}
.nav-links{display:none}.hero{padding-top:44px}}
"""


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)} — Demo Store</title>
<link rel="icon" href="/static/img/favicon.svg">
<style>{BASE_CSS}</style>
</head>
<body>
<header><div class="wrap nav">
  <a class="logo" href="/demo/shop"><span class="logo-mark">D</span> Demo Store</a>
  <nav class="nav-links">
    <a href="/demo/shop">Каталог</a>
    <a href="/">PricePulse</a>
    <a href="/docs">API</a>
  </nav>
  <a class="nav-cta" href="/">Отслеживать цены →</a>
</div></header>
{body}
<footer><div class="wrap footer-in">
  <div>Demo Store — учебная витрина проекта PricePulse.<br>Цены меняются автоматически и не являются офертой.</div>
  <div>Данные генерируются локально · никакие реальные магазины не парсятся</div>
</div></footer>
</body></html>"""


def fmt_money(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


def _price_card(product: DemoProduct, price: float) -> str:
    old_price = round(product.base_price * 1.14 / 10) * 10 - 1
    discount = max(0, round((1 - price / old_price) * 100))
    reviews = f"{product.reviews:,}".replace(",", " ")
    return f"""
    <a class="card" href="/demo/shop/{product.slug}">
      <span class="badge">{escape(product.badge)}</span>
      <div class="card-img"><img src="{product.image}" alt="{escape(product.title)}" loading="lazy"></div>
      <div class="brand">{escape(product.brand)} · {escape(product.category)}</div>
      <h3>{escape(product.title)}</h3>
      <div class="rating">★ {product.rating} <span>· {reviews} отзывов</span></div>
      <div class="price-row">
        <span class="price">{fmt_money(price)} ₽</span>
        <span class="old">{fmt_money(old_price)} ₽</span>
        <span class="off">−{discount}%</span>
      </div>
    </a>"""


def catalog_page() -> str:
    now = datetime.now(UTC)
    cards = "".join(
        _price_card(product, demo_price(product.base_price, product.slug, now))
        for product in DEMO_PRODUCTS
    )
    body = f"""
<main class="wrap hero">
  <div class="kicker"><span class="dot"></span> цены обновляются автоматически</div>
  <h1>Витрина, которую <span>можно парсить</span></h1>
  <p>Встроенный демо-магазин PricePulse. Скопируйте ссылку на любой товар и добавьте
  её в трекер — сервис сам найдёт название, цену и будет следить за изменениями.</p>
  <div class="grid">{cards}</div>
</main>"""
    return _page("Каталог", body)


def product_page(product: DemoProduct) -> str:
    now = datetime.now(UTC)
    price = demo_price(product.base_price, product.slug, now)
    old_price = round(product.base_price * 1.14 / 10) * 10 - 1
    discount = max(0, round((1 - price / old_price) * 100))
    reviews = f"{product.reviews:,}".replace(",", " ")
    specs = "".join(
        f'<div class="spec"><span>{escape(key)}</span><span>{escape(value)}</span></div>'
        for key, value in product.specs.items()
    )
    body = f"""
<main class="wrap product">
  <div class="crumbs"><a href="/demo/shop">Demo Store</a> <span>/</span>
    <span>{escape(product.category)}</span> <span>/</span> <span>{escape(product.title)}</span></div>
  <div class="pd">
    <div class="gallery"><img data-product-image src="{product.image}" alt="{escape(product.title)}"></div>
    <div>
      <div class="brand">{escape(product.brand)} · {escape(product.category)}</div>
      <h1 data-product-title>{escape(product.title)}</h1>
      <div class="meta">
        <span class="rating">★ {product.rating}</span>
        <span>{reviews} отзывов</span>
        <span class="pill">{escape(product.badge)}</span>
        <span class="pill">Артикул {escape(product.slug)}</span>
      </div>
      <div class="big-price">
        <span class="price" data-product-price>{fmt_money(price)} ₽</span>
        <span class="old">{fmt_money(old_price)} ₽</span>
        <span class="off">−{discount}%</span>
      </div>
      <span data-product-currency hidden>RUB</span>
      <div class="stock"><span class="dot"></span>
        <span data-product-stock data-in-stock="true">В наличии · доставка завтра</span></div>
      <div class="actions">
        <a class="btn btn-primary" href="/">Добавить в PricePulse</a>
        <a class="btn btn-ghost" href="/demo/shop">В каталог</a>
      </div>
      <div class="note">
        <span>💡</span>
        <span>Скопируйте адрес этой страницы и вставьте его в трекер. Цена в разметке
        размечена атрибутами <b>data-product-price</b> и <b>data-product-title</b> —
        именно их читает парсер.</span>
      </div>
      <p class="desc">{escape(product.description)}</p>
      <div class="specs">{specs}</div>
    </div>
  </div>
</main>"""
    return _page(product.title, body).replace(",", " ")


def demo_robots() -> str:
    return "User-agent: *\nAllow: /demo/shop\nDisallow: /api\n"
