# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
from urllib.parse import urlsplit

from . import constants as C
from .helpers import (absolutize, dicts, safe_int, sort_key, strip_html,
                      timestamp_to_human)


def title_parts(item):
    heading = (item.get('heading') or '').strip()
    if (item.get('type') or '').lower() != 'episode':
        return '', heading
    show = heading.split('|')[0].strip()
    name = (item.get('subHeading') or '').strip()
    if not show or not name or name.lower() == show.lower():
        return '', heading
    return show, name


INHERITED = ('genre', 'cast', 'director', 'writer', 'country')


def _paragraphs(*parts):
    return '\n\n'.join(part for part in parts if part)


def inherit(meta, parent):
    if not parent:
        return meta
    for key in INHERITED:
        if not meta.get(key) and parent.get(key):
            meta[key] = parent[key]
    if parent.get('plot') and parent['plot'] not in meta.get('plot', ''):
        meta['plot'] = _paragraphs(meta.get('plot'), parent['plot'])
    return meta


def extract_metadata(main_content, parent=None):
    show, title = title_parts(main_content)
    plot = strip_html(main_content.get('body') or '')
    lead = strip_html(main_content.get('lead') or '')
    if lead and lead not in plot:
        plot = _paragraphs(lead, plot)
    sub = strip_html(main_content.get('subHeading') or '')
    if sub and sub != title and sub not in plot:
        plot = _paragraphs(plot, sub)
        lead = lead or sub

    premiered = timestamp_to_human(main_content.get('publicStart')
                                   or main_content.get('scheduleStart'),
                                   '%Y-%m-%d')
    meta = {
        'title': title,
        'plot': plot,
        'plotoutline': lead,
        'studio': 'ERR',
        'mediatype': media_type_for(main_content.get('type')),
    }
    if show and show != title:
        meta['tvshowtitle'] = show
    if premiered:
        meta['premiered'] = premiered
        meta['aired'] = premiered
        meta['year'] = safe_int(premiered[:4]) or None
    if meta['mediatype'] != 'episode':
        year = safe_int(main_content.get('year'))
        if year:
            meta['year'] = year
    if main_content.get('originalTitle'):
        meta['originaltitle'] = main_content['originalTitle']
    if main_content.get('country'):
        meta['country'] = main_content['country']
    season = safe_int(main_content.get('season'))
    episode = safe_int(main_content.get('episode'))
    if season:
        meta['season'] = season
    if episode:
        meta['episode'] = episode
    category = main_content.get('primaryCategory') or {}
    if isinstance(category, dict) and category.get('name'):
        meta['genre'] = category['name']
    meta.update(credits_of(main_content))
    return inherit({k: v for k, v in meta.items() if v}, parent)


def credits_of(main_content):
    found = {'director': [], 'writer': [], 'cast': []}
    for maker in dicts(main_content.get('makers')):
        name = (maker.get('name') or '').strip()
        field = C.MAKER_ROLES.get(maker.get('typeId'))
        if name and field and name not in found[field]:
            found[field].append(name)
    return found


MEDIA_TYPES = {'series': 'tvshow', 'episode': 'episode', 'movie': 'movie'}


def media_type_for(content_type):
    return MEDIA_TYPES.get((content_type or '').lower(), 'video')


def duration_of(media):
    return safe_int((media.get('mediaInfo') or {}).get('duration'))


MONTHS_ET = ('jaanuar', 'veebruar', 'märts', 'aprill', 'mai', 'juuni',
             'juuli', 'august', 'september', 'oktoober', 'november',
             'detsember')


def _order_key(entry):
    name = entry['name'].replace('.', '').strip().lower()
    if name.isdigit():
        return int(name)
    if name in MONTHS_ET:
        return MONTHS_ET.index(name)
    return None


def _sorted_if_complete(items, keys):
    if not items or any(key is None for key in keys):
        return list(items)
    return [item for _key, item in sorted(zip(keys, items),
                                          key=lambda pair: pair[0])]


def order_seasons(entries):
    return _sorted_if_complete(entries, [_order_key(e) for e in entries])


def order_contents(items):
    items = dicts(items)
    if items and all(safe_int(item.get('episode')) for item in items):
        return _sorted_if_complete(items, [
            (safe_int(item.get('season')), safe_int(item.get('episode')))
            for item in items])
    return _sorted_if_complete(items, [
        safe_int(item.get('publicStart') or item.get('scheduleStart'))
        or None for item in items])


def leaf_seasons(seasons, scope=None):
    leaves = []
    for season in seasons:
        if scope is not None and str(season['id']) != str(scope):
            continue
        if season['children']:
            leaves.extend(((season['id'], child['id']), child)
                          for child in season['children'])
        else:
            leaves.append(((season['id'], None), season))
    return leaves


def folder_metadata(parent, title, season=None):
    if not parent:
        return {}
    meta = dict(parent)
    meta['title'] = title
    meta.pop('episode', None)
    if season is None:
        meta.pop('season', None)
    else:
        meta['season'] = season
    return meta


def _season_block(page_data):
    raw = page_data.get('seasonList')
    return raw if isinstance(raw, dict) else {}


def _season_entries(items):
    return order_seasons([_season_entry(item) for item in dicts(items)])


def _season_entry(item):
    return {
        'id': item.get('id'),
        'name': str(item.get('name') or '').strip(),
        'first_content_id': item.get('firstContentId'),
        'contents': order_contents(item.get('contents') or []),
        'children': _season_entries(item.get('items')),
    }


def season_list(page_data):
    return _season_entries(_season_block(page_data).get('items'))


def season_list_type(page_data):
    return _season_block(page_data).get('type', '')


def find_season(seasons, season_id, sub_id=None):
    for season in seasons:
        if str(season['id']) != str(season_id):
            continue
        if sub_id is None:
            return season
        for child in season['children']:
            if str(child['id']) == str(sub_id):
                return child
        return None
    return None


def _heading_label(item):
    heading = (item.get('heading') or '').strip()
    sub = (item.get('subHeading') or '').strip()
    if sub and sub.lower() != heading.lower():
        return '%s - %s' % (heading, sub) if heading else sub
    return heading


def label_for(item):
    show, name = title_parts(item)
    label = '%s - %s' % (show, name) if show else _heading_label(item)
    season = safe_int(item.get('season'))
    episode = safe_int(item.get('episode'))
    if season and episode:
        return '%s (S%02dE%02d)' % (label, season, episode) if label else \
            'S%02dE%02d' % (season, episode)
    return label or str(item.get('id') or '')


def alphabetical(items):
    return sorted(items, key=lambda item: sort_key(label_for(item)))


def pick_media(main_content, prefer_audio=False):
    medias = dicts(main_content.get('medias'))
    if not medias:
        return None
    wanted = 'audio' if prefer_audio else 'video'
    for media in medias:
        if (media.get('type') or '') == wanted and not is_geo_blocked(media):
            return media
    for media in medias:
        if not is_geo_blocked(media):
            return media
    return medias[0]


def is_drm(media):
    return bool((media.get('restrictions') or {}).get('drm'))


def drm_config(media):
    servers = media.get('licenseServerUrl') or {}
    url = servers.get('widevine') if isinstance(servers, dict) else None
    token = media.get('jwt')
    if not url or not token:
        return None
    return {'url': url, 'token': token}


def is_geo_blocked(media):
    return bool((media.get('restrictions') or {}).get('geoBlock'))


def select_stream(media):
    src = media.get('src') or {}
    if not isinstance(src, dict):
        return '', ''
    orders = ((C.HLS_PRIORITY, 'hls'), (C.DASH_PRIORITY, 'mpd'))
    if is_drm(media):
        orders = orders[::-1]
    for keys, protocol in orders + ((('file',), 'file'),):
        for key in keys:
            if src.get(key):
                return absolutize(src[key]), protocol
    return '', ''


def live_is_audio(payload):
    return (payload.get('config') or {}).get('mediaType') == 'audio'


def live_drm(payload, session_id):
    drm = (payload.get('config') or {}).get('drm')
    if not isinstance(drm, dict):
        return None
    srcs = drm.get('srcs')
    manifest = srcs.get('dash') if isinstance(srcs, dict) else None
    config = drm_config({'licenseServerUrl': drm.get('licenseServerUrls'),
                         'jwt': drm.get('jwt')})
    if not manifest or config is None:
        return None
    parts = urlsplit(absolutize(manifest))
    config['manifest'] = parts._replace(
        path='/%s%s' % (session_id, parts.path)).geturl()
    return config


def subtitles_of(media, language=None):
    subs = []
    wanted = (language or '').lower()
    for entry in dicts(media.get('subtitles')):
        if not entry.get('src'):
            continue
        code = (entry.get('srclang') or '').lower()
        name = (entry.get('name') or '').lower()
        if wanted and wanted not in (code, name):
            continue
        subs.append(absolutize(entry['src']))
    if wanted and not subs:
        return subtitles_of(media, None)
    return subs
