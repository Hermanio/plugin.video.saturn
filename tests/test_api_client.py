# SPDX-License-Identifier: GPL-3.0-or-later
import datetime
from urllib.parse import urljoin

import pytest
import requests

from resources.lib import categories, content, menu, schedule
from resources.lib import constants as C
from resources.lib.api import ApiError, ErrApi
from resources.lib.helpers import absolutize, default_headers, extract_art

pytestmark = pytest.mark.integration

YESTERDAY = datetime.date.today() - datetime.timedelta(days=1)


@pytest.fixture(scope='module')
def api():
    return ErrApi(log=lambda m: None)


def first_plain_film(api):
    for item in categories.flatten_items(api.get_category('filmid')):
        if item.get('type') != 'movie':
            continue
        main = api.get_content(item['id']).get('mainContent') or {}
        media = content.pick_media(main)
        if media is not None and not content.is_drm(media):
            return main, media
    return None


@pytest.fixture(scope='module')
def movie_content(api):
    found = first_plain_film(api)
    if found is None or content.select_stream(found[1])[1] != 'hls':
        pytest.fail('no DRM-free film with an HLS stream: the shape changed')
    return found[0]


def get(url, **kwargs):
    return requests.get(url, headers=default_headers(), timeout=30, **kwargs)


def test_every_catalogue_has_a_menu(api):
    items = api.get_menu()
    names = {item['name'] for item in items}
    assert {'Video', 'Audio'} <= names
    assert [i for i in items if i['name'] == 'Video'][0]['kids']
    for key in C.DOMAINS:
        sections = ErrApi(domain=key, log=lambda m: None).get_menu()
        assert sections and all(s.get('name') for s in sections), key


def test_a_category_has_rows_of_titles(api):
    category = api.get_category('filmid')
    assert category['id'] and category['name']
    assert any(block.get('data') for block in category['frontPage'])


def test_every_root_category_saturn_offers_has_titles(api):
    fallbacks = C.DOMAINS['jupiter']['section_fallbacks']
    entries = menu.flat_entries(api.get_menu(), fallbacks)
    assert {'muusika', 'audio', 'filmid', 'sarjad'} <= \
        {entry['path'] for entry in entries}
    for entry in entries:
        assert categories.flatten_items(api.get_category(entry['path'])), \
            entry['path']
    kids = ErrApi(domain='lasteekraan', log=lambda m: None)
    assert categories.flatten_items(
        kids.get_category(C.DOMAINS['lasteekraan']['path']))


def test_a_films_streams_and_art_are_on_errs_https_hosts(movie_content):
    src = movie_content['medias'][0]['src']
    for key, value in src.items():
        if isinstance(value, str) and 'err.ee' in value:
            assert absolutize(value).startswith('https://'), key
    art = extract_art(movie_content)
    assert art and all(url.startswith('https://') for url in art.values())
    assert requests.get(list(art.values())[0], timeout=30).status_code == 200


def test_a_film_plays_from_master_to_segment(movie_content):
    master_url, protocol = content.select_stream(
        content.pick_media(movie_content))
    assert protocol == 'hls'
    master = get(master_url)
    assert master.status_code == 200
    assert '#EXT-X-STREAM-INF' in master.text
    variants = [line.strip() for line in master.text.splitlines()
                if line.strip() and not line.startswith('#')]
    variant_url = urljoin(master_url, variants[0])
    variant = get(variant_url)
    assert variant.status_code == 200 and '#EXTINF' in variant.text
    segment_uri = next(line.strip() for line in variant.text.splitlines()
                       if line.strip() and not line.startswith('#'))
    segment = requests.get(urljoin(variant_url, segment_uri),
                           headers=default_headers(), timeout=60)
    assert segment.status_code == 200
    assert len(segment.content) > 10000


def test_search_finds_a_title_by_name(api, movie_content):
    phrase = movie_content['heading'].split(':')[0].strip()
    result = api.search_all(phrase=phrase, limit=10)
    headings = ' '.join(i['heading'] for i in result['contents']).lower()
    assert phrase.lower() in headings


def test_search_pages_through_the_catalogue(api):
    first = api.search_all(phrase='', page=1, limit=5)
    second = api.search_all(phrase='', page=2, limit=5)
    assert first['has_more']
    assert {i['id'] for i in first['contents']} != \
        {i['id'] for i in second['contents']}


def test_an_audio_search_hit_opens_under_the_audio_root(api):
    hits = [i for i in api.search_all(phrase='', limit=20)['contents']
            if i.get('rootCategoryId') != C.SEARCH_ROOT_ID]
    assert hits, 'search returned no audio'
    page = api.get_content(hits[0]['id'], C.AUDIO_ROOT_ID)
    assert page['mainContent']['id'] == hits[0]['id']


def test_unknown_content_and_channels_raise(api):
    with pytest.raises(ApiError):
        api.get_content(999999999999, 3905)
    with pytest.raises(ApiError):
        api.get_live_media('nosuchchannel')


def test_every_live_channel_streams(api):
    for name, _label in C.LIVE_TV + C.LIVE_RADIO:
        payload = api.get_live_media(name)
        assert payload['src'] and payload['nameId'] == name, name
    for channel in ('etv', 'vikerraadio'):
        url = absolutize(api.get_live_media(channel)['src'])
        response = get(url)
        assert response.status_code == 200, channel
        assert '#EXTM3U' in response.text


def test_every_tv_channel_offers_a_widevine_stream_saturn_can_open(api):
    for name, _label in C.LIVE_TV:
        drm = content.live_drm(api.get_live_media(name), '12345678901234')
        assert drm, name
        response = get(drm['manifest'])
        assert response.status_code == 200, name
        assert 'edef8ba9' in response.text.lower(), name


def test_yesterdays_schedules_list_programmes(api):
    assert schedule.parse_schedule(api.get_schedule('etv', YESTERDAY))
    assert api.get_schedule('vikerraadio', YESTERDAY, kind='radio')


def test_yesterdays_catch_up_plays(api):
    playable = [p for p in schedule.parse_schedule(
        api.get_schedule('etv', YESTERDAY)) if schedule.is_playable(p)]
    if not playable:
        pytest.skip('no catch-up entries yesterday')
    page = api.get_content(playable[0]['content_id'])
    url, protocol = content.select_stream(
        content.pick_media(page['mainContent']))
    assert url.startswith('https://')
    assert protocol in ('hls', 'mpd', 'file')


def test_every_radio_station_lists_programmes_that_open(api):
    for name, station_id in C.RADIO_STATION_IDS.items():
        programmes = categories.radio_programmes(
            api.get_radio_programmes(station_id))
        assert programmes, name
        page = api.get_content(programmes[0]['id'], C.AUDIO_ROOT_ID)
        assert page['mainContent'], name


def test_search_reaches_lasteekraan_and_its_hits_open(api):
    hits = [item for item in api.search_all(phrase='lotte', limit=20)
            ['contents'] if 'lasteekraan.err.ee' in
            (item.get('canonicalUrl') or '')]
    assert hits, 'search no longer covers Lasteekraan'
    page = api.get_content(hits[0]['id'])
    assert content.pick_media(page['mainContent'])
