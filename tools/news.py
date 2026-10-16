#!/usr/bin/env python3
"""What's new: every release of every app, as a page (news.html) and a feed (feed.xml).

Also bakes each app card's latest version into index.html (the "v1.14.0 · 16 Oct 2026" lines), so the hub is right
even when GitHub's API doesn't answer a visitor. Run by .github/workflows/news.yml once a day and on demand;
`python3 tools/news.py --from DIR` builds from saved API answers (DIR/<repo>.json) instead of asking GitHub.
Only the standard library; GITHUB_TOKEN, when set, raises GitHub's rate limit.
"""
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://erik1028.github.io/'
# repo, name on the hub, accent, icon, page (the cards' order)
APPS = [
    ('OrbitOverlay', 'OrbitOverlay', '#ff5d93', 'img/orbitoverlay.svg', 'OrbitOverlay/'),
    ('VRGallery', 'VR Gallery', '#3d8bfd', 'img/vrgallery.png', 'VRGallery/'),
    ('Mixtape', 'Mixtape', '#7fb564', 'img/mixtape.png', 'Mixtape/'),
    ('ajazz-dock', 'Hexpad', '#f8764f', 'img/hexpad.png', 'ajazz-dock/'),
    ('Prisma', 'Prisma', '#00c8aa', 'img/prisma.png', 'Prisma/'),
    ('Flux', 'Flux', '#34d399', 'img/flux.png', 'Flux/'),
    ('focal', 'Focal', '#4fd2f0', 'img/focal.png', 'focal/'),
]
SKIP_SECTION = re.compile(r'download|install|checksum|sha-?256|assets|files|upgrad', re.I)


def releases(repo, src):
    if src:
        with open(os.path.join(src, repo + '.json'), encoding='utf-8') as f:
            data = json.load(f)
    else:
        data, page = [], 1
        while True:
            req = urllib.request.Request(f'https://api.github.com/repos/Erik1028/{repo}/releases?per_page=100&page={page}',
                                         headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'erik1028-news'})
            if os.environ.get('GITHUB_TOKEN'):
                req.add_header('Authorization', 'Bearer ' + os.environ['GITHUB_TOKEN'])
            with urllib.request.urlopen(req, timeout=30) as r:
                chunk = json.load(r)
            data += chunk
            if len(chunk) < 100:
                break
            page += 1
    return [x for x in data if not x.get('draft') and x.get('published_at')]


def plain(s):
    s = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', s)
    s = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', s)
    s = re.sub(r'<[^>]+>', '', s)
    s = re.sub(r'\*\*(.+?)\*\*|__(.+?)__', lambda m: m.group(1) or m.group(2), s)
    s = re.sub(r'`([^`]+)`', r'\1', s)
    s = re.sub(r'(?<![\w*])\*(?!\s)([^*]+?)\*(?!\w)', r'\1', s)
    return re.sub(r'\s+', ' ', s).strip()


def cut(s, n):
    return s if len(s) <= n else re.sub(r'\s+\S*$', '', s[:n - 1]).rstrip(',;:—-') + '…'


def summary(body):
    """The first paragraph of prose, the first three list items and the first picture (none of them from a
    Downloads / Install / Checksums section, nor a heading or a line that is only a bold title)."""
    lead, bullets, para, item, skipping = '', [], [], None, False
    def end_para():
        # the lead is prose that comes before the list: a paragraph after it is usually how to install
        nonlocal lead, para
        if para and not lead and not bullets and item is None:
            t = plain(' '.join(para))
            if not re.match(r'(download|install|just replace|grab|get)\b', t, re.I):
                lead = t
        para = []
    def end_item():
        nonlocal item
        if item is not None and len(bullets) < 3:
            t = plain(item)
            if t:
                bullets.append(t)
        item = None
    for raw in (body or '').replace('\r', '').split('\n'):
        line = raw.strip()
        if line.startswith('#'):
            end_para(); end_item()
            skipping = bool(SKIP_SECTION.search(line))
            continue
        if skipping:
            continue
        if not line:
            end_para(); end_item()
            continue
        if re.fullmatch(r'\*\*[^*]+\*\*:?', line) or line.startswith(('|', '<details', '</details', '<summary')):
            end_para(); end_item()
            if re.fullmatch(r'\*\*[^*]+\*\*:?', line) and SKIP_SECTION.search(line):
                skipping = True
            continue
        m = re.match(r'^([-*+]|\d+\.)\s+(.*)', line)
        if m:
            end_para(); end_item()
            item = m.group(2)
        elif item is not None and raw[:1] in (' ', '\t'):
            item += ' ' + line
        elif item is not None:
            end_item(); para.append(line.lstrip('> '))
        else:
            para.append(line.lstrip('> '))
    end_para(); end_item()
    img = re.search(r'!\[([^\]]*)\]\((https?://[^)\s]+)\)|<img[^>]*src="(https?://[^"]+)"[^>]*?(?:alt="([^"]*)")?', body or '')
    pic = None
    if img:
        pic = (img.group(2) or img.group(3), img.group(1) or img.group(4) or '')
    return cut(lead, 300), [cut(b, 170) for b in bullets], pic


def subtitle(name, app, tag):
    """'VR Gallery 2.16.2 - Years and Months, fixed' -> 'Years and Months, fixed'; a release under an older name
    ('VRChronicle 1.1.0') keeps that name; just the app and its version -> nothing."""
    name = (name or '').strip()
    m = re.split(r'\s+[—–-]\s+', name, maxsplit=1)
    if len(m) == 2 and m[1]:
        sub = m[1].strip()
        return sub[:1].upper() + sub[1:]
    bare = re.sub(r'\s*v?' + re.escape(tag.lstrip('v')) + r'\s*$', '', name, flags=re.I).strip()
    if bare and bare.lower() != app.lower():
        return name
    return ''


def day(iso):
    return dt.datetime.strptime(iso[:10], '%Y-%m-%d')


def fmt(d):
    mon = 'Sept' if d.month == 9 else d.strftime('%b')      # as the cards' script writes it (en-GB)
    return f'{d.day} {mon} {d.year}'


E = html.escape


def build(src=None):
    entries, latest = [], {}
    for repo, name, acc, icon, page in APPS:
        rs = releases(repo, src)
        stable = [r for r in rs if not r.get('prerelease')]
        if stable:
            latest[repo] = max(stable, key=lambda r: r['published_at'])
        for r in rs:
            lead, bullets, pic = summary(r.get('body'))
            title = subtitle(r.get('name'), name, r['tag_name'])
            # 'Mixtape v0.6 — the first stable release!' -> 'The first stable release!' (the header shows the app and version)
            stripped = re.sub(r'^' + re.escape(name) + r'\s+v?' + re.escape(r['tag_name'].lstrip('v')) + r'\s*[—–:-]\s*', '', lead, flags=re.I)
            if stripped != lead and stripped:
                lead = stripped[:1].upper() + stripped[1:]
            same = lambda s: re.sub(r'[^a-z0-9]+', ' ', s.lower()).strip()
            if title and lead and (same(lead) == same(title) or (same(title) in same(lead) and len(lead) < len(title) + 16)):
                lead = ''          # 'Redesigned main window' over 'A redesigned main window.'
            entries.append(dict(repo=repo, app=name, acc=acc, icon=icon, page=page, tag=r['tag_name'], when=r['published_at'],
                                title=title, lead=lead, bullets=bullets, pic=pic,
                                url=r['html_url'], pre=bool(r.get('prerelease'))))
    entries.sort(key=lambda e: e['when'], reverse=True)
    counts = {repo: sum(1 for e in entries if e['repo'] == repo) for repo, *_ in APPS}

    # ---- news.html ----
    chips = [f'<button type="button" aria-pressed="true" data-app="">All <span>{len(entries)}</span></button>']
    for repo, name, acc, icon, page in APPS:
        chips.append(f'<button type="button" aria-pressed="false" data-app="{repo}" style="--acc:{acc}"><img src="{icon}" width="20" height="20" alt="">'
                     f'{E(name)} <span>{counts[repo]}</span></button>')
    rows, month = [], None
    for e in entries:
        d = day(e['when'])
        m = d.strftime('%B %Y')
        if m != month:
            month = m
            rows.append(f'<h2 class="month">{m}</h2>')
        parts = [f'<article class="entry" data-app="{e["repo"]}" style="--acc:{e["acc"]}">',
                 f'<time datetime="{e["when"][:10]}">{fmt(d)}</time><div class="body">',
                 f'<div class="hd"><a href="{e["page"]}"><img src="{e["icon"]}" width="24" height="24" alt="">{E(e["app"])}</a>'
                 f'<code>{E(e["tag"])}</code>{"<span class=pre>pre-release</span>" if e["pre"] else ""}</div>']
        if e['title']:
            parts.append(f'<h3>{E(e["title"])}</h3>')
        if e['lead']:
            parts.append(f'<p>{E(e["lead"])}</p>')
        if e['bullets']:
            parts.append('<ul>' + ''.join(f'<li>{E(b)}</li>' for b in e['bullets']) + '</ul>')
        if e['pic']:
            parts.append(f'<img class="pic" src="{E(e["pic"][0])}" alt="{E(e["pic"][1])}" loading="lazy">')
        parts.append(f'<a class="more" href="{E(e["url"])}">Release notes</a></div></article>')
        rows.append(''.join(parts))
    feeds = ' · '.join(f'<a href="https://github.com/Erik1028/{repo}/releases.atom">{E(name)}</a>' for repo, name, *_ in APPS)
    page = PAGE.replace('{{CHIPS}}', '\n'.join(chips)).replace('{{ROWS}}', '\n'.join(rows)).replace('{{FEEDS}}', feeds) \
        .replace('{{COUNT}}', str(len(entries)))
    with open(os.path.join(ROOT, 'news.html'), 'w', encoding='utf-8') as f:
        f.write(page)

    # ---- feed.xml (Atom, the 40 newest) ----
    X = lambda s: html.escape(s, quote=True)
    items = []
    for e in entries[:40]:
        title = f'{e["app"]} {e["tag"]}' + (f' — {e["title"]}' if e['title'] else '')
        text = e['lead'] or ' '.join(e['bullets'])
        items.append(f'<entry><title>{X(title)}</title><link href="{X(e["url"])}"/><id>{X(e["url"])}</id>'
                     f'<updated>{e["when"]}</updated><published>{e["when"]}</published>'
                     f'<category term="{X(e["app"])}"/><summary>{X(text)}</summary></entry>')
    feed = ('<?xml version="1.0" encoding="utf-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom">'
            f'<title>Erik1028\'s apps: new releases</title><subtitle>OrbitOverlay, VR Gallery, Mixtape, Hexpad, Prisma, Flux and Focal</subtitle>'
            f'<link href="{SITE}news.html"/><link rel="self" href="{SITE}feed.xml"/><id>{SITE}news.html</id>'
            f'<updated>{entries[0]["when"]}</updated><author><name>Erik1028</name><uri>https://github.com/Erik1028</uri></author>\n'
            + '\n'.join(items) + '\n</feed>\n')
    with open(os.path.join(ROOT, 'feed.xml'), 'w', encoding='utf-8') as f:
        f.write(feed)

    # ---- index.html: each card's version line ----
    p = os.path.join(ROOT, 'index.html')
    with open(p, encoding='utf-8') as f:
        s = f.read()
    for repo, r in latest.items():
        line = f'{r["tag_name"]} · {fmt(day(r["published_at"]))}'
        s = re.sub(r'(<span class="rel" data-repo="Erik1028/' + re.escape(repo) + r'"[^>]*><i></i>)[^<]*(</span>)',
                   lambda m: m.group(1) + E(line) + m.group(2), s)
    with open(p, 'w', encoding='utf-8') as f:
        f.write(s)
    print(f'{len(entries)} releases; newest {entries[0]["app"]} {entries[0]["tag"]}')


PAGE = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>What's new · Erik1028's apps</title>
<meta name="description" content="Every release of OrbitOverlay, VR Gallery, Mixtape, Hexpad, Prisma, Flux and Focal, newest first.">
<link rel="canonical" href="https://erik1028.github.io/news.html">
<link rel="alternate" type="application/atom+xml" title="Erik1028's apps: new releases" href="feed.xml">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Erik1028">
<meta property="og:title" content="What's new in Erik1028's apps">
<meta property="og:description" content="Every release of every app, newest first.">
<meta property="og:image" content="https://erik1028.github.io/og.png">
<meta property="og:url" content="https://erik1028.github.io/news.html">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#101116">
<link rel="icon" href="img/orbitoverlay.svg" type="image/svg+xml">
<style>
/* What's new: made by tools/news.py from the apps' GitHub releases (edit the template there, not this file).
   The hub's quiet page; each release in its own app's accent. */
:root{
  color-scheme:dark;
  --bg:#101116; --card:#17181f; --line:#262833; --text:#eceef4; --dim:#9aa0b0;
  --sans:"Segoe UI Variable Text","Segoe UI Variable","Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif;
  --display:"Segoe UI Variable Display","Segoe UI Variable","Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif;
  --mono:"Cascadia Mono",Consolas,ui-monospace,Menlo,monospace;
}
*{box-sizing:border-box}
[hidden]{display:none!important}
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--sans);font-size:17px;line-height:1.55;-webkit-font-smoothing:antialiased}
main{max-width:900px;margin:0 auto;padding-block:40px 56px;padding-left:max(20px,env(safe-area-inset-left,0px));padding-right:max(20px,env(safe-area-inset-right,0px))}
a{color:var(--text);text-decoration:underline;text-decoration-color:var(--acc,#6b7080);text-decoration-thickness:2px;text-underline-offset:3px}
a:hover{color:var(--acc,#fff)}
a:focus-visible,button:focus-visible{outline:2px solid var(--acc,#fff);outline-offset:3px;border-radius:6px}
.crumb{font-size:15px}
.crumb a{color:var(--dim);text-decoration:none}
.crumb a:hover{color:var(--text)}
h1{font-family:var(--display);font-size:clamp(36px,5vw,56px);line-height:1.05;letter-spacing:-0.03em;margin:22px 0 0}
.by{color:var(--dim);margin:14px 0 0}
.chips{display:flex;gap:8px;margin:28px 0 8px;overflow-x:auto;padding:4px 2px 8px;scrollbar-width:thin}
.chips button{flex:none;display:inline-flex;align-items:center;gap:8px;font:600 14.5px/1 var(--sans);color:var(--text);background:var(--card);border:1px solid var(--line);
  border-radius:999px;padding:0 14px 0 12px;min-height:40px;cursor:pointer;transition:border-color .2s,background .2s}
.chips button img{width:20px;height:20px;border-radius:5px}
.chips button span{color:var(--dim);font-weight:500;font-variant-numeric:tabular-nums}
.chips button:hover{border-color:color-mix(in srgb,var(--acc,#fff) 50%,var(--line))}
.chips button[aria-pressed="true"]{background:color-mix(in srgb,var(--acc,#eceef4) 18%,var(--card));border-color:var(--acc,#eceef4)}
.month{position:sticky;top:0;z-index:2;margin:0;padding:22px 0 10px;background:var(--bg);font:700 13px/1.2 var(--sans);letter-spacing:.14em;text-transform:uppercase;color:var(--dim)}
.entry{display:grid;grid-template-columns:96px minmax(0,1fr);gap:4px 24px;padding:18px 0 22px;border-top:1px solid var(--line)}
.entry time{font:500 13.5px/1.9 var(--mono);color:var(--dim);font-variant-numeric:tabular-nums}
.body{min-width:0}
.hd{display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px}
.hd a{display:inline-flex;align-items:center;gap:9px;font-weight:700;color:var(--acc);text-decoration:none}
.hd a:hover{text-decoration:underline}
.hd img{width:24px;height:24px;border-radius:6px}
.hd code{font:600 13px/1 var(--mono);padding:4px 8px;border-radius:7px;background:color-mix(in srgb,var(--acc) 16%,transparent);color:var(--text)}
.hd .pre{font-size:13px;color:var(--dim)}
.entry h3{font-family:var(--display);font-size:20px;line-height:1.25;margin:10px 0 0;text-wrap:balance}
.entry p{margin:8px 0 0;color:#c9ccd6}
.entry ul{margin:10px 0 0;padding-left:1.15em;color:var(--dim);font-size:15.5px;display:flex;flex-direction:column;gap:5px}
.entry li::marker{color:var(--acc)}
.pic{display:block;max-width:100%;max-height:320px;width:auto;height:auto;margin-top:14px;border-radius:12px;border:1px solid var(--line)}
.more{display:inline-block;margin-top:10px;font-size:14.5px}
@media (max-width:600px){.entry{grid-template-columns:1fr}.entry time{line-height:1.4}}
.none{color:var(--dim);padding:24px 0}
footer{margin-top:40px;padding-top:20px;border-top:1px solid var(--line);color:var(--dim);font-size:14.5px}
footer p{margin:0 0 8px}
footer a{color:var(--dim)}
@media (prefers-reduced-motion:reduce){.chips button{transition:none}}
</style>
</head>
<body>
<main>
<nav class="crumb"><a href="./">← All apps</a></nav>
<h1>What's new</h1>
<p class="by">Every release of every app, newest first. Follow them all with the <a href="feed.xml">feed</a> (RSS / Atom).</p>
<div class="chips" role="group" aria-label="Show the releases of">
{{CHIPS}}
</div>
<div id="list">
{{ROWS}}
</div>
<p class="none" hidden>No releases here.</p>
<footer>
<p>One app only? Its own feed: {{FEEDS}}.</p>
<p>Made from the apps' GitHub releases, once a day. Free Windows apps by <a href="https://github.com/Erik1028">Erik1028</a>.</p>
</footer>
</main>
<script>
// the chips show one app's releases (or all); #app=<repo> in the address keeps the choice, so a link can point at it
(function () {
  var chips = document.querySelectorAll('.chips button'), list = document.getElementById('list'), none = document.querySelector('.none');
  function show(app) {
    chips.forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-app') === app)); });
    var any = false, month = null, monthHas = false;
    Array.prototype.forEach.call(list.children, function (el) {
      if (el.classList.contains('month')) { if (month) month.hidden = !monthHas; month = el; monthHas = false; return; }
      var on = !app || el.getAttribute('data-app') === app;
      el.hidden = !on;
      if (on) { any = true; monthHas = true; }
    });
    if (month) month.hidden = !monthHas;
    none.hidden = any;
  }
  chips.forEach(function (b) {
    b.addEventListener('click', function () {
      var app = b.getAttribute('data-app');
      show(app);
      history.replaceState(null, '', app ? '#app=' + app : location.pathname);
    });
  });
  var m = location.hash.match(/^#app=([\\w-]+)/);
  if (m) show(m[1]);
})();
</script>
</body>
</html>
'''

if __name__ == '__main__':
    src = sys.argv[sys.argv.index('--from') + 1] if '--from' in sys.argv else None
    build(src)
