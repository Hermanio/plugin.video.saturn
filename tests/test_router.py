# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import time
from urllib.parse import parse_qsl, urlparse

import pytest
import xbmcaddon
import xbmcgui
import xbmcplugin

from resources.lib import categories
from resources.lib import constants as C
from resources.lib import content as content_mod
from resources.lib import router as router_mod
from resources.lib.api import ApiError
from resources.lib.helpers import sort_key

BASE = 'plugin://plugin.video.saturn/'
HANDLE = 3


def make_router(fake_api_cls, params, **api_kwargs):
    instance = router_mod.Router(BASE, HANDLE, params)
    instance._api_client = fake_api_cls(**api_kwargs)
    return instance


def route(fake_api_cls, params, **api_kwargs):
    instance = make_router(fake_api_cls, params, **api_kwargs)
    instance.dispatch()
    return instance


def route_page(fake_api_cls, page, action, **params):
    content_id = str(page['mainContent']['id'])
    return route(fake_api_cls, dict(params, action=action, id=content_id),
                 contents={content_id: page})


def route_category(fake_api_cls, category, action, **params):
    return route(fake_api_cls, dict({'action': action, 'path': 'filmid'},
                                    **params), category=category)


def raising(exc):
    def boom(*_args, **_kwargs):
        raise exc
    return boom


def urls():
    return [entry['url'] for entry in xbmcplugin.DIRECTORY]


def labels():
    return [entry['listitem'].label for entry in xbmcplugin.DIRECTORY]


def actions():
    return [params_of(url).get('action') for url in urls()]


def params_of(url):
    return dict(parse_qsl(urlparse(url).query))


def find_entry(needle):
    for entry in xbmcplugin.DIRECTORY:
        if needle in entry['url']:
            return entry
    return None


def all_count():
    label = find_entry('action=all')['listitem'].label
    return int(label.rsplit('(', 1)[1].rstrip(')'))


def search_calls(instance):
    return [call[1] for call in instance.api.calls if call[0] == 'search_all']


def ended_ok():
    return xbmcplugin.STATE['ended']['succeeded'] is True


def row_with_an_info_page():
    return {'frontPage': [{'header': 'Row', 'data': [
        {'id': 1, 'heading': 'real', 'type': 'movie'},
        {'id': 2, 'heading': 'info page', 'type': 'info'},
    ]}]}


def test_root_leads_with_search_tv_and_radio_then_every_category(
        fake_api, menu_fixture):
    route(fake_api, {}, menu=menu_fixture['data']['items'])
    found = labels()
    assert found[:3] == ['Search', 'TV', 'Radio']
    assert 'Video' not in found and 'Audio' not in found
    assert 'Otse' not in found
    for name in ('Sarjad', 'Filmid', 'Muusika', 'Saated (Audio)'):
        assert name in found, name
    assert found[-1] == 'Lasteekraan'
    assert ended_ok()
    assert actions()[0] == 'search'
    assert [params_of(u).get('kind') for u in urls()[1:3]] == ['tv', 'radio']
    assert params_of(find_entry('path=muusika')['url'])['section'] == 'Audio'
    kids = params_of(find_entry('domain=lasteekraan')['url'])
    assert (kids['action'], kids['path']) == ('category', 'vaata-ja-kuula')


def test_root_icons_are_real_files_that_tell_rows_apart(fake_api,
                                                        menu_fixture):
    route(fake_api, {}, menu=menu_fixture['data']['items'])
    icons = {e['listitem'].label: e['listitem'].art.get('icon') or ''
             for e in xbmcplugin.DIRECTORY}
    for label, icon in icons.items():
        assert os.path.isfile(icon), (label, icon)
    names = {label: os.path.basename(icon) for label, icon in icons.items()}
    assert names['Search'] == 'search.png'
    assert names['TV'] == 'tv.png'
    assert names['Radio'] == 'radio.png'
    assert names['Filmid'] == 'movies.png'
    assert names['Sarjad'] == 'series.png'
    assert names['Muusika'] == 'music.png'
    assert len(set(names.values())) > 4


@pytest.mark.parametrize('params,method,exc', [
    ({}, 'get_menu', ApiError('down')),
    ({}, 'get_menu', RuntimeError('unexpected')),
    ({'action': 'epg', 'channel': 'etv'}, 'get_schedule', ApiError('down')),
    ({'action': 'radioprogrammes', 'station': '404'}, 'get_radio_programmes',
     ApiError('down')),
])
def test_a_listing_that_fails_tells_the_user_and_ends(fake_api, params,
                                                      method, exc):
    instance = make_router(fake_api, params)
    setattr(instance.api, method, raising(exc))
    instance.dispatch()
    assert xbmcplugin.STATE['ended']['succeeded'] is False
    assert xbmcgui.NOTIFICATIONS[0]['icon'] == xbmcgui.NOTIFICATION_ERROR


def test_an_unknown_action_fails_instead_of_hanging(fake_api):
    route(fake_api, {'action': 'nonsense'})
    assert xbmcplugin.STATE['ended']['succeeded'] is False


@pytest.mark.parametrize('action,method,exc', [
    ('play', 'get_content', ApiError('nope')),
    ('play', 'get_content', RuntimeError('kaboom')),
    ('playlive', 'get_live_media', ApiError('no such channel')),
])
def test_playback_that_fails_answers_kodi_instead_of_hanging(
        fake_api, action, method, exc):
    instance = make_router(fake_api, {'action': action, 'id': '1',
                                      'channel': 'nope'})
    setattr(instance.api, method, raising(exc))
    instance.dispatch()
    assert xbmcplugin.RESOLVED[0]['succeeded'] is False


@pytest.mark.parametrize('action,method,exc,message', [
    ('', 'get_menu', RuntimeError('unexpected'), 'see the Kodi log'),
    ('play', 'get_content', RuntimeError('kaboom'), 'see the Kodi log'),
    ('play', 'get_content', ApiError('down'), 'ERR API'),
])
def test_only_a_network_failure_is_blamed_on_err(
        fake_api, action, method, exc, message):
    instance = make_router(fake_api, {'action': action, 'id': '1'})
    setattr(instance.api, method, raising(exc))
    instance.dispatch()
    assert message in xbmcgui.NOTIFICATIONS[0]['message']


def test_a_schedule_row_without_a_recording_answers_kodi(fake_api):
    route(fake_api, {'action': 'noop'})
    assert xbmcplugin.RESOLVED[0]['succeeded'] is False


def test_a_category_lists_all_then_its_real_rows(fake_api, category_fixture):
    category = category_fixture['data']['category']
    route_category(fake_api, category, 'category', title='Filmid')
    assert actions()[0] == 'all'
    valid = {str(b['index']) for b in categories.category_blocks(category)}
    rows = [params_of(u) for u in urls() if 'action=block' in u]
    assert rows and all(row['index'] in valid for row in rows)
    assert all('category=' not in url for url in urls())
    assert xbmcplugin.STATE['category'] == 'Filmid'


def test_category_rows_are_alphabetical_after_all_and_the_banner(
        fake_api, category_fixture):
    route_category(fake_api, category_fixture['data']['category'],
                   'category')
    found = labels()
    assert found[1] == 'Featured (1)'
    assert len(found) > 3
    assert found[2:] == sorted(found[2:], key=sort_key)


def test_a_row_plays_its_films_directly(fake_api, category_fixture):
    category = category_fixture['data']['category']
    target = next(b for b in categories.category_blocks(category)
                  if any(i.get('type') == 'movie' for i in b['items']))
    route_category(fake_api, category, 'block', index=str(target['index']))
    playables = [e for e in xbmcplugin.DIRECTORY if not e['is_folder']]
    assert playables
    for entry in playables:
        assert params_of(entry['url'])['action'] == 'play'
        assert entry['listitem'].getProperty('IsPlayable') == 'true'
    assert xbmcplugin.STATE['content'] == 'tvshows'


def test_a_hand_picked_row_lists_its_titles_alphabetically(
        fake_api, category_fixture):
    category = category_fixture['data']['category']
    block = max(categories.category_blocks(category),
                key=lambda b: len(b['items']))
    route_category(fake_api, category, 'block', index=str(block['index']))
    assert len(labels()) > 1
    assert labels() == sorted(labels(), key=sort_key)


@pytest.mark.parametrize('manual', [
    {'banner': False, 'highTimeline': False},
    None,
])
def test_a_row_err_fills_itself_keeps_its_newest_first_order(fake_api,
                                                             manual):
    rows = [{'id': 3, 'type': 'movie', 'heading': 'Zorro'},
            {'id': 2, 'type': 'movie', 'heading': 'Mina'},
            {'id': 1, 'type': 'movie', 'heading': 'Aabits'}]
    category = {'frontPage': [{'header': 'Viimati lisatud', 'manual': manual,
                               'data': rows}]}
    route_category(fake_api, category, 'block', index='0')
    assert labels() == ['Zorro', 'Mina', 'Aabits']


def sort_methods():
    return [method for method, _mask in xbmcplugin.STATE['sort_methods']]


def test_a_listing_opens_in_saturns_order_and_can_be_resorted_by_date(
        fake_api, category_fixture, series_fixture):
    route_category(fake_api, category_fixture['data']['category'], 'all')
    assert sort_methods() == [xbmcplugin.SORT_METHOD_UNSORTED,
                              xbmcplugin.SORT_METHOD_LABEL,
                              xbmcplugin.SORT_METHOD_VIDEO_YEAR]
    xbmcplugin.reset()
    route_page(fake_api, series_fixture['data'], 'content')
    assert sort_methods()[0] == xbmcplugin.SORT_METHOD_UNSORTED
    assert xbmcplugin.SORT_METHOD_EPISODE in sort_methods()


def test_resorting_keeps_saturns_labels(fake_api, category_fixture):
    route_category(fake_api, category_fixture['data']['category'], 'all')
    assert {mask for _method, mask in xbmcplugin.STATE['sort_methods']} == \
        {'%L'}


def test_menus_offer_no_sorting(fake_api):
    route(fake_api, {'action': 'live', 'kind': 'tv'})
    assert xbmcplugin.STATE['sort_methods'] == []


def test_info_pages_are_left_out_of_rows(fake_api):
    route_category(fake_api, row_with_an_info_page(), 'block', index='0')
    assert labels() == ['real']


def test_all_lists_a_category_alphabetically_as_many_as_it_claims(
        fake_api, category_fixture):
    category = category_fixture['data']['category']
    route_category(fake_api, category, 'category')
    claimed = all_count()
    xbmcplugin.reset()
    route_category(fake_api, category, 'all')
    assert claimed == len(labels()) > 1
    assert labels() == sorted(labels(), key=sort_key)


def test_the_all_count_leaves_out_info_pages(fake_api):
    route_category(fake_api, row_with_an_info_page(), 'category')
    assert all_count() == 1


def test_a_catalogue_without_rows_is_still_browsable(fake_api):
    category = {'frontPage': [], 'items': [
        {'id': n, 'heading': 'Lotte %d' % n, 'type': 'movie'}
        for n in range(1, 4)]}
    route_category(fake_api, category, 'category')
    assert all_count() == 3
    xbmcplugin.reset()
    route_category(fake_api, category, 'all')
    assert len(xbmcplugin.DIRECTORY) == 3


def test_images_can_be_switched_off(fake_api, category_fixture):
    xbmcaddon.SETTINGS['enableImages'] = 'false'
    category = category_fixture['data']['category']
    index = categories.category_blocks(category)[0]['index']
    route_category(fake_api, category, 'block', index=str(index))
    assert all(entry['listitem'].art == {} for entry in xbmcplugin.DIRECTORY)


def test_season_links_open_each_seasons_own_episodes(fake_api,
                                                     series_fixture):
    page = series_fixture['data']
    seasons = content_mod.season_list(page)
    assert len(seasons) >= 2, \
        'the fixture lost its multi-season shape; re-record a real series'
    route_page(fake_api, page, 'content')
    ids = {params_of(u)['id'] for u in urls() if 'action=season' in u}
    assert ids == {str(s['first_content_id']) for s in seasons}


def test_a_season_err_gives_no_episode_id_still_opens(
        fake_api, series_fixture):
    page = json.loads(json.dumps(series_fixture['data']))
    for item in page['seasonList']['items']:
        item.pop('firstContentId', None)
    route_page(fake_api, page, 'content')
    ids = {params_of(u)['id'] for u in urls() if 'action=season' in u}
    assert ids == {str(page['mainContent']['id'])}


def test_a_single_season_lists_its_episodes_directly(fake_api,
                                                     series_fixture):
    page = dict(series_fixture['data'])
    page['seasonList'] = dict(page['seasonList'],
                              items=page['seasonList']['items'][:1])
    route_page(fake_api, page, 'content')
    assert 'season' not in actions()


def test_a_season_lists_its_episodes(fake_api, series_fixture):
    page = series_fixture['data']
    season = content_mod.season_list(page)[0]
    route_page(fake_api, page, 'season', season=str(season['id']))
    assert len(xbmcplugin.DIRECTORY) == len(season['contents'])
    assert all(not entry['is_folder'] for entry in xbmcplugin.DIRECTORY)


def test_an_unknown_season_is_an_empty_listing(fake_api, series_fixture):
    route_page(fake_api, series_fixture['data'], 'season', season='nope')
    assert xbmcplugin.DIRECTORY == []
    assert ended_ok()


def test_a_film_page_offers_playback(fake_api, movie_fixture):
    route_page(fake_api, movie_fixture['data'], 'content')
    assert 'play' in actions()


def test_a_programmes_clips_get_a_row_of_their_own(fake_api, movie_fixture):
    page = dict(movie_fixture['data'])
    page['mainContent'] = dict(page['mainContent'], clips=[
        {'id': 555, 'heading': 'Klipp', 'type': 'clip'},
        {'id': 556, 'heading': 'Teine', 'type': 'clip'}])
    route_page(fake_api, page, 'content')
    assert find_entry('action=clips') is not None
    xbmcplugin.reset()
    route_page(fake_api, page, 'clips')
    assert labels() == ['Klipp', 'Teine']
    assert actions() == ['play', 'play']


def test_a_monthly_programme_lists_years_then_months_then_episodes(
        fake_api, monthly_fixture):
    page = monthly_fixture['data']
    year = content_mod.season_list(page)[0]
    route_page(fake_api, page, 'content')
    first = [e for e in xbmcplugin.DIRECTORY if 'action=season' in e['url']]
    assert first and first[0]['is_folder'] is True

    xbmcplugin.reset()
    route_page(fake_api, page, 'season', season=str(year['id']))
    months = [e for e in xbmcplugin.DIRECTORY if 'action=season' in e['url']]
    assert [params_of(e['url'])['id'] for e in months] == [
        str(child['first_content_id']) for child in year['children']]
    for entry in months:
        assert entry['is_folder'] is True
        assert params_of(entry['url'])['sub']

    xbmcplugin.reset()
    month = year['children'][0]
    route_page(fake_api, page, 'season', season=str(year['id']),
               sub=str(month['id']))
    assert len(xbmcplugin.DIRECTORY) == len(month['contents'])
    assert all(not e['is_folder'] for e in xbmcplugin.DIRECTORY)


def _two_season_page():
    return {
        'mainContent': {'id': 100, 'heading': 'Sherlock', 'type': 'series',
                        'body': 'A detective.', 'primaryCategory':
                            {'name': 'Draama'}},
        'seasonList': {'type': 'seasonal', 'items': [
            {'id': 1, 'name': '1', 'firstContentId': 11, 'contents': []},
            {'id': 2, 'name': '2', 'firstContentId': 21, 'contents': []},
        ]},
    }


def _season_page(season_id, episodes):
    page = _two_season_page()
    for entry in page['seasonList']['items']:
        if entry['id'] == season_id:
            entry['contents'] = episodes
    return page


def _episode(content_id, season, number):
    return {'id': content_id, 'type': 'episode', 'heading': 'Sherlock',
            'subHeading': 'Osa %d' % number, 'season': season,
            'episode': number}


def test_a_series_offers_to_play_every_season_first(fake_api):
    route(fake_api, {'action': 'content', 'id': '100'},
          contents={'100': _two_season_page()})
    assert actions()[0] == 'allseasons'


def test_all_seasons_lists_every_episode_oldest_first(fake_api):
    pages = {
        '100': _two_season_page(),
        '11': _season_page(1, [_episode(12, 1, 2), _episode(11, 1, 1)]),
        '21': _season_page(2, [_episode(22, 2, 2), _episode(21, 2, 1)]),
    }
    route(fake_api, {'action': 'allseasons', 'id': '100'}, contents=pages)
    assert [params_of(url)['id'] for url in urls()] == ['11', '12', '21', '22']
    assert all(not entry['is_folder'] for entry in xbmcplugin.DIRECTORY)


def test_all_seasons_keeps_the_episodes_a_season_already_carried(fake_api):
    page = _season_page(1, [_episode(12, 1, 2), _episode(11, 1, 1)])
    pages = {'100': page, '21': _season_page(2, [_episode(21, 2, 1)])}
    instance = route(fake_api, {'action': 'allseasons', 'id': '100'},
                     contents=pages)
    assert ('content', '11', 3905) not in instance.api.calls
    assert [params_of(url)['id'] for url in urls()] == ['11', '12', '21']


def _two_year_monthly_page(*filled):
    years = []
    for year in ('2025', '2026'):
        january = {'id': 1, 'name': 'jaanuar', 'firstContentId': 'j' + year,
                   'contents': [{'id': 'e' + year, 'type': 'episode',
                                 'heading': 'Päeva püük', 'subHeading': year,
                                 'scheduleStart': int(year)}]
                   if year in filled else []}
        february = dict(january, id=2, name='veebruar',
                        firstContentId='f' + year, contents=[])
        years.append({'id': 'y' + year, 'name': year,
                      'items': [january, february]})
    return {'mainContent': {'id': 100, 'heading': 'Päeva püük'},
            'seasonList': {'type': 'monthly', 'items': years}}


def test_all_of_a_year_lists_that_years_months_not_another_years(fake_api):
    pages = {'100': _two_year_monthly_page(),
             'j2026': _two_year_monthly_page('2025', '2026'),
             'f2026': _two_year_monthly_page()}
    route(fake_api, {'action': 'allseasons', 'id': '100',
                     'season': 'y2026'}, contents=pages)
    assert [params_of(url)['id'] for url in urls()] == ['e2026']


def test_season_rows_carry_the_programmes_own_description(fake_api):
    route(fake_api, {'action': 'content', 'id': '100'},
          contents={'100': _two_season_page()})
    seasons = [e for e in xbmcplugin.DIRECTORY if 'action=season' in e['url']]
    infos = [entry['listitem'].getVideoInfoTag().info for entry in seasons]
    assert [info['season'] for info in infos] == [1, 2]
    for entry, info in zip(seasons, infos):
        assert info['plot'] == 'A detective.'
        assert info['genre'] == ['Draama']
        assert info['title'] == entry['listitem'].label


def test_episodes_keep_their_episode_order_not_the_alphabet(fake_api):
    page = {'mainContent': {'id': 1, 'heading': 'Sari'},
            'seasonList': {'items': [{'id': 7, 'name': '1', 'contents': [
                {'id': 12, 'type': 'episode', 'heading': 'Sari',
                 'subHeading': 'Algus', 'season': 1, 'episode': 2},
                {'id': 11, 'type': 'episode', 'heading': 'Sari',
                 'subHeading': 'Viimane', 'season': 1, 'episode': 1},
            ]}]}}
    route_page(fake_api, page, 'content')
    assert [params_of(u)['id'] for u in urls()] == ['11', '12']


def test_a_film_plays_from_errs_cdn(fake_api, movie_fixture):
    route_page(fake_api, movie_fixture['data'], 'play')
    assert xbmcplugin.RESOLVED[0]['succeeded'] is True
    assert xbmcplugin.RESOLVED[0]['listitem'].getPath().startswith(
        'https://vod.err.ee/')


def test_audio_plays_through_the_audio_catalogue(fake_api, audio_fixture):
    instance = route_page(fake_api, audio_fixture['data'], 'play',
                          section='Audio')
    call = [c for c in instance.api.calls if c[0] == 'content'][0]
    assert call[2] == C.AUDIO_ROOT_ID
    assert xbmcplugin.RESOLVED[0]['succeeded'] is True


def test_the_preferred_subtitle_language_reaches_the_player(
        fake_api, movie_fixture, with_inputstreamhelper):
    xbmcaddon.SETTINGS['preferredLanguage'] = 'va'
    route_page(fake_api, movie_fixture['data'], 'play')
    subtitles = xbmcplugin.RESOLVED[0]['listitem'].subtitles
    assert [url.rsplit('_', 1)[1] for url in subtitles] == ['VA.vtt']


def test_the_player_shows_no_artwork_when_artwork_is_off(
        fake_api, movie_fixture):
    xbmcaddon.SETTINGS['enableImages'] = 'false'
    route_page(fake_api, movie_fixture['data'], 'play')
    assert xbmcplugin.RESOLVED[0]['listitem'].art == {}


def test_subtitles_can_be_switched_off(fake_api, movie_fixture):
    xbmcaddon.SETTINGS['enableSubtitles'] = 'false'
    route_page(fake_api, movie_fixture['data'], 'play')
    assert xbmcplugin.RESOLVED[0]['listitem'].subtitles == []


def _search_result(search_fixture, **extra):
    block = search_fixture['video']
    return dict({'contents': block['contents'], 'page': 1, 'limit': 10},
                **extra)


def test_search_asks_for_a_phrase_and_lists_the_hits(fake_api,
                                                     search_fixture):
    xbmcgui.INPUT_TEXT[0] = 'sherlock'
    instance = route(fake_api, {'action': 'search'},
                     search=_search_result(search_fixture))
    assert xbmcgui.DIALOGS[0].get('input')
    assert search_calls(instance)[0]['phrase'] == 'sherlock'
    assert xbmcplugin.DIRECTORY


def test_a_cancelled_search_lists_nothing(fake_api):
    route(fake_api, {'action': 'search'})
    assert xbmcplugin.STATE['ended']['succeeded'] is False
    assert xbmcplugin.DIRECTORY == []


def test_a_search_link_searches_for_its_phrase(fake_api, search_fixture):
    instance = route(fake_api, {'action': 'searchresults', 'phrase': 'eesti'},
                     search=_search_result(search_fixture))
    assert xbmcplugin.DIRECTORY
    assert search_calls(instance)[0]['phrase'] == 'eesti'


def test_one_search_covers_the_whole_catalogue(fake_api):
    instance = route(fake_api, {'action': 'searchresults', 'phrase': 'x',
                                'section': 'Audio', 'category': '4137',
                                'domain': 'lasteekraan'})
    calls = search_calls(instance)
    assert len(calls) == 1
    assert 'category' not in calls[0] and 'site_content' not in calls[0]


def test_an_audio_hit_opens_as_audio(fake_api, search_fixture):
    video, audio = search_fixture['video']['contents'][:2]
    route(fake_api, {'action': 'searchresults', 'phrase': 'x'},
          search={'contents': [video, audio], 'audio_ids': {audio['id']},
                  'has_more': False})
    assert [params_of(u)['section'] for u in urls()] == ['Video', 'Audio']


def test_search_offers_the_next_page(fake_api, search_fixture):
    route(fake_api, {'action': 'searchresults', 'phrase': 'x', 'page': '1'},
          search=_search_result(search_fixture, has_more=True))
    pages = [params_of(u)['page'] for u in urls() if 'searchresults' in u]
    assert pages == ['2']


def test_a_search_without_hits_says_so(fake_api):
    route(fake_api, {'action': 'searchresults', 'phrase': 'zz'})
    assert xbmcgui.NOTIFICATIONS


def test_live_tv_lists_the_channels_and_the_schedule(fake_api):
    route(fake_api, {'action': 'live', 'kind': 'tv'})
    channels = [e for e in xbmcplugin.DIRECTORY
                if 'action=playlive' in e['url']]
    assert [e['listitem'].label for e in channels] == ['ETV', 'ETV2', 'ETV+']
    for entry in channels:
        assert entry['is_folder'] is False
        assert entry['listitem'].getProperty('IsPlayable') == 'true'
    assert find_entry('action=epgchannels')['is_folder'] is True
    assert find_entry('action=radiostations') is None


def test_the_radio_menu_leads_to_every_stations_programmes(fake_api):
    route(fake_api, {'action': 'live', 'kind': 'radio'})
    assert 'Vikerraadio' in labels() and 'ETV' not in labels()
    assert find_entry('action=radiostations')['listitem'].label == \
        'Programmes'
    xbmcplugin.reset()
    route(fake_api, {'action': 'radiostations'})
    assert labels() == ['Vikerraadio', 'Raadio 2', 'Klassikaraadio',
                        'Raadio 4', 'Raadio Tallinn']
    assert [params_of(u)['station'] for u in urls()] == [
        '404', '405', '407', '406', '408']


def test_a_stations_programmes_open_as_audio_in_estonian_order(
        fake_api, radio_fixture):
    results = list(reversed(radio_fixture['data']['results']))
    instance = route(fake_api, {'action': 'radioprogrammes',
                                'station': '404', 'title': 'Vikerraadio'},
                     radio=results)
    assert instance.api.calls == [('radio', '404')]
    assert len(labels()) == len(results)
    assert labels() == sorted(labels(), key=sort_key)
    first = xbmcplugin.DIRECTORY[0]
    assert first['is_folder'] is True
    assert params_of(first['url'])['action'] == 'content'
    assert params_of(first['url'])['section'] == 'Audio'
    assert first['listitem'].art['thumb'].startswith(
        'https://s.err.ee/photo/')
    assert xbmcplugin.STATE['category'] == 'Vikerraadio'


def test_a_live_channel_plays_as_live(fake_api):
    route(fake_api, {'action': 'playlive', 'channel': 'etv', 'label': 'ETV'},
          live={'src': '//live.err.ee/live/etv.m3u8',
                'config': {'mediaType': 'video'}})
    resolved = xbmcplugin.RESOLVED[0]
    assert resolved['succeeded'] is True
    assert resolved['listitem'].getPath() == \
        'https://live.err.ee/live/etv.m3u8'
    assert resolved['listitem'].getProperty('IsLive') == 'true'


def _now_showing(name, **extra):
    now = int(time.time())
    return [dict({'startTime': now - 60, 'endTime': now + 60, 'name': name},
                 **extra)]


@pytest.mark.parametrize('schedule,label', [
    (_now_showing('Ringvaade'), 'ETV2: Ringvaade'),
    (_now_showing('Grace', streamGeoblocked=True), 'ETV2: Grace'),
    ([], 'ETV2'),
    (None, 'ETV2'),
])
def test_live_tv_is_named_after_what_is_on_and_plays_regardless(
        fake_api, schedule, label):
    instance = make_router(fake_api, {'action': 'playlive', 'kind': 'tv',
                                      'channel': 'etv2', 'label': 'ETV2'},
                           live={'src': '//live.err.ee/live/etv2.m3u8'},
                           schedule=schedule)
    if schedule is None:
        instance.api.get_schedule = raising(ApiError('schedule down'))
    instance.dispatch()
    resolved = xbmcplugin.RESOLVED[0]
    assert resolved['succeeded'] is True
    assert resolved['listitem'].label == label
    assert not xbmcgui.NOTIFICATIONS


def test_live_radio_looks_up_the_radio_schedule(fake_api):
    instance = route(fake_api, {'action': 'playlive', 'kind': 'radio',
                                'channel': 'vikerraadio'},
                     live={'src': '//live.err.ee/live/vikerraadio.m3u8'})
    kinds = {call[3] for call in instance.api.calls if call[0] == 'schedule'}
    assert kinds == {'radio'}


def test_the_schedule_lists_every_channel(fake_api):
    route(fake_api, {'action': 'epgchannels', 'kind': 'tv'})
    assert 'ETV' in labels()
    for entry in xbmcplugin.DIRECTORY:
        assert entry['is_folder'] is True
        assert params_of(entry['url'])['action'] == 'epgdays'


def test_the_schedule_offers_today_and_the_catch_up_window(fake_api):
    route(fake_api, {'action': 'epgdays', 'kind': 'tv', 'channel': 'etv',
                     'label': 'ETV'})
    dates = [params_of(u)['date'] for u in urls()]
    assert len(dates) == C.SCHEDULE_DAYS_BACK + 1
    assert dates == sorted(set(dates), reverse=True)


def test_a_days_schedule_plays_what_was_recorded(fake_api, schedule_fixture):
    route(fake_api, {'action': 'epg', 'kind': 'tv', 'channel': 'etv',
                     'label': 'ETV', 'date': '2026-09-10'},
          schedule=schedule_fixture)
    plays = [e for e in xbmcplugin.DIRECTORY
             if params_of(e['url'])['action'] == 'play']
    assert plays, 'no catch-up entries routed to playback'
    for entry in plays:
        assert entry['listitem'].getProperty('IsPlayable') == 'true'
        assert params_of(entry['url'])['id']


def test_a_radio_schedule_plays_through_the_audio_catalogue(
        fake_api, schedule_fixture):
    instance = route(fake_api, {'action': 'epg', 'kind': 'radio',
                                'channel': 'vikerraadio',
                                'date': '2026-09-10'},
                     schedule=schedule_fixture)
    assert ('schedule', 'vikerraadio', '2026-09-10', 'radio') in \
        instance.api.calls
    plays = [params_of(u) for u in urls() if params_of(u)['action'] == 'play']
    assert plays and plays[0]['section'] == 'Audio'
    assert all('root=' not in url for url in urls())


def test_a_schedule_row_without_a_recording_is_not_playable(fake_api):
    instance = route(fake_api, {'action': 'epg', 'kind': 'tv',
                                'channel': 'etv', 'date': '2026-09-10'},
                     schedule=[
                         {'startTime': 100, 'endTime': 200,
                          'name': 'Recorded', 'contentId': 7,
                          'mediaExist': True},
                         {'startTime': 200, 'endTime': 300,
                          'name': 'Not recorded', 'contentId': 0,
                          'mediaExist': False}])
    assert ('schedule', 'etv', '2026-09-10', 'tv') in instance.api.calls
    assert actions() == ['play', 'noop']
    assert 'Recorded' in labels()[0]
    assert 'Not recorded' in labels()[1]


def test_a_catalogue_choice_stays_in_every_link(fake_api):
    kids = router_mod.Router(BASE, HANDLE, {'domain': 'lasteekraan'})
    assert kids.api.root_id == 3592
    assert 'domain=lasteekraan' in kids.url(action='category', path='x')
    plain = router_mod.Router(BASE, HANDLE, {})
    assert 'domain=' not in plain.url(action='category', path='x')


@pytest.mark.parametrize('argv,params', [
    ([BASE, '5', '?section=Video'], {'section': 'Video'}),
    ([BASE, '1', ''], {}),
])
def test_kodis_arguments_reach_the_router(fake_api, monkeypatch,
                                          menu_fixture, argv, params):
    captured = {}

    class Spy(router_mod.Router):
        def __init__(self, base_url, handle, given):
            captured.update(handle=handle, params=given)
            super().__init__(base_url, handle, given)
            self._api_client = fake_api(menu=menu_fixture['data']['items'])

    monkeypatch.setattr(router_mod, 'Router', Spy)
    router_mod.run(argv)
    assert captured == {'handle': int(argv[1]), 'params': params}
    assert xbmcplugin.DIRECTORY
