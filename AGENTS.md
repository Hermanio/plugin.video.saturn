# AGENTS.md

Saturn is an unofficial Kodi add-on for ERR Jupiter (`jupiter.err.ee`), the
on-demand service of Estonian Public Broadcasting. Pure Python 3, no build
step, no runtime dependency beyond what `addon.xml` declares.

ERR publishes no API documentation and can change the service without notice.
`tests/fixtures/` holds recorded responses; `./run-tests.sh api` checks them
against the live service.

## Commands

Nothing to install by hand: the first `./run-tests.sh` creates `.venv` and
installs `tests/requirements.txt` into it.

```bash
./run-tests.sh          # static + unit          ~3s    no network
./run-tests.sh api      # live ERR API           ~30s   needs network
./run-tests.sh check    # Kodi add-on checker    ~70s   needs network
./run-tests.sh all      # every level, in order

./package.sh                                # build the zip into dist/
.venv/bin/python tools/record_fixtures.py   # re-record tests/fixtures
.venv/bin/python tools/survey_api.py        # what ERR changed
```

Run `./run-tests.sh` before claiming anything works: it takes three seconds
and catches documentation drift too. Playback, DRM above all, is proven only
in a real Kodi on a real device; do that by hand before a release.

## Architecture

Kodi calls `addon.py` for every `plugin://` request; it does nothing but call
`resources/lib/router.py:run()`, and everything else hangs off that.

| Module | Owns |
|--------|------|
| `constants.py` | URLs, ids, priority orders, icon maps. Data only, no logic |
| `helpers.py` | Pure utilities: URL building, artwork picking, HTML, time |
| `api.py` | `ErrApi`: one method per endpoint, no caching |
| `menu.py` | Navigation-tree parsing |
| `categories.py` | Category pages and the radio programme index |
| `content.py` | Content pages: metadata, seasons, stream and DRM selection |
| `schedule.py` | EPG parsing and catch-up detection |
| `kodiutils.py` | Every `xbmc*` call that is not a listing |
| `playqueue.py` | `ListItem` construction and `setResolvedUrl()` |
| `router.py` | URL dispatch; `Router.ACTIONS` is the route table |

Outside the add-on: `tests/` (every level behind `run-tests.sh`), `tools/`
(fixture recorder and survey) and `docs/screenshots/` (the README's); none
of them ship.

## Code style

- Standard library only, beyond what `addon.xml` declares; HTTP goes through
  `urllib`, as in VRT NU and InputStream Helper, so Saturn brings no copy of
  `requests` or `certifi` that Kodi's repository would have to keep current.
- PEP 8, 79 columns, four-space indent, single quotes, `%`-formatting. Every
  shipped file opens with `# -*- coding: utf-8 -*-` and
  `# SPDX-License-Identifier: GPL-3.0-or-later`; tests carry the SPDX line.
- **The code is the documentation.** The only `#` lines in shipped code,
  tests and tools are the coding and SPDX headers. Names carry the meaning.
  If a passage needs a comment to be followed, rename or split it. A service
  behaviour that forced the design goes in a fixture and a test.
- Kodi 21+ APIs only, since inputstream.adaptive 21.5 sets the floor:
  `InfoTagVideo` setters through `ku.apply_info()`, never `ListItem.setInfo()`;
  `xbmcaddon.Addon()`, never `Addon(id=...)`; settings through
  `Addon().getSettings()`, never the deprecated `Addon().getSetting*()`.
- User-visible text goes through `ku.localize(id, 'English fallback')`.
- In the router: build URLs with `self.url(...)`, wrap API calls in
  `self._api(...)`, end a listing with exactly one `self.finish(...)` or
  `self.fail(...)`. Playback actions belong in `PLAYBACK_ACTIONS` so an
  unhandled exception answers Kodi with a failed `setResolvedUrl` instead of
  leaving it waiting. Folders Saturn invents get
  `content.folder_metadata(parent, label)`, or Kodi draws "No information
  available" beside every one of them.

## Invariants the tests enforce

These are not style preferences. Breaking one fails `./run-tests.sh`.

- **The parsing layer imports nothing from Kodi.** `constants`, `helpers`,
  `api`, `menu`, `categories`, `content` and `schedule` stay importable in a
  plain Python process; only `kodiutils`, `playqueue` and `router` touch
  `xbmc*`. Checked by AST walk, so a function-scoped import does not dodge it.
- **The version lives in `addon.xml` and nowhere else.** The zip name, the git
  tag, the release title and `<news>` all derive from it. Never hardcode a
  version in the README.
- **Strings**: ids 30000–30299, defined in *both* catalogues. Every
  `ku.localize()` id must exist in both; every shipped id must be used. `en_gb`
  keeps `msgstr` empty (the msgid is the English text); `et_ee` must be fully
  translated, because an empty `msgstr` silently shows English.
- **Documentation is checked against the repository** by `tests/test_docs.py`:
  the README settings table against `settings.xml` plus the English
  catalogue, and `tests/README.md` against the test files it names. Add or
  rename a setting or a test file, update the docs in the same change.
- **Unit tests never touch the network.** Anything that reaches ERR is
  `@pytest.mark.integration`, packaging is `@pytest.mark.compliance`.
- **`resources/settings.xml` may never hold an `<option>` with an empty
  value.** Kodi's settings parser takes the whole process down on one; that is
  why "any" is spelled out rather than left blank.
- **The zip ships the add-on and nothing else.** `package.sh` copies only
  what its `SHIPPED` list names; a new file the add-on needs at runtime goes
  on that list and on the one in `test_packaging.py`.

## Testing

Outside Kodi there is no `xbmc` module: `tests/stubs/` fakes it and records
what the add-on did, and `conftest.FakeApi` stands in for `ErrApi`, so unit
tests never touch the network. [tests/README.md](tests/README.md) lists the
recorders and the helpers.

Put parsing tests in the module-shaped file (`test_content.py`, `test_menu.py`,
`test_live.py`) and route tests in `test_router.py`. A test's name says what
the user would have seen go wrong, not which function it calls.

`tests/fixtures/` holds real API responses, trimmed, and only of DRM-free
titles, so no licence token can be recorded; the recorder redacts any token
anyway, and `test_addon_xml.py` fails on one. DRM is tested with made-up
tokens, never against ERR's licence server. Re-record them with `tools/record_fixtures.py` in the same commit as
the code change that needed it.

## Procedures

Multi-file jobs have step-by-step skills in `.agents/skills/`:

- **`update`**: everything that changes what Saturn shows: checking ERR
  for changes with `tools/survey_api.py`, repairing the client when ERR moved
  or `./run-tests.sh api` fails, adding or changing a `plugin://` route with
  its strings, icon and test, and re-recording fixtures.

## Releasing

A release is a pushed `v<version>` tag; `.github/workflows/release.yml` does
the rest: fast tests, `./package.sh`, and a GitHub release titled
`Saturn <version>` carrying the zip, with `<news>` as its notes. A tag that
disagrees with `addon.xml` publishes nothing.

1. Bump `version` in `addon.xml`: a new capability is a minor bump, a fix a
   patch.
2. Rewrite `<news>` as `<version> - ` and one sentence on what changed for
   the user. Kodi shows it beside the update and the release uses it as its
   notes; `test_docs.py` checks the prefix.
3. Merge that to `main` and wait for the Tests workflow to pass on it.
4. `git tag v<version> && git push origin v<version>`, then `gh run watch`.

## Future improvements

Waiting on the owner's go-ahead; do not start these unprompted.

- A weekly scheduled `./run-tests.sh api` in CI, so ERR changes are caught
  between releases. GitHub's runners may be geo-blocked from some ERR
  endpoints; a self-hosted runner in Estonia would avoid that.

## Commits and pull requests

Until 1.0.0 is tagged the repository is one commit, `initial commit`, and
every fix is amended into it and force-pushed. After that, changes land on
`main` through pull requests.

A commit subject reads as prose and says
what changed for the user, not which files moved: *"Play radio as radio, and
give live television a cushion"*. Bodies explain the reasoning and record the
measurement when there was one.

**No trailers.** `Co-Authored-By:`, `Generated with:` and the like are banned
from commit messages and pull requests. A commit message is the reasoning
behind the change, not a record of what typed it.

Never commit `dist/`, `.venv/`, or a fixture carrying
a live DRM token.
