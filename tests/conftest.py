# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import sys

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ADDON_DIR = os.path.dirname(TESTS_DIR)
STUBS_DIR = os.path.join(TESTS_DIR, 'stubs')
FIXTURES_DIR = os.path.join(TESTS_DIR, 'fixtures')

for path in (STUBS_DIR, ADDON_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)


def load_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name), encoding='utf-8') as handle:
        return json.load(handle)


def fixture_file(filename):
    return pytest.fixture(lambda: load_fixture(filename))


menu_fixture = fixture_file('menu.json')
audio_tab_menu_fixture = fixture_file('menu_audio_tab.json')
radio_fixture = fixture_file('radio_programmes.json')
category_fixture = fixture_file('category_filmid.json')
movie_fixture = fixture_file('content_movie.json')
series_fixture = fixture_file('content_series.json')
monthly_fixture = fixture_file('content_monthly.json')
audio_fixture = fixture_file('content_audio.json')
search_fixture = fixture_file('search_video.json')
live_tv_fixture = fixture_file('live_etv.json')
live_radio_fixture = fixture_file('live_vikerraadio.json')
schedule_fixture = fixture_file('schedule_etv.json')


@pytest.fixture
def movie(movie_fixture):
    return movie_fixture['data']['mainContent']


@pytest.fixture(autouse=True)
def clean_kodi_state():
    import xbmcgui
    import xbmcplugin
    import xbmcaddon
    xbmcgui.reset()
    xbmcplugin.reset()
    xbmcaddon.reset()
    yield
    rejected = list(xbmcgui.REJECTED_INFO)
    end_calls = xbmcplugin.STATE['end_calls']
    left_spinning = bool(xbmcplugin.DIRECTORY) and not xbmcplugin.RESOLVED \
        and end_calls == 0
    xbmcgui.reset()
    xbmcplugin.reset()
    assert not rejected, 'Kodi would drop these silently: %s' % rejected
    assert end_calls <= 1, 'endOfDirectory called %d times' % end_calls
    assert not left_spinning, 'a listing never called endOfDirectory'


class FakeApi:
    def __init__(self, menu=None, category=None, contents=None, search=None,
                 live=None, radio=None, schedule=None):
        self.menu = menu or []
        self.category = category or {}
        self.contents = contents or {}
        self.search_result = search or {'contents': [], 'limit': 50}
        self.live = live or {}
        self.radio = radio or []
        self.schedule = schedule or []
        self.calls = []
        self.root_id = 3905

    def get_menu(self):
        self.calls.append(('menu',))
        return self.menu

    def get_category(self, url):
        self.calls.append(('category', url))
        return self.category

    def get_content(self, content_id, root_id=None):
        self.calls.append(('content', str(content_id), root_id))
        return self.contents[str(content_id)]

    def search_all(self, **kwargs):
        self.calls.append(('search_all', kwargs))
        result = dict(self.search_result)
        result.setdefault('has_more', len(result.get('contents') or [])
                          >= result.get('limit', 0))
        return result

    def get_live_media(self, channel_name):
        self.calls.append(('live', channel_name))
        return self.live

    def get_radio_programmes(self, station_id):
        self.calls.append(('radio', station_id))
        return self.radio

    def get_schedule(self, channel, when, kind='tv'):
        self.calls.append(('schedule', channel, str(when), kind))
        return self.schedule


@pytest.fixture
def fake_api():
    return FakeApi


@pytest.fixture
def with_inputstreamhelper():
    from . import fake_inputstreamhelper

    fake_inputstreamhelper.reset()
    sys.modules['inputstreamhelper'] = fake_inputstreamhelper
    yield fake_inputstreamhelper
    fake_inputstreamhelper.reset()
    sys.modules.pop('inputstreamhelper', None)
