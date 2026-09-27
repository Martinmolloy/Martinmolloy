# Scout PDF

Turns a Scout page (for example `go.swarmsolar.co.uk/sk-energy/index.html`) into a clickable PDF
that can be emailed. The PDF can't animate or recalculate, so it holds the sweep at every
drive-time and minimum-size setting and links them together:

- the radar at each of the 9 settings, with numbered dots that open each site
- one page per site: roof, figures, checks, people, verdict, and a grid of how it fares at every setting
- the suggested starting point, qualified shortlist, campaign and what Scout filtered out

The client's name, depot, town, contact and starting settings are read from the Scout page itself.

## Build

Needs Node with `playwright-core` and a Chromium it can find (set `CHROMIUM_PATH` if it can't),
and Python with `pypdf`.

```sh
npm install playwright-core@1.56
pip install pypdf

node scrape.js ../../go.swarmsolar.co.uk/sk-energy/index.html data.json
python3 build_html.py data.json scout.html print.css
node render.js scout.html raw.pdf
python3 finish.py raw.pdf "Swarm-Solar-Scout-SK-Energy.pdf" data.json scout.html

# check every link lands where it should
node anchors.js scout.html anchors.json
python3 check_links.py "Swarm-Solar-Scout-SK-Energy.pdf" anchors.json
```

`render.js` also reports anything that runs into the footer; if it lists a page, the content
on it is too long for the fixed 1280x720 layout.
