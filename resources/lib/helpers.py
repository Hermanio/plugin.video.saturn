# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
import html
import re
import time
import unicodedata
from urllib.parse import urlencode

from . import constants as C

_TAG_RE = re.compile(r'<[^>]+>')
_WS_RE = re.compile(r'[ \t\r\f\v]+')
_SORT_TOKEN_RE = re.compile(r'\d+|\w|\s+')


def absolutize(url):
    if not url:
        return ''
    url = url.strip()
    if url.startswith('//'):
        return 'https:' + url
    if url.startswith('/'):
        return C.API_BASE + url
    return url


def default_headers():
    return {
        'User-Agent': C.USER_AGENT,
        'Referer': C.REFERER,
        'Accept': 'application/json, text/plain, */*',
    }


def stream_headers():
    return urlencode({'User-Agent': C.USER_AGENT, 'Referer': C.REFERER})


def strip_html(text):
    if not text:
        return ''
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p\s*>', '\n\n', text, flags=re.IGNORECASE)
    text = html.unescape(_TAG_RE.sub('', text)).replace('\xa0', ' ')
    text = _WS_RE.sub(' ', text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def timestamp_to_human(ts, fmt):
    if not ts:
        return ''
    try:
        return time.strftime(fmt, time.localtime(int(ts)))
    except (ValueError, TypeError, OverflowError):
        return ''


def build_url(base, **kwargs):
    params = {k: v for k, v in kwargs.items() if v not in (None, '')}
    if not params:
        return base
    return base + '?' + urlencode(sorted(params.items()))


def pick_photo(photos, preferred_types):
    for photo in photos:
        if not isinstance(photo, dict):
            continue
        types = photo.get('photoTypes') or {}
        for key in preferred_types:
            entry = types.get(key)
            if isinstance(entry, dict) and entry.get('url'):
                return absolutize(entry['url'])
        if photo.get('photoUrlOriginal'):
            return absolutize(photo['photoUrlOriginal'])
    return ''


def extract_art(item):
    landscape = item.get('photos') or item.get('horizontalPhotos') or []
    poster = pick_photo(item.get('verticalPhotos') or [], C.ART_POSTER)
    thumb = pick_photo(landscape, C.ART_THUMB) or poster
    art = {
        'thumb': thumb,
        'poster': poster or thumb,
        'fanart': pick_photo(landscape, C.ART_FANART) or thumb,
        'icon': pick_photo(item.get('squarePhotos') or [], C.ART_ICON)
        or thumb,
        'landscape': thumb,
    }
    return {key: value for key, value in art.items() if value}


def dicts(value):
    return [i for i in value if isinstance(i, dict)] \
        if isinstance(value, list) else []


def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _letter_rank(char):
    if char in C.ESTONIAN_ALPHABET:
        return 1, C.ESTONIAN_ALPHABET.index(char)
    base = unicodedata.normalize('NFD', char)[0]
    if base in C.ESTONIAN_ALPHABET:
        return 1, C.ESTONIAN_ALPHABET.index(base)
    return 2, ord(char)


def sort_key(text):
    folded = unicodedata.normalize('NFC', str(text or '')).casefold()
    ranks = []
    for token in _SORT_TOKEN_RE.findall(folded):
        if token.isdecimal():
            ranks.append((0, int(token)))
        elif token.isspace():
            ranks.append((0, -1))
        else:
            ranks.append(_letter_rank(token))
    while ranks and ranks[0] == (0, -1):
        ranks.pop(0)
    return ranks, folded
