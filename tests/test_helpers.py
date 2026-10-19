# SPDX-License-Identifier: GPL-3.0-or-later
import pytest

from resources.lib import helpers


@pytest.mark.parametrize('raw,expected', [
    ('//vod.err.ee/hls/vod/1/v/master.m3u8',
     'https://vod.err.ee/hls/vod/1/v/master.m3u8'),
    ('https://vod.err.ee/x.m3u8', 'https://vod.err.ee/x.m3u8'),
    ('http://vod.err.ee/x.m3u8', 'http://vod.err.ee/x.m3u8'),
    ('/subtitles/file/1/1.vtt',
     'https://services.err.ee/subtitles/file/1/1.vtt'),
    ('', ''),
    (None, ''),
])
def test_errs_relative_links_become_full_urls(raw, expected):
    assert helpers.absolutize(raw) == expected


def test_requests_and_streams_look_like_the_jupiter_website():
    headers = helpers.default_headers()
    assert headers['Referer'] == 'https://jupiter.err.ee/'
    assert 'Mozilla/5.0' in headers['User-Agent']
    encoded = helpers.stream_headers()
    assert 'Referer=https%3A%2F%2Fjupiter.err.ee%2F' in encoded
    assert 'User-Agent=' in encoded


@pytest.mark.parametrize('raw,expected', [
    ('<p>Hello <b>world</b></p>', 'Hello world'),
    ('a<br>b', 'a\nb'),
    ('a &amp; b&nbsp;c', 'a & b c'),
    ('&amp;&quot;&nbsp;', '&"'),
    ('', ''),
    (None, ''),
])
def test_descriptions_lose_their_html(raw, expected):
    assert helpers.strip_html(raw) == expected


def test_times_and_dates_read_as_kodi_expects():
    out = helpers.timestamp_to_human(1694694144, '%d.%m.%Y %H:%M')
    assert len(out) == 16 and out[2] == '.'
    assert helpers.timestamp_to_human(1694694144, '%Y-%m-%d').startswith(
        '2023-09-')
    for nothing in (0, None, 'nonsense'):
        assert helpers.timestamp_to_human(nothing, '%H:%M') == ''


def test_plugin_urls_drop_empty_values_and_ignore_argument_order():
    url = helpers.build_url('plugin://x/', action='play', id=42, empty='')
    assert url.startswith('plugin://x/?')
    assert 'action=play' in url and 'id=42' in url and 'empty' not in url
    assert helpers.build_url('plugin://x/') == 'plugin://x/'
    assert helpers.build_url('plugin://x/', b=2, a=1) == \
        helpers.build_url('plugin://x/', a=1, b=2)


SIZES = [{'photoTypes': {'8': {'url': '//s.err.ee/small.jpg'},
                         '69': {'url': '//s.err.ee/large.jpg'}}}]


@pytest.mark.parametrize('photos,wanted,expected', [
    (SIZES, ('69', '8'), 'https://s.err.ee/large.jpg'),
    (SIZES, ('8',), 'https://s.err.ee/small.jpg'),
    (SIZES, ('17',), ''),
    ([{'photoTypes': {}, 'photoUrlOriginal': '//s.err.ee/orig.jpg'}],
     ('69',), 'https://s.err.ee/orig.jpg'),
    ([], ('69',), ''),
])
def test_the_wanted_photo_size_is_picked(photos, wanted, expected):
    assert helpers.pick_photo(photos, wanted) == expected


def test_each_art_slot_gets_its_own_photo():
    art = helpers.extract_art({
        'photos': [{'photoTypes': {'17': {'url': '//s.err.ee/land.jpg'},
                                   '71': {'url': '//s.err.ee/fan.jpg'}}}],
        'verticalPhotos': [
            {'photoTypes': {'60': {'url': '//s.err.ee/pos.jpg'}}}],
        'squarePhotos': [{'photoTypes': {'44': {'url': '//s.err.ee/sq.jpg'}}}],
    })
    assert art['fanart'] == 'https://s.err.ee/fan.jpg'
    assert art['poster'] == 'https://s.err.ee/pos.jpg'
    assert art['icon'] == 'https://s.err.ee/sq.jpg'
    assert art['thumb'] == 'https://s.err.ee/land.jpg'


def test_a_poster_fills_the_other_art_slots_when_it_is_all_there_is():
    art = helpers.extract_art({'verticalPhotos': [
        {'photoTypes': {'60': {'url': '//s.err.ee/v.jpg'}}}]})
    assert art['thumb'] == art['poster'] == 'https://s.err.ee/v.jpg'
    assert helpers.extract_art({}) == {}


def test_a_number_from_err_survives_junk():
    assert helpers.safe_int('7') == 7
    assert helpers.safe_int(None) == 0
    assert helpers.safe_int('abc', 5) == 5


@pytest.mark.parametrize('titles,expected', [
    (['Õhtu', 'Zorro', 'Šokk', 'Tõde', 'Saag', 'Ärkamine', 'Wiki', 'Vaba',
      'Üle', 'Öö', 'Žürii'],
     ['Saag', 'Šokk', 'Zorro', 'Žürii', 'Tõde', 'Vaba', 'Wiki', 'Õhtu',
      'Ärkamine', 'Öö', 'Üle']),
    (['Osa 10', 'osa 2', 'Osa 1'], ['Osa 1', 'osa 2', 'Osa 10']),
    (['Kass', '„Elu“', 'Éclair', 'Draakon'],
     ['Draakon', 'Éclair', '„Elu“', 'Kass']),
])
def test_titles_sort_in_estonian_order(titles, expected):
    assert sorted(titles, key=helpers.sort_key) == expected
