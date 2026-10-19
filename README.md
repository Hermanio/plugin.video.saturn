# Saturn

**A Kodi add-on for watching and listening to ERR Jupiter.**

> **Unofficial.** Not affiliated with, endorsed by or supported by Eesti
> Rahvusringhääling. It uses the same public API as the jupiter.err.ee
> website, which can change without notice and break Saturn until it is
> fixed. Most content is only available inside Estonia.

[Jupiter](https://jupiter.err.ee) is the on-demand service of Estonian
Public Broadcasting: films, series, documentaries, sport, children's
programmes, radio and radio theatre, plus live TV and radio. Saturn puts
it in Kodi, so it can be browsed and played with a remote instead of a
browser.

*Mitteametlik Kodi lisa ERR Jupiteri vaatamiseks ja kuulamiseks.*

## What it does

- **One root menu**: search, TV, radio, every Jupiter category (Filmid,
  Sarjad, Saated, Sport, Io, Raadioteater, Muusika …) and Lasteekraan.
- **Categories as rows**, as on the website (*Eesti*, *Euroopa kino*,
  *Dokumentaal* …), plus **All**. Rows ERR's editors pick and **All** are
  sorted A–Z in Estonian order; rows ERR fills itself (latest episodes,
  *Viimati lisatud*, *Peagi aeguvad*) keep ERR's newest-first order.
  Kodi's **Sort by** menu re-sorts any listing by name or air date, and
  episodes by number.
- **Series in watching order**: seasons and episodes oldest first, and an
  **All seasons** row that plays a whole series through.
- **Search** across video, audio and Lasteekraan at once.
- **Live TV and radio**: ETV, ETV2, ETV+ and the five ERR radio stations, with
  each channel's schedule and **catch-up** of programmes that have aired.
- **Radio programmes A–Z** for each station, about 700 in all.
- **DRM titles** through Widevine, and subtitles.
- Posters, plots, air dates, cast, director and writer.
- **English and Estonian**, following Kodi's interface language.

ERR flags some programmes as restricted for online streaming. Saturn ignores
the flag and requests the stream anyway; if ERR refuses it, playback fails as
for any unavailable stream.

Saturn does not sign in to an ERR account (no watch history, favourites,
*Jätka* or recommendations), download anything, or add titles to Kodi's
library.

## How it works

1. **Browse.** Every listing is one request to ERR's API at
   `services.err.ee`, the one the website uses: the navigation menu,
   category pages, content pages, search, and the TV and radio schedules.
   Nothing is cached between requests.
2. **Pick a stream.** A title's media is read for its sources, and
   `inputstream.adaptive` plays them: HLS for plain titles, DASH for DRM
   titles, with the Widevine licence server and token ERR hands out for
   that title. Live TV plays ERR's Widevine stream, as the website does,
   because ERR shuts its open stream off during programmes it may only
   show protected; without Widevine it falls back to the open stream.
   Live radio plays in Kodi's own player.
3. **Widevine.** `script.module.inputstreamhelper` checks for
   `inputstream.adaptive` and the Widevine CDM before the first DRM title,
   and offers to install the CDM when it is missing.
4. **Catch-up.** In a channel's schedule, a programme that has aired and
   that ERR keeps on Jupiter is playable; picking it opens that Jupiter
   title rather than the live stream.

## Requirements

- Kodi 21 (Omega) or newer, on any platform.
- `inputstream.adaptive` 21.5.0 or newer and
  `script.module.inputstreamhelper`. Kodi installs both from its official
  repository, LibreELEC included; see below for desktop Linux.
- A connection from Estonia for most content.

## Installing

1. Download `plugin.video.saturn-<version>.zip` from the
   [latest release](https://github.com/Hermanio/plugin.video.saturn/releases/latest).
2. In Kodi, enable **Settings → System → Add-ons → Unknown sources**.
3. **Add-ons → Install from zip file**, pick the zip. Kodi installs the
   dependencies, and Saturn appears under **Video add-ons** and
   **Music add-ons**.

There are no automatic updates. To update, install a newer zip the same
way; Kodi replaces the old version.

A Linux distribution's own Kodi cannot fetch `inputstream.adaptive`, because
the official Kodi repository has no Linux builds of it. Install the
distribution's package first (`kodi-inputstream-adaptive` on Debian and
Ubuntu, `kodi-addon-inputstream-adaptive` on Arch), then the zip.

The first DRM title you play asks to install the **Widevine CDM** and shows
Google's licence. Accept both, once; without them only DRM titles fail.

### If a DRM title closes Kodi

DRM playback runs Google's Widevine library inside Kodi, through
`inputstream.adaptive`. When that pair does not suit the system, Kodi closes
as the title starts. Use the `inputstream.adaptive` built for your Kodi
version (21.x for Kodi 21 Omega): your distribution's package on desktop
Linux, as above, or your platform's official repository elsewhere. Remove
any copy installed from another add-on repository.

Films and series without DRM and radio are not affected.

## Settings

| Setting | Default | What it does |
|---------|---------|--------------|
| Load subtitles | On | Attach subtitle tracks to streams |
| Preferred subtitle language | Any | Attach only this language's subtitles, when there are any |
| Load artwork | On | Turn off on slow connections |

## Reporting a problem

Open an issue at <https://github.com/Hermanio/plugin.video.saturn/issues>.
Say what you opened (the jupiter.err.ee link of the title, or the menu path
in Kodi), what happened (an error, an empty listing, playback that failed or
closed Kodi), and whether it plays on jupiter.err.ee in a browser from the
same place. Then paste the output of this, run on the Kodi machine (over SSH
on LibreELEC):

```sh
{
grep -m1 'Starting Kodi' ~/.kodi/temp/kodi.log
grep -m1 'Platform:' ~/.kodi/temp/kodi.log
grep -E 'plugin\.video\.saturn|inputstream|Widevine' ~/.kodi/temp/kodi.log | tail -40
} 2>&1
```

It prints the Kodi version, the platform, and Saturn's and
`inputstream.adaptive`'s log lines. If Kodi closed, use `kodi.old.log`
instead, which holds the session that ended. On Windows the log is
`%APPDATA%\Kodi\kodi.log`; on Android, find it under
**Settings → System → Logging**. A log can carry the address of your Kodi
machine on the network; remove anything that looks private before posting.

## Development

```bash
./run-tests.sh                             # static + unit tests, no network (~3s)
./run-tests.sh api                         # the live ERR API (~30s)
./run-tests.sh check                       # build the zip, run kodi-addon-checker
./package.sh                               # build dist/plugin.video.saturn-<version>.zip
.venv/bin/python tools/record_fixtures.py  # re-record tests/fixtures from ERR
.venv/bin/python tools/survey_api.py       # report what ERR changed
```

The unit tests run against ERR responses recorded in `tests/fixtures/`, so
they pass while ERR is down; `api` checks those recordings against the live
service. [tests/README.md](tests/README.md) explains each level.

To release, bump `version` and `<news>` in `addon.xml`, then push a tag
`v<version>`. GitHub Actions runs the tests, builds the zip and publishes it
as a release.

This add-on was written with the help of LLM-based coding tools and checked
against real hardware.

## Licence

GPL-3.0-or-later. See [LICENSE](LICENSE).
