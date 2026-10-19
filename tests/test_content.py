# SPDX-License-Identifier: GPL-3.0-or-later
import pytest
import xbmcgui

from resources.lib import categories, content


@pytest.fixture
def months(monthly_fixture):
    return content.season_list(monthly_fixture['data'])


def test_a_film_has_a_title_a_clean_plot_and_an_iso_date(movie):
    meta = content.extract_metadata(movie)
    assert meta['title'] == movie['heading']
    assert meta['studio'] == 'ERR'
    assert '<' not in meta['plot']
    assert len(meta['premiered']) == 10 and meta['premiered'][4] == '-'


def test_an_empty_page_still_says_where_it_came_from():
    assert content.extract_metadata({}) == {'studio': 'ERR',
                                            'mediatype': 'video'}


@pytest.mark.parametrize('content_type,media_type', [
    ('series', 'tvshow'), ('episode', 'episode'), ('movie', 'movie'),
    ('clip', 'video'), ('content', 'video'), (None, 'video'),
])
def test_every_media_type_is_one_kodi_accepts(content_type, media_type):
    assert content.media_type_for(content_type) == media_type
    assert media_type in xbmcgui.VIDEO_MEDIA_TYPES


def test_a_film_plays_its_hls_stream(movie):
    media = content.pick_media(movie)
    assert media['type'] == 'video'
    assert content.is_drm(media) is False
    url, protocol = content.select_stream(media)
    assert protocol == 'hls'
    assert url.startswith('https://vod.err.ee/hls/')


@pytest.mark.parametrize('media,expected', [
    ({'src': {'hls': '//a/hls.m3u8', 'hlsNew': '//a/new.m3u8',
              'dash': '//a/d.mpd'}}, ('https://a/new.m3u8', 'hls')),
    ({'restrictions': {'drm': True},
      'src': {'hls': '//a/hls.m3u8', 'dashNew': '//a/new.mpd'}},
     ('https://a/new.mpd', 'mpd')),
    ({'src': {'file': '//vod.err.ee/file/vod/1.mp4'}},
     ('https://vod.err.ee/file/vod/1.mp4', 'file')),
    ({}, ('', '')),
    ({'src': {}}, ('', '')),
])
def test_the_best_stream_is_chosen(media, expected):
    assert content.select_stream(media) == expected


def test_drm_and_geoblocking_are_read_from_the_restrictions():
    assert content.is_drm({'restrictions': {'drm': True}}) is True
    assert content.is_drm({}) is False
    assert content.is_geo_blocked({'restrictions': {'geoBlock': True}})
    assert not content.is_geo_blocked({'restrictions': {}})


GEO = {'restrictions': {'geoBlock': True}}


@pytest.mark.parametrize('medias,prefer_audio,expected', [
    ([dict(GEO, type='video', src='//a'), {'type': 'video', 'src': '//b'}],
     False, '//b'),
    ([dict(GEO, type='video', src='//a')], False, '//a'),
    ([{'type': 'video', 'src': '//v'}, {'type': 'audio', 'src': '//a'}],
     True, '//a'),
    ([{'type': 'video', 'src': '//v'}, {'type': 'audio', 'src': '//a'}],
     False, '//v'),
    ([], False, None),
])
def test_the_right_media_is_picked(medias, prefer_audio, expected):
    media = content.pick_media({'medias': medias}, prefer_audio=prefer_audio)
    assert (media or {}).get('src') == expected


SUBTITLES = {'subtitles': [
    {'srclang': 'VA', 'name': 'eesti', 'src': 'https://a/et.vtt'},
    {'srclang': 'RU', 'name': 'vene', 'src': 'https://a/ru.vtt'},
]}


@pytest.mark.parametrize('media,language,expected', [
    (SUBTITLES, 'ru', ['https://a/ru.vtt']),
    (SUBTITLES, 'va', ['https://a/et.vtt']),
    (SUBTITLES, None, ['https://a/et.vtt', 'https://a/ru.vtt']),
    (SUBTITLES, 'fr', ['https://a/et.vtt', 'https://a/ru.vtt']),
    ({}, None, []),
])
def test_the_preferred_subtitles_are_loaded(media, language, expected):
    assert content.subtitles_of(media, language) == expected


def test_a_films_subtitles_load_over_https(movie):
    subs = content.subtitles_of(content.pick_media(movie))
    assert subs and all(url.startswith('https://') for url in subs)


def test_a_drm_licence_needs_both_the_url_and_the_token():
    media = {'jwt': 'abc', 'licenseServerUrl': {
        'widevine': 'https://drm-widevine-licensing.axprod.net/AcquireLicense',
        'playReady': 'https://example.invalid/pr'}}
    assert content.drm_config(media) == {
        'token': 'abc', 'url': media['licenseServerUrl']['widevine']}
    assert content.drm_config({'jwt': 'abc'}) is None
    assert content.drm_config({'licenseServerUrl': {'widevine': 'u'}}) is None


def test_every_season_can_be_opened(series_fixture):
    seasons = content.season_list(series_fixture['data'])
    assert seasons
    for season in seasons:
        assert season['name']
        assert season['first_content_id'], \
            'a season without its own content id cannot be opened'
        assert season['children'] == []
        for episode in season['contents']:
            assert episode['id'] and episode['type'] == 'episode'
    assert content.season_list_type(series_fixture['data']) in (
        'seasonal', 'monthly', 'shortSeriesList')


def test_a_film_has_no_seasons(movie_fixture):
    assert content.season_list(movie_fixture['data']) == []


@pytest.mark.parametrize('item,label', [
    ({'heading': 'X', 'season': 2, 'episode': 3}, 'X (S02E03)'),
    ({'heading': 'X'}, 'X'),
    ({'id': 7}, '7'),
    ({'heading': 'Sherlock', 'subHeading': 'Etüüd roosas'},
     'Sherlock - Etüüd roosas'),
    ({'heading': 'Sherlock', 'subHeading': ''}, 'Sherlock'),
    ({'heading': 'X', 'subHeading': 'x'}, 'X'),
])
def test_a_row_is_labelled_once_and_numbered(item, label):
    assert content.label_for(item) == label


def test_a_categorys_rows_are_counted_and_indexed(category_fixture):
    blocks = categories.category_blocks(category_fixture['data']['category'])
    assert blocks
    for block in blocks:
        assert block['items']
        assert isinstance(block['index'], int)


def test_personal_and_live_rows_are_left_out():
    item = {'id': 1, 'heading': 'x', 'type': 'movie'}
    category = {'frontPage': [
        {'header': 'Jätka', 'userBasedTimeline': True, 'data': [item]},
        {'header': 'Otse', 'liveBlock': True, 'data': [item]},
        {'header': 'Eesti', 'data': [item]},
    ]}
    headers = [b['header'] for b in categories.category_blocks(category)]
    assert headers == ['Eesti']


def test_rows_say_whether_errs_editors_picked_them(category_fixture):
    category = category_fixture['data']['category']
    blocks = {b['header']: b for b in categories.category_blocks(category)}
    assert blocks['']['banner'] is True
    assert blocks['Eesti']['banner'] is False
    assert categories.block_at(category, blocks['Eesti']['index'])[1] is True
    assert categories.block_at(category, blocks['']['index'])[1] is False
    assert categories.block_at({'frontPage': [{'manual': True}]}, 0) == \
        ([], False)


def test_a_row_link_opens_that_row_or_nothing(category_fixture):
    category = category_fixture['data']['category']
    block = categories.category_blocks(category)[0]
    assert categories.block_at(category, block['index'])[0] == block['items']
    assert categories.block_at(category, 9999) == ([], False)
    assert categories.block_at({}, 0) == ([], False)


def test_all_lists_each_title_once(category_fixture):
    ids = [i['id'] for i in categories.flatten_items(
        category_fixture['data']['category'])]
    assert ids and len(ids) == len(set(ids))


def test_a_category_with_no_rows_lists_its_items():
    item = {'id': 1, 'heading': 'Lotte', 'type': 'movie'}
    category = {'frontPage': [], 'items': [item, dict(item, id=2)]}
    assert categories.category_blocks(category) == []
    assert [i['id'] for i in categories.flatten_items(category)] == [1, 2]


def test_items_are_ignored_when_rows_exist(category_fixture):
    category = dict(category_fixture['data']['category'])
    category['items'] = [{'id': 999999, 'heading': 'stray', 'type': 'movie'}]
    assert 999999 not in [i['id'] for i in categories.flatten_items(category)]


def test_a_monthly_programme_has_years_of_months_of_episodes(
        monthly_fixture, months):
    assert content.season_list_type(monthly_fixture['data']) == 'monthly'
    assert months and all(year['contents'] == [] for year in months)
    children = [m for year in months for m in year['children']]
    assert children
    for month in children:
        assert month['name'] and month['first_content_id']
    episodes = [e for month in children for e in month['contents']]
    assert episodes and all(e['id'] for e in episodes)


def test_a_year_or_a_month_can_be_found_by_its_link(months):
    year = months[0]
    month = year['children'][0]
    assert content.find_season(months, year['id']) is year
    assert content.find_season(months, year['id'], month['id']) is month
    assert content.find_season(months, year['id'], 'nope') is None
    assert content.find_season(months, 'nope') is None


@pytest.mark.parametrize('item,expected,absent', [
    ({'heading': 'Libahunt', 'subHeading': 'Tammsaare ainetel',
      'type': 'movie'},
     {'plot': 'Tammsaare ainetel', 'plotoutline': 'Tammsaare ainetel'}, ()),
    ({'heading': 'Riigimehed', 'subHeading': 'Piloot', 'type': 'episode'},
     {'title': 'Piloot'}, ('plot', 'plotoutline')),
    ({'heading': 'Film', 'lead': 'Same words.', 'subHeading': 'Same words.',
      'type': 'movie'}, {'plot': 'Same words.'}, ()),
])
def test_a_sub_heading_describes_a_row_only_when_it_adds_something(
        item, expected, absent):
    meta = content.extract_metadata(item)
    for key, value in expected.items():
        assert meta[key] == value, key
    for key in absent:
        assert key not in meta, key


def test_a_sub_heading_does_not_displace_a_real_description():
    meta = content.extract_metadata({
        'heading': 'Film', 'lead': 'A short lead.',
        'body': '<p>The full synopsis.</p>', 'subHeading': 'Extra line',
        'type': 'movie'})
    assert meta['plotoutline'] == 'A short lead.'
    assert meta['plot'].startswith('A short lead.')
    assert 'The full synopsis.' in meta['plot']
    assert meta['plot'].endswith('Extra line')


RIIGIMEHED_EPISODE = {
    'heading': 'Riigimehed', 'subHeading': 'Piloot', 'type': 'episode',
    'season': 1, 'episode': 1, 'year': '2010', 'publicStart': 1598529600,
    'makers': [
        {'typeId': 8, 'type': 'Näitlejad', 'name': 'Ott Sepp'},
        {'typeId': 8, 'type': 'Näitlejad', 'name': 'Jaak Prints'},
        {'typeId': 10, 'type': 'Režissöör', 'name': 'Tammo Sumera'},
        {'typeId': 18, 'type': 'Stsenarist', 'name': 'Martin Algus'},
        {'typeId': 17, 'type': 'Produtsent', 'name': 'Andres Arro'},
    ],
}


@pytest.mark.parametrize('item,title,show', [
    (RIIGIMEHED_EPISODE, 'Piloot', 'Riigimehed'),
    ({'heading': 'Riigimehed | Piloot | 1. hooaeg, 1. osa',
      'subHeading': 'Piloot', 'type': 'episode'}, 'Piloot', 'Riigimehed'),
    ({'heading': 'Da Vinci kood', 'type': 'movie'}, 'Da Vinci kood', None),
    ({'heading': 'Aktuaalne kaamera', 'type': 'episode'},
     'Aktuaalne kaamera', None),
])
def test_an_episode_is_titled_by_itself_under_its_programme(item, title,
                                                            show):
    meta = content.extract_metadata(item)
    assert meta['title'] == title
    assert meta.get('tvshowtitle') == show


def test_makers_are_filed_under_the_job_they_did():
    meta = content.extract_metadata(RIIGIMEHED_EPISODE)
    assert meta['director'] == ['Tammo Sumera']
    assert meta['writer'] == ['Martin Algus']
    assert meta['cast'] == ['Ott Sepp', 'Jaak Prints']
    assert content.credits_of({'makers': ['nonsense', {'name': ''}]}) == {
        'director': [], 'writer': [], 'cast': []}


def test_an_episode_is_dated_by_when_it_aired():
    meta = content.extract_metadata(RIIGIMEHED_EPISODE)
    assert meta['aired'] == meta['premiered'] == '2020-08-27'
    assert meta['year'] == 2020


def test_a_film_keeps_its_production_year():
    meta = content.extract_metadata({
        'heading': 'Da Vinci kood', 'type': 'movie', 'year': '2006',
        'publicStart': 1788000000})
    assert meta['year'] == 2006
    assert meta['premiered'].startswith('2026-')


def test_a_listing_row_inherits_the_programmes_description():
    parent = content.extract_metadata({
        'heading': 'Riigimehed', 'type': 'series',
        'lead': 'Huumorisari kusib.',
        'primaryCategory': {'name': 'Komoodia'},
        'makers': [{'typeId': 10, 'name': 'Kaaren Kaer'},
                   {'typeId': 8, 'name': 'Ott Sepp'}],
    })
    row = content.extract_metadata({
        'heading': 'Riigimehed', 'subHeading': 'Piloot', 'type': 'episode',
        'season': 1, 'episode': 1,
    }, parent)
    assert row['title'] == 'Piloot'
    assert row['plot'] == 'Huumorisari kusib.'
    assert 'plotoutline' not in row
    assert row['genre'] == 'Komoodia'
    assert row['cast'] == ['Ott Sepp']
    assert row['director'] == ['Kaaren Kaer']


def test_inheriting_never_overwrites_what_the_row_already_says():
    parent = content.extract_metadata({
        'heading': 'Programme', 'type': 'series', 'lead': 'Series blurb.',
        'makers': [{'typeId': 10, 'name': 'Series Director'}],
    })
    row = content.extract_metadata({
        'heading': 'Programme', 'subHeading': 'Episode', 'type': 'episode',
        'body': 'The episode has its own synopsis.',
        'makers': [{'typeId': 10, 'name': 'Episode Director'}],
    }, parent)
    assert row['director'] == ['Episode Director']
    assert row['plot'].startswith('The episode has its own synopsis.')
    assert 'Series blurb.' in row['plot']


def test_the_programme_blurb_is_not_repeated():
    parent = content.extract_metadata({'heading': 'P', 'type': 'series',
                                       'lead': 'Same blurb.'})
    row = content.extract_metadata({'heading': 'P', 'subHeading': 'E',
                                    'type': 'episode',
                                    'lead': 'Same blurb.'}, parent)
    assert row['plot'].count('Same blurb.') == 1


@pytest.mark.parametrize('items,expected', [
    ([{'id': 3, 'season': 10, 'episode': 27},
      {'id': 2, 'season': 10, 'episode': 26},
      {'id': 1, 'season': 10, 'episode': 15}], [1, 2, 3]),
    ([{'id': 2, 'publicStart': 200}, {'id': 1, 'publicStart': 100}], [1, 2]),
    ([{'id': 2}, {'id': 1}], [2, 1]),
])
def test_episodes_are_listed_oldest_first_when_they_can_be(items, expected):
    assert [i['id'] for i in content.order_contents(items)] == expected


@pytest.mark.parametrize('names,expected', [
    (['september', 'august', 'juuli'], ['juuli', 'august', 'september']),
    (['2026', '2025', '2024'], ['2024', '2025', '2026']),
    (['Uus', 'Vana'], ['Uus', 'Vana']),
])
def test_years_and_months_are_listed_oldest_first(names, expected):
    entries = [{'name': name} for name in names]
    assert [e['name'] for e in content.order_seasons(entries)] == expected


def test_months_come_back_in_playing_order(monthly_fixture, months):
    raw = [item['name'] for item in
           monthly_fixture['data']['seasonList']['items'][0]['items']]
    names = [child['name'] for child in months[0]['children']]
    assert names == sorted(raw, key=content.MONTHS_ET.index)
    assert names != raw, 'the fixture was already in order; nothing proven'


def test_all_seasons_plays_the_entries_that_hold_episodes(months):
    leaves = content.leaf_seasons(months)
    assert leaves and all(not leaf['children'] for _a, leaf in leaves)
    assert [leaf['name'] for _a, leaf in leaves] == \
        [child['name'] for child in months[0]['children']]
    for address, leaf in leaves:
        assert content.find_season(months, *address) is leaf
    assert content.leaf_seasons(months, scope=months[0]['id']) == leaves
    assert content.leaf_seasons(months, scope='no-such-year') == []


def test_a_folder_saturn_invents_carries_the_programmes_description():
    parent = {'title': 'Sherlock', 'plot': 'Detective', 'genre': 'Draama',
              'season': 1, 'episode': 3, 'mediatype': 'episode'}
    meta = content.folder_metadata(parent, 'Season 2', season=2)
    assert meta['title'] == 'Season 2'
    assert meta['plot'] == 'Detective' and meta['genre'] == 'Draama'
    assert meta['season'] == 2
    assert 'episode' not in meta
    assert content.folder_metadata({}, 'Season 2') == {}
