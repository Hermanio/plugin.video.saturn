# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from . import constants as C
from .helpers import default_headers, dicts, safe_int


class ApiError(Exception):
    pass


class ErrApi:
    def __init__(self, domain=C.DEFAULT_DOMAIN, log=None):
        self.domain = C.DOMAINS[domain]
        self._log = log or (lambda msg: None)

    @property
    def root_id(self):
        return self.domain['root_id']

    def get_json(self, url, params):
        url = url + '?' + urlencode(params)
        self._log('GET %s' % url)
        try:
            with urlopen(Request(url, headers=default_headers()),
                         timeout=C.HTTP_TIMEOUT) as response:
                return json.load(response)
        except Exception as exc:
            raise ApiError('%s: %s' % (url, exc))

    @staticmethod
    def _data(payload):
        if isinstance(payload, dict):
            if payload.get('error'):
                raise ApiError(str(payload['error']))
            return payload.get('data', payload)
        return payload

    def get_menu(self):
        data = self._data(self.get_json(C.EP_MENU,
                                        {'menuId': self.domain['menu_id']}))
        items = (data or {}).get('items') or []
        if not isinstance(items, list):
            raise ApiError('menu items malformed')
        return items

    def get_category(self, url):
        data = self._data(self.get_json(C.EP_CATEGORY, {
            'url': (url or '').strip('/'),
            'domain': self.domain['domain'],
            'page': 'web',
        }))
        category = (data or {}).get('category')
        if not isinstance(category, dict):
            raise ApiError('category %s malformed' % url)
        return category

    def get_content(self, content_id, root_id=None):
        data = self._data(self.get_json(C.EP_CONTENT, {
            'contentId': content_id,
            'rootId': root_id if root_id is not None else self.root_id,
            'page': 'video',
        }))
        if not isinstance(data, dict) or 'mainContent' not in data:
            raise ApiError('content %s malformed' % content_id)
        return data

    def _search(self, phrase, page, limit, media=C.SEARCH_MEDIA):
        options = {
            'page': int(page),
            'limit': int(limit),
            'offset': 0,
            'category': C.SEARCH_ROOT_ID,
            'phrase': phrase or '',
            'types': ['media'],
            'searchTypes': list(media),
            'viewTypes': ['series', 'movie', 'episode', 'clip'],
            'now': 0,
        }
        data = self._data(self.get_json(C.EP_SEARCH, {
            'type': media[0],
            'options': json.dumps(options, separators=(',', ':')),
        }))
        return data if isinstance(data, dict) else {}

    def search_all(self, phrase='', page=1, limit=C.SEARCH_PAGE_SIZE):
        data = self._search(phrase, page, limit)
        blocks = [data.get(medium) or {} for medium in C.SEARCH_MEDIA]
        audio = data.get('audio') or {}
        return {
            'contents': [item for block in blocks
                         for item in block.get('contents') or []],
            'audio_ids': {item.get('id') for item in
                          dicts(audio.get('contents'))},
            'has_more': any(len(block.get('contents') or []) >=
                            (block.get('limit') or limit) for block in blocks),
        }

    def get_radio_programmes(self, station_id):
        programmes = []
        page = 1
        while True:
            payload = self.get_json(C.EP_RADIO_PROGRAMMES, {
                'active': 'true',
                'sortOrder': 'asc',
                'page': page,
                'limit': C.RADIO_PAGE_SIZE,
                'primaryCategoryIds[]': station_id,
            })
            if not isinstance(payload, dict) or \
                    payload.get('status') != 'success':
                raise ApiError('radio programmes %s malformed' % station_id)
            programmes.extend((payload.get('data') or {}).get('results')
                              or [])
            if page >= safe_int(payload.get('totalPages'), 1):
                return programmes
            page += 1

    def get_live_media(self, channel_name):
        data = self._data(self.get_json(C.EP_LIVE,
                                        {'channelName': channel_name}))
        if not isinstance(data, dict) or not data.get('src'):
            raise ApiError('live channel %s unavailable' % channel_name)
        return data

    def get_schedule(self, channel, when, kind='tv'):
        endpoint = C.EP_RADIO_SCHEDULE if kind == 'radio' else C.EP_TV_SCHEDULE
        payload = self.get_json(endpoint, {
            'channel': channel,
            'day': when.day,
            'month': when.month,
            'year': when.year,
        })
        if isinstance(payload, dict):
            payload = payload.get('data') or []
        return payload if isinstance(payload, list) else []
