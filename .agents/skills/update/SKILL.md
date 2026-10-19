---
name: update
description: Update the Saturn Kodi add-on to what ERR serves now, or extend it. Use when checking ERR for changes ("has ERR changed anything?", before a release), when `./run-tests.sh api` fails, when a listing, menu entry or stream has gone missing or answers an unexpected shape, when tests/fixtures needs re-recording, and when adding or changing a plugin:// route (a menu entry, listing, folder or playback action) or any user-visible text. Covers tools/survey_api.py, ERR's other sites, re-deriving endpoints from the front-end bundles, the client and parsers, Router.ACTIONS, both string catalogues, navigation icons, fixtures and tests.
compatibility: The survey and the live tests need network access to jupiter.err.ee, lasteekraan.err.ee, eestiraadio.err.ee and services.err.ee. Everything else runs offline in the repo's .venv.
---

# Updating Saturn

ERR publishes no API documentation and changes the service without notice.
`./run-tests.sh api` catches an endpoint that broke; only the survey catches
something ERR stopped offering, or started offering, while every endpoint
still answers. Work through the steps in order; a route added for its own sake
starts at step 4.

## 1. Survey

```bash
./run-tests.sh api
.venv/bin/python tools/survey_api.py
```

The survey changes nothing. It prints every category on Saturn's root with
its rows (kind, size, item types), every menu of every catalogue, and the API
calls in the bundles of jupiter.err.ee, lasteekraan.err.ee and any other ERR
site a menu links to. It ends with **Findings**; a clean run has none:

| Finding | Means |
|---------|-------|
| `category: … lists no titles` / `failed` | A category Saturn offers is gone or broken |
| `menu: KEY/NAME -> LINK has N programmes Saturn lists nowhere` | A menu entry Saturn does not offer holds playable titles |
| `menu: … failed` | A catalogue's menu, or a page it links to, did not load |
| `bundle: HOST failed` | An ERR site's front end could not be fetched; rerun, or check the site by hand |
| `site: … links to HOST` | A menu points at an ERR site whose API Saturn does not use |
| `row: … unknown keys` / `item types` | ERR changed what a row carries |
| `endpoint: Saturn calls …; no ERR front end does` | An endpoint ERR's own sites stopped calling |

## 2. Decide

- **Broken**: Saturn shows less than it should, or would fail. Go to 3.
- **New**: ERR offers something Saturn does not use. If it belongs in Saturn,
  it is a route (4), usually with a client method first (3).
- **Not a change**: the survey misread something. Fix the survey, so a clean
  run stays at zero.

ERR runs several sites over one content-id space. A new site matters only if
it lists programmes Jupiter's API does not, and costs one client method, not a
second client, when its ids open through `getContentPageData`. Eesti Raadio's
`search/az` is the example: active programmes (`state` 1) open through
Jupiter with `AUDIO_ROOT_ID`, archived ones (`state` 2) answer 404. These
sites keep their API at `https://SITE/api` and answer 403 without Saturn's
headers:

```bash
curl -s -A 'Mozilla/5.0' -H 'Referer: https://jupiter.err.ee/' \
  'https://eestiraadio.err.ee/api/v1/search/az?active=true' | head -c 1500
```

Row order follows ERR's own flags: rows with `manual.highTimeline` (picked by
editors) are sorted A–Z in Estonian order, rows ERR fills itself keep its
newest-first order, `manual.banner` leads. A new row kind means revisiting
that rule in `categories.py` and the router.

## 3. Fix the client

A 404 is not proof an endpoint is dead: read the call site before deciding.
Confirm by hand first:

```bash
curl -s -H 'Referer: https://jupiter.err.ee/' \
  'https://services.err.ee/api/v2/menu/getMenuById?menuId=555' | head -c 2000
```

Every endpoint the site uses is in its bundle:

```bash
curl -s https://jupiter.err.ee/ | grep -oE '(main|chunk)-[A-Za-z0-9]+\.js'
curl -s https://jupiter.err.ee/main-XXXXXXXX.js -o /tmp/main.js
grep -oE '/api/v?[0-9]?/?[A-Za-z0-9_/-]+' /tmp/main.js | sort -u
```

Some URLs are assembled from pieces (`"/api/" + type + "Schedule/" + method`),
so search for the method name too. Landmarks: `defaultSearchParams`,
`DEFAULT_DOMAIN_ID`, `getByUrl(`, `getContentPageData?contentId=`,
`getMenu(`. The bundle is one long line, so cut context out with Python
rather than `grep -o '.{0,200}'`. Parameters are where this API is easy to get
wrong, and the call site shows them.

URLs, ids and per-catalogue data (`DOMAINS`, including `section_fallbacks`)
live in `constants.py`; requests in `api.py`, one method per endpoint; parsing
in `menu.py`, `categories.py`, `content.py` and `schedule.py`. When ERR stops
listing something it still serves, fall back to it in data and keep reading
ERR's own list first, so Saturn follows ERR again if it changes back.

## 4. Add or change a route

Register a `Router` method in `ACTIONS` and follow AGENTS.md › Code style.
Every listing has this shape:

```python
def my_route(self):
    path = self.params.get('path', '')
    data = self._api('my route %s' % path, self.api.some_call, path)
    if data is None:
        return
    self.add_content_items(some_parser(data), self.section)
    self.finish(CONTENT_EPISODES, category=self.params.get('title', ''))
```

Titles ERR curated by hand go through `content.alphabetical()`; a listing
with an order of its own (episodes, a feed, a schedule) keeps it.

New text needs an id in both catalogues: 30000s navigation, 30100s settings,
30200s errors. A new navigation row needs a real PNG under
`resources/images/menu/`, registered in `C.MENU_ICONS`; skin textures such as
`DefaultFolder.png` do not load in Estuary's list views.

Test it in `tests/test_router.py`, named for what the user would have seen go
wrong:

```python
def test_my_route_lists_the_programmes_episodes(fake_api, series_fixture):
    instance = make_router(fake_api, {'action': 'myroute', 'id': '123'},
                           contents={'123': series_fixture['data']})
    instance.dispatch()
    assert labels() == [...]
    assert xbmcplugin.STATE['content'] == 'episodes'
```

## 5. Record the fixtures

```bash
.venv/bin/python tools/record_fixtures.py
```

It rewrites the fixtures it records from the live service, trimmed, picking
only DRM-free titles and redacting any token anyway. When a response changed shape, keep the old one as a
fixture of its own (`menu_audio_tab.json`) and test both, so Saturn still
works if ERR changes back. Read the diff before committing it.

## 6. Verify

```bash
./run-tests.sh
./run-tests.sh api
.venv/bin/python tools/survey_api.py
```

A change in what ERR offers needs a live test that would have caught it, as
`test_every_root_category_saturn_offers_has_titles` does. Streams and DRM are
proven only by a real player: play the change on a real device before tagging.
