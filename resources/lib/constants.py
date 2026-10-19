# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
API_BASE = 'https://services.err.ee'

REFERER = 'https://jupiter.err.ee/'
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

EP_MENU = API_BASE + '/api/v2/menu/getMenuById'
EP_CATEGORY = API_BASE + '/api/v2/category/getByUrl'
EP_CONTENT = API_BASE + '/api/v2/vodContent/getContentPageData'
EP_SEARCH = API_BASE + '/api/search/getVodContents2/'
EP_LIVE = API_BASE + '/api/live/getLiveMediaData'
EP_TV_SCHEDULE = API_BASE + '/api/tvSchedule/getTimelineSchedule'
EP_RADIO_SCHEDULE = API_BASE + '/api/radioSchedule/getTimelineSchedule'
EP_RADIO_PROGRAMMES = 'https://eestiraadio.err.ee/api/v1/search/az'
PHOTO_BASE = 'https://s.err.ee/photo/'

DOMAINS = {
    'jupiter': {
        'domain': 'jupiter.err.ee',
        'root_id': 3905,
        'menu_id': 555,
        'section_fallbacks': {
            'audio': (('Saated', '/audio'), ('Muusika', '/muusika')),
        },
    },
    'lasteekraan': {
        'domain': 'lasteekraan.err.ee',
        'root_id': 3592,
        'menu_id': 1124,
        'label': 'Lasteekraan',
        'path': 'vaata-ja-kuula',
    },
}
DEFAULT_DOMAIN = 'jupiter'

AUDIO_ROOT_ID = 4483
SEARCH_ROOT_ID = DOMAINS['jupiter']['root_id']
SEARCH_MEDIA = ('video', 'audio')

MAKER_ROLES = {
    10: 'director',
    18: 'writer',
    8: 'cast',
    4: 'cast',
    3: 'cast',
}

MENU_ICONS = {
    'search': 'search.png',
    'tv': 'tv.png',
    'radio': 'radio.png',
    'programmes': 'audio.png',
    'schedule': 'schedule.png',
    'day': 'day.png',
    'clips': 'clips.png',
    'all': 'all.png',
    'more': 'more.png',
    'lasteekraan': 'kids.png',
}

SECTION_ICONS = {'audio': 'audio.png'}
DEFAULT_CATEGORY_ICON = 'video.png'
CATEGORY_ICONS = {
    'filmid': 'movies.png',
    'sarjad': 'series.png',
    'muusika': 'music.png',
    'raadioteater': 'songs.png',
    'sport': 'sport.png',
}

FOLDER_TYPES = ('series', 'content', 'show', 'category')
SKIP_TYPES = ('info',)

HLS_PRIORITY = ('hlsNew', 'hls2', 'hls', 'hlsNoSub')
DASH_PRIORITY = ('dashNew', 'dash', 'dashNoSub')

ART_FANART = ('71', '69', '37', '17')
ART_POSTER = ('60', '8', '22', '17')
ART_THUMB = ('17', '22', '8', '69')
ART_ICON = ('44', '8', '22', '1')

LIVE_TV = (
    ('etv', 'ETV'),
    ('etv2', 'ETV2'),
    ('etvpluss', 'ETV+'),
)
LIVE_RADIO = (
    ('vikerraadio', 'Vikerraadio'),
    ('raadio2', 'Raadio 2'),
    ('klassikaraadio', 'Klassikaraadio'),
    ('raadio4', 'Raadio 4'),
    ('raadiotallinn', 'Raadio Tallinn'),
)
RADIO_STATION_IDS = {
    'vikerraadio': 404,
    'raadio2': 405,
    'klassikaraadio': 407,
    'raadio4': 406,
    'raadiotallinn': 408,
}
LIVE_CHANNELS = {'tv': LIVE_TV, 'radio': LIVE_RADIO}
RADIO_PAGE_SIZE = 100
LIVE_LINKS = ('/telekava', '/raadiokava')

SCHEDULE_DAYS_BACK = 14

ALL_SEASONS_MAX_PARTS = 25

SEARCH_PAGE_SIZE = 50
HTTP_TIMEOUT = 30

ESTONIAN_ALPHABET = 'abcdefghijklmnopqrsšzžtuvwõäöüxy'
