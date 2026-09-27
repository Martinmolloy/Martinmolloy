"""Rewrites Chromium's named-destination links as direct [page /Fit] links, adds bookmarks and metadata.

Usage: python3 finish.py raw.pdf out.pdf data.json scout.html
"""
import json
import re
import sys

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, NameObject, NumberObject

raw, out, data = sys.argv[1], sys.argv[2], json.load(open(sys.argv[3]))
r = PdfReader(raw)
w = PdfWriter(clone_from=r)
order = re.findall(r'<section class="page[^"]*" id="([^"]+)"', open(sys.argv[4]).read())
assert len(order) == len(r.pages), (len(order), len(r.pages))
dest_page = {n: i for i, n in enumerate(order)}
named = {name.lstrip('/'): r.get_destination_page_number(d) for name, d in r.named_destinations.items()}
assert all(dest_page[n] == i for n, i in named.items()), 'named destinations disagree with page order'
refs = [pg.indirect_reference for pg in w.pages]
fixed = uri = 0
for pg in w.pages:
    for a in pg.get('/Annots') or []:
        a = a.get_object()
        if a.get('/Subtype') != '/Link':
            continue
        dname = a.get('/Dest')
        if dname is not None and not isinstance(dname, ArrayObject):
            n = str(dname).lstrip('/')
            a[NameObject('/Dest')] = ArrayObject([refs[dest_page[n]], NameObject('/Fit')])
            fixed += 1
        elif '/A' in a:
            uri += 1
        a[NameObject('/Border')] = ArrayObject([NumberObject(0), NumberObject(0), NumberObject(0)])
# bookmarks
dd, ds = data['defaults']['drive'], data['defaults']['size']
rows = [x for x in data['settings'] if x['drive'] == dd and x['size'] == ds][0]['rows']
w.add_outline_item(f'Radar: {dd} min, {ds} kWp', dest_page[f'set-{dd}-{ds}'])
w.add_outline_item('Suggested starting point and shortlist', dest_page['plan'])
w.add_outline_item('Campaign 01 and what Scout filtered out', dest_page['campaign'])
sites = w.add_outline_item('Sites', dest_page['site-' + rows[0]['id']])
for row in rows:
    w.add_outline_item(f"{row['n']} {row['name']}", dest_page['site-' + row['id']], parent=sites)
others = [(d, s) for d in (60, 90, 120) for s in (50, 100, 250) if (d, s) != (dd, ds)]
other = w.add_outline_item('Other settings', dest_page['set-%d-%d' % others[0]])
for d, s in others:
    w.add_outline_item(f'{d} min, {s} kWp', dest_page[f'set-{d}-{s}'], parent=other)
w.add_metadata({
    '/Title': data['title'],
    '/Author': 'Swarm Solar',
    '/Subject': f"Sample territory sweep from {data['client']['depot']}, {data['client']['town']}",
    '/Keywords': f"Swarm Solar, Scout, {data['client']['name']}, commercial solar",
    '/Creator': 'Swarm Solar',
})
w._root_object[NameObject('/OpenAction')] = ArrayObject([refs[0], NameObject('/Fit')])
w._root_object[NameObject('/PageLayout')] = NameObject('/SinglePage')
w.write(out)
print(f'pages {len(w.pages)} | internal links rewritten {fixed} | web/mail links {uri}')
