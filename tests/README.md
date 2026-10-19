# Testing Saturn

```bash
./run-tests.sh          # static + unit          ~3s     no network
./run-tests.sh api      # live ERR API           ~30s    needs network
./run-tests.sh check    # Kodi add-on checker    ~70s    needs network
./run-tests.sh all      # every level, in order
```

The first run creates `.venv` and installs `tests/requirements.txt`; it is
rebuilt when that file or the checkout's location changes.

## The levels

| Level | File(s) | Proves |
|-------|---------|--------|
| static | `test_addon_xml.py` | `addon.xml`, settings and `.po` files are well-formed and consistent, the code keeps its style rules, and no fixture carries a DRM token |
| docs | `test_docs.py` | The README and `<news>` match the repository; the release workflow publishes the zip with `<news>` as its notes, and nothing on a tag that disagrees with `addon.xml` |
| unit | `test_api.py`, `test_helpers.py`, `test_menu.py`, `test_content.py`, `test_live.py`, `test_playqueue.py`, `test_router.py`, `test_artwork.py` | Parsing and routing, driven by recorded fixtures |
| compliance | `test_packaging.py` | `package.sh` builds a zip the official Kodi checker passes |
| integration | `test_api_client.py` | The live ERR API still behaves the way Saturn expects |

Unit tests read `tests/fixtures/`, never the network, so they pass while
ERR is down. Playback in a real Kodi, DRM above all, is checked by hand on a
real device before a release; nothing here can stand in for Widevine.

## When a test fails

- **`./run-tests.sh`**: the bug is in the repository; nothing at this level
  depends on ERR.
- **`./run-tests.sh api`**: ERR has probably changed. Follow the `update`
  skill in `.agents/skills/`: fix the client, then re-record the fixtures with
  `.venv/bin/python tools/record_fixtures.py` in the same commit.
- **`./run-tests.sh check`**: the checker names the Kodi packaging rule that
  broke.

## Writing a test

Parsing tests go in the module-shaped file (`test_content.py`,
`test_menu.py`, `test_live.py`) and routes in `test_router.py`. Mark network
tests `@pytest.mark.integration`.

Outside Kodi there is no `xbmc` module, so `tests/stubs/` provides fakes that
`conftest.py` puts on `sys.path` before the add-on is imported. They record
what the add-on did, and an autouse fixture resets them between tests. It
fails a test whose ListItem Kodi would have dropped silently, that ends a
listing twice, or that fills a listing and never ends it.

| Recorder | Holds |
|----------|-------|
| `xbmcplugin.DIRECTORY` | Every row added: URL, ListItem, folder flag |
| `xbmcplugin.STATE` | Content type, plugin category, sort methods, how `endOfDirectory` was called |
| `xbmcplugin.RESOLVED` | Every `setResolvedUrl()` call |
| `xbmcgui.NOTIFICATIONS` | What the user was told |
| `xbmcgui.DIALOGS` | Every dialog opened, the search keyboard included |
| `xbmcgui.REJECTED_INFO` | Info labels Kodi would have dropped |
| `xbmcaddon.SETTINGS` | Write into it to make the add-on believe a setting |
| `xbmcgui.INPUT_TEXT[0]` | Scripts the search keyboard |

`conftest.FakeApi` stands in for `ErrApi`, and `make_router(fake_api, {...})`
in `test_router.py` builds a router wired to it. The `with_inputstreamhelper`
fixture puts `fake_inputstreamhelper.py` in place of the real module, for
tests that play a stream.
