# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
import datetime
from urllib.parse import parse_qsl

import xbmcgui
import xbmcplugin

from . import categories as cat_mod
from . import constants as C
from . import content as content_mod
from . import helpers
from . import kodiutils as ku
from . import menu as menu_mod
from . import playqueue
from . import schedule as schedule_mod
from .api import ApiError, ErrApi
from .helpers import build_url, dicts, safe_int, sort_key

PLAYBACK_ACTIONS = ('play', 'playlive', 'noop')

CONTENT_TVSHOWS = 'tvshows'
CONTENT_EPISODES = 'episodes'
CONTENT_FILES = 'files'

SORT_METHODS = {
    CONTENT_TVSHOWS: (xbmcplugin.SORT_METHOD_UNSORTED,
                      xbmcplugin.SORT_METHOD_LABEL,
                      xbmcplugin.SORT_METHOD_VIDEO_YEAR),
    CONTENT_EPISODES: (xbmcplugin.SORT_METHOD_UNSORTED,
                       xbmcplugin.SORT_METHOD_EPISODE,
                       xbmcplugin.SORT_METHOD_VIDEO_YEAR),
}
SATURNS_OWN_LABEL = '%L'


class Router:
    def __init__(self, base_url, handle, params):
        self.base_url = base_url
        self.handle = handle
        self.params = params
        self.domain_key = params.get('domain', C.DEFAULT_DOMAIN)
        self.art_enabled = ku.get_setting_bool('enableImages')
        self.items = []
        self._api_client = None

    @property
    def section(self):
        return self.params.get('section', 'Video')

    @property
    def api(self):
        if self._api_client is None:
            self._api_client = ErrApi(domain=self.domain_key, log=ku.debug)
        return self._api_client

    def url(self, **kwargs):
        if self.domain_key != C.DEFAULT_DOMAIN:
            kwargs.setdefault('domain', self.domain_key)
        return build_url(self.base_url, **kwargs)

    @staticmethod
    def _subtitle_language():
        value = ku.get_setting('preferredLanguage')
        return '' if value in ('any', '') else value

    def _art(self, item):
        return helpers.extract_art(item) if self.art_enabled else {}

    @staticmethod
    def _category_icon(entry):
        return C.CATEGORY_ICONS.get(entry['path']) or C.SECTION_ICONS.get(
            (entry['section'] or '').lower(), C.DEFAULT_CATEGORY_ICON)

    @staticmethod
    def _menu_art(icon=None):
        icon = ku.image(icon) if icon else ku.ADDON_ICON
        return {'icon': icon, 'thumb': icon, 'fanart': ku.ADDON_FANART}

    def _api(self, what, call, *args, **kwargs):
        try:
            return call(*args, **kwargs)
        except ApiError as exc:
            ku.error('%s failed: %s' % (what, exc))
            self.fail(ku.localize(30204, 'Could not reach the ERR API'))
            return None

    def _category_page(self):
        path = self.params.get('path', '')
        category = self._api('category %s' % path, self.api.get_category,
                             path)
        return category, path, self.params.get('title', path)

    def _content_page(self, content_id=None):
        content_id = content_id or self.params.get('id')
        return self._api('content %s' % content_id, self.api.get_content,
                         content_id, self._root_id_for_section(self.section))

    def add_item(self, label, url, is_folder, art=None, metadata=None,
                 playable=False):
        list_item = playqueue.build_list_item(label, art, metadata,
                                              playable=playable)
        self.items.append((url, list_item, is_folder))

    def finish(self, content_type, category=None):
        xbmcplugin.addDirectoryItems(self.handle, self.items, len(self.items))
        if category:
            xbmcplugin.setPluginCategory(self.handle, category)
        xbmcplugin.setContent(self.handle, content_type)
        for method in SORT_METHODS.get(content_type, ()):
            xbmcplugin.addSortMethod(self.handle, method,
                                     labelMask=SATURNS_OWN_LABEL)
        xbmcplugin.endOfDirectory(self.handle)

    def fail(self, message):
        ku.notify(message, icon=xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(self.handle, succeeded=False)

    def _root_id_for_section(self, section):
        return C.AUDIO_ROOT_ID if menu_mod.is_audio(section) \
            else self.api.root_id

    def add_content_item(self, item, section='Video', parent=None):
        item_type = (item.get('type') or '').lower()
        if item_type in C.SKIP_TYPES:
            return
        folder = item_type in C.FOLDER_TYPES
        url = self.url(action='content' if folder else 'play',
                       id=item.get('id'), section=section)
        self.add_item(content_mod.label_for(item), url, folder,
                      self._art(item),
                      content_mod.extract_metadata(item, parent),
                      playable=not folder)

    def add_content_items(self, items, section='Video', parent=None):
        for item in dicts(items):
            if item.get('id'):
                self.add_content_item(item, section, parent)

    def root(self):
        self.add_item(ku.localize(30002, 'Search'),
                      self.url(action='search'), True,
                      self._menu_art(C.MENU_ICONS['search']))
        self.add_item(ku.localize(30020, 'TV'),
                      self.url(action='live', kind='tv'), True,
                      self._menu_art(C.MENU_ICONS['tv']))
        self.add_item(ku.localize(30021, 'Radio'),
                      self.url(action='live', kind='radio'), True,
                      self._menu_art(C.MENU_ICONS['radio']))

        sections = self._api('menu', self.api.get_menu)
        if sections is None:
            return
        fallbacks = C.DOMAINS[self.domain_key].get('section_fallbacks')
        for entry in menu_mod.flat_entries(sections, fallbacks):
            self.add_item(entry['label'],
                          self.url(action='category', path=entry['path'],
                                   section=entry['section'],
                                   title=entry['label']),
                          True, self._menu_art(self._category_icon(entry)))

        kids = C.DOMAINS['lasteekraan']
        self.add_item(kids['label'],
                      self.url(action='category', path=kids['path'],
                               title=kids['label'], domain='lasteekraan'),
                      True, self._menu_art(C.MENU_ICONS['lasteekraan']))
        self.finish(CONTENT_FILES, category=ku.ADDON_NAME)

    def category(self):
        category, path, title = self._category_page()
        if category is None:
            return
        section = self.section

        art = self._art(category) or self._menu_art()

        blocks = cat_mod.category_blocks(category)
        listed = sum(1 for i in cat_mod.flatten_items(category)
                     if (i.get('type') or '').lower() not in C.SKIP_TYPES)
        self.add_item('%s (%d)' % (ku.localize(30003, 'All'), listed),
                      self.url(action='all', path=path, section=section,
                               title=title), True,
                      self._menu_art(C.MENU_ICONS['all']))
        featured = ku.localize(30014, 'Featured')
        for block in sorted(blocks, key=lambda block: (
                not block['banner'], sort_key(block['header'] or featured))):
            label = block['header'] or featured
            self.add_item('%s (%d)' % (label, len(block['items'])),
                          self.url(action='block', path=path,
                                   index=block['index'], section=section,
                                   title=label),
                          True, art)
        self.finish(CONTENT_FILES, category=title)

    def block(self):
        category, _path, title = self._category_page()
        if category is None:
            return
        items, curated = cat_mod.block_at(category, self.params['index'])
        if curated:
            items = content_mod.alphabetical(items)
        self.add_content_items(items, self.section)
        self.finish(CONTENT_TVSHOWS, category=title)

    def all_items(self):
        category, _path, title = self._category_page()
        if category is None:
            return
        self.add_content_items(content_mod.alphabetical(
            cat_mod.flatten_items(category)), self.section)
        self.finish(CONTENT_TVSHOWS, category=title)

    def _add_year(self, year, art, parent):
        self._add_all_row(ku.localize(30010, 'All %s') % year['name'],
                          year['children'], art, parent, scope=year['id'])
        for month in year['children']:
            label = month['name'].capitalize()
            self.add_item(label,
                          self.url(action='season',
                                   id=month['first_content_id']
                                   or self.params.get('id'),
                                   season=year['id'], sub=month['id'],
                                   section=self.section), True, art,
                          content_mod.folder_metadata(parent, label))

    def _add_season_rows(self, seasons, monthly, art, parent):
        if not monthly:
            self._add_all_row(ku.localize(30008, 'All seasons'), seasons,
                              art, parent)
        season_word = ku.localize(30007, 'Season')
        for season in seasons:
            label = season['name'] or season_word
            number = label.replace('.', '')
            if not monthly and number.isdigit():
                label = '%s %s' % (season_word, label)
            self.add_item(label,
                          self.url(action='season',
                                   id=season['first_content_id']
                                   or self.params.get('id'),
                                   season=season['id'],
                                   section=self.section), True, art,
                          content_mod.folder_metadata(
                              parent, label, safe_int(number) or None))

    def _add_seasons(self, page, seasons, parent):
        art = self._art(page['mainContent'])
        only = seasons[0] if len(seasons) == 1 else None
        if only and only['contents']:
            self.add_content_items(only['contents'], self.section, parent)
        elif only and only['children']:
            self._add_year(only, art, parent)
        else:
            monthly = content_mod.season_list_type(page) == 'monthly'
            self._add_season_rows(seasons, monthly, art, parent)

    def _add_clips_row(self, clips, parent):
        label = ku.localize(30009, 'Clips')
        self.add_item('%s (%d)' % (label, len(clips)),
                      self.url(action='clips', id=self.params.get('id'),
                               section=self.section), True,
                      self._menu_art(C.MENU_ICONS['clips']),
                      content_mod.folder_metadata(parent, label))

    def _add_single_title(self, page):
        main = page['mainContent']
        if content_mod.pick_media(main):
            self.add_content_item(dict(main, type='movie'), self.section)
        self.add_content_items(page.get('categoryContents'), self.section)

    def content(self):
        page = self._content_page()
        if page is None:
            return

        main = page['mainContent']
        parent = content_mod.extract_metadata(main)
        seasons = content_mod.season_list(page)
        clips = dicts(main.get('clips'))

        self._add_seasons(page, seasons, parent)
        if clips:
            self._add_clips_row(clips, parent)
        if not seasons and not clips:
            self._add_single_title(page)
        self.finish(CONTENT_EPISODES, category=main.get('heading') or '')

    def season(self):
        page = self._content_page()
        if page is None:
            return

        main = page['mainContent']
        parent = content_mod.extract_metadata(main)
        seasons = content_mod.season_list(page)
        entry = content_mod.find_season(seasons, self.params['season'],
                                        self.params.get('sub'))
        if entry is None:
            self.finish(CONTENT_EPISODES)
            return

        if entry['children'] and not entry['contents']:
            self._add_year(entry, self._art(main), parent)
        else:
            self.add_content_items(entry['contents'], self.section, parent)
        self.finish(CONTENT_EPISODES, category=entry['name'])

    def _add_all_row(self, label, parts, art, parent=None, scope=None):
        parts = [part for part in parts or [] if part.get('first_content_id')
                 or part.get('contents')]
        if not 1 < len(parts) <= C.ALL_SEASONS_MAX_PARTS:
            return
        self.add_item(label,
                      self.url(action='allseasons', id=self.params.get('id'),
                               section=self.section, season=scope),
                      True, art or self._menu_art(C.MENU_ICONS['all']),
                      content_mod.folder_metadata(parent, label))

    def all_seasons(self):
        page = self._content_page()
        if page is None:
            return

        main = page['mainContent']
        parent = content_mod.extract_metadata(main)
        seasons = content_mod.season_list(page)
        parts = content_mod.leaf_seasons(seasons, self.params.get('season'))

        items = []
        for address, part in parts[:C.ALL_SEASONS_MAX_PARTS]:
            contents = part['contents']
            if not contents and part['first_content_id']:
                fetched = self._content_page(part['first_content_id'])
                if fetched is None:
                    return
                found = content_mod.find_season(
                    content_mod.season_list(fetched), *address)
                contents = found['contents'] if found else []
            items.extend(contents)

        self.add_content_items(content_mod.order_contents(items),
                               self.section, parent)
        self.finish(CONTENT_EPISODES,
                    category=main.get('heading') or '')

    def clips(self):
        page = self._content_page()
        if page is None:
            return
        main = page['mainContent']
        self.add_content_items(main.get('clips'), self.section,
                               content_mod.extract_metadata(main))
        self.finish(CONTENT_EPISODES)

    def search(self):
        phrase = self.params.get('phrase') or \
            ku.get_search_phrase(ku.localize(30011, 'Search Saturn'))
        if not phrase:
            xbmcplugin.endOfDirectory(self.handle, succeeded=False)
            return
        self.search_results(phrase)

    def search_results(self, phrase=None):
        phrase = phrase or self.params.get('phrase', '')
        page = int(self.params.get('page', 1))
        result = self._api('search', self.api.search_all, phrase=phrase,
                           page=page)
        if result is None:
            return

        items = result['contents']
        audio_ids = result.get('audio_ids') or set()
        for item in dicts(items):
            if item.get('id'):
                self.add_content_item(
                    item, 'Audio' if item['id'] in audio_ids else 'Video')
        if result['has_more']:
            self.add_item(ku.localize(30005, 'Next page'),
                          self.url(action='searchresults', phrase=phrase,
                                   page=page + 1), True,
                          self._menu_art(C.MENU_ICONS['more']))
        if not items:
            ku.notify(ku.localize(30012, 'No results'))
        self.finish(CONTENT_TVSHOWS,
                    category='%s: %s' % (ku.localize(30002, 'Search'), phrase))

    def play(self):
        content_id = self.params.get('id')
        section = self.section
        page = self.api.get_content(content_id,
                                    self._root_id_for_section(section))
        main = page['mainContent']
        playqueue.resolve(
            self.handle, main,
            prefer_audio=menu_mod.is_audio(section),
            subtitle_language=self._subtitle_language(),
            enable_subtitles=ku.get_setting_bool('enableSubtitles'),
            enable_art=self.art_enabled,
        )

    def live(self):
        kind = self.params.get('kind', 'tv')
        art = self._menu_art(C.MENU_ICONS[kind])
        for name, label in C.LIVE_CHANNELS[kind]:
            self.add_item(label,
                          self.url(action='playlive', channel=name,
                                   label=label, kind=kind),
                          False, art,
                          {'title': label, 'studio': 'ERR'}, playable=True)
        self.add_item(ku.localize(30016, 'Schedule'),
                      self.url(action='epgchannels', kind=kind), True,
                      self._menu_art(C.MENU_ICONS['schedule']))
        if kind == 'radio':
            self.add_item(ku.localize(30022, 'Programmes'),
                          self.url(action='radiostations'), True,
                          self._menu_art(C.MENU_ICONS['programmes']))
        self.finish(CONTENT_FILES, category=ku.localize(30015, 'Live'))

    def radio_stations(self):
        art = self._menu_art(C.MENU_ICONS['programmes'])
        for name, label in C.LIVE_RADIO:
            self.add_item(label,
                          self.url(action='radioprogrammes', title=label,
                                   station=C.RADIO_STATION_IDS[name]),
                          True, art)
        self.finish(CONTENT_FILES,
                    category=ku.localize(30022, 'Programmes'))

    def radio_programmes(self):
        station = self.params.get('station', '')
        results = self._api('radio programmes %s' % station,
                            self.api.get_radio_programmes, station)
        if results is None:
            return
        self.add_content_items(content_mod.alphabetical(
            cat_mod.radio_programmes(results)), 'Audio')
        self.finish(CONTENT_TVSHOWS, category=self.params.get('title', ''))

    def epg_channels(self):
        kind = self.params.get('kind', 'tv')
        art = self._menu_art(C.MENU_ICONS['schedule'])
        for name, label in C.LIVE_CHANNELS[kind]:
            self.add_item(label,
                          self.url(action='epgdays', kind=kind, channel=name,
                                   label=label), True, art)
        self.finish(CONTENT_FILES, category=ku.localize(30016, 'Schedule'))

    def epg_days(self):
        kind = self.params.get('kind', 'tv')
        channel = self.params.get('channel', '')
        label = self.params.get('label', channel)
        art = self._menu_art(C.MENU_ICONS['day'])
        today = datetime.date.today()
        for offset in range(0, C.SCHEDULE_DAYS_BACK + 1):
            day = today - datetime.timedelta(days=offset)
            day_label = ku.localize(30017, 'Today') if offset == 0 \
                else day.strftime('%d.%m.%Y')
            self.add_item(day_label,
                          self.url(action='epg', kind=kind, channel=channel,
                                   label=label, date=day.isoformat()),
                          True, art)
        self.finish(CONTENT_FILES, category=label)

    def epg(self):
        kind = self.params.get('kind', 'tv')
        channel = self.params.get('channel', '')
        label = self.params.get('label', channel)
        day = datetime.date.fromisoformat(self.params['date'])

        raw = self._api('schedule %s' % channel, self.api.get_schedule,
                        channel, day, kind=kind)
        if raw is None:
            return

        section = 'Audio' if kind == 'radio' else 'Video'
        art = self._menu_art(C.MENU_ICONS[kind])
        for programme in schedule_mod.parse_schedule(raw):
            metadata = {'title': programme['title'], 'studio': 'ERR'}
            if programme['plot']:
                metadata['plot'] = programme['plot']
            playable = schedule_mod.is_playable(programme)
            url = self.url(action='play', id=programme['content_id'],
                           section=section) if playable \
                else self.url(action='noop')
            self.add_item(schedule_mod.programme_label(programme), url,
                          False, art, metadata, playable=playable)
        self.finish(CONTENT_EPISODES, category='%s %s' % (
            label, day.strftime('%d.%m.%Y')))

    def noop(self):
        playqueue.cancel(self.handle)

    def play_live(self):
        channel = self.params.get('channel', '')
        kind = self.params.get('kind', 'tv')
        label = self.params.get('label', channel)

        payload = self.api.get_live_media(channel)
        current = self._current_programme(channel, kind)
        if current:
            label = '%s: %s' % (label, current['title'])
        playqueue.resolve_live(self.handle, label, payload)

    def _current_programme(self, channel, kind):
        now = datetime.datetime.now()
        days = [now.date()]
        if now.hour < 6:
            days.append(now.date() - datetime.timedelta(days=1))
        programmes = []
        for day in days:
            try:
                programmes.extend(schedule_mod.parse_schedule(
                    self.api.get_schedule(channel, day, kind=kind)))
            except ApiError:
                continue
        current = schedule_mod.current_programme(programmes)
        return current if current and current.get('title') else None

    ACTIONS = {
        '': 'root',
        'category': 'category',
        'block': 'block',
        'all': 'all_items',
        'content': 'content',
        'season': 'season',
        'allseasons': 'all_seasons',
        'clips': 'clips',
        'search': 'search',
        'searchresults': 'search_results',
        'play': 'play',
        'live': 'live',
        'playlive': 'play_live',
        'radiostations': 'radio_stations',
        'radioprogrammes': 'radio_programmes',
        'epgchannels': 'epg_channels',
        'epgdays': 'epg_days',
        'epg': 'epg',
        'noop': 'noop',
    }

    def dispatch(self):
        action = self.params.get('action', '')
        ku.debug('dispatch %s %s' % (action or 'root', self.params))
        try:
            getattr(self, self.ACTIONS[action])()
        except Exception as exc:
            ku.error('%s raised %s: %s' % (action or 'root',
                                           type(exc).__name__, exc))
            if isinstance(exc, ApiError):
                message = ku.localize(30204, 'Could not reach the ERR API')
            else:
                message = ku.localize(30205,
                                      'Something went wrong, see the Kodi log')
            if action in PLAYBACK_ACTIONS:
                playqueue.reject(self.handle, message)
            else:
                self.fail(message)


def run(argv):
    params = dict(parse_qsl(argv[2].lstrip('?')))
    Router(argv[0], int(argv[1]), params).dispatch()
