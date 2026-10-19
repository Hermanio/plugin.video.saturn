# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
import random
from urllib.parse import urlencode

import xbmcgui
import xbmcplugin

from . import content as content_mod
from . import kodiutils as ku
from .helpers import absolutize, extract_art, stream_headers

ADAPTIVE_ADDON = 'inputstream.adaptive'
LICENSE_TYPE = 'com.widevine.alpha'

MIME_BY_PROTOCOL = {
    'hls': 'application/x-mpegURL',
    'mpd': 'application/dash+xml',
}


def cancel(handle):
    xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())


def reject(handle, message):
    ku.notify(message, icon=xbmcgui.NOTIFICATION_ERROR)
    cancel(handle)


def build_list_item(label, art=None, metadata=None, playable=False):
    list_item = xbmcgui.ListItem(label=label, offscreen=True)
    if art:
        list_item.setArt(art)
    if metadata:
        ku.apply_info(list_item, metadata)
    if playable:
        list_item.setProperty('IsPlayable', 'true')
    return list_item


def apply_stream_headers(list_item, protocol):
    headers = stream_headers()
    list_item.setProperty('inputstream.adaptive.stream_headers', headers)
    list_item.setProperty('inputstream.adaptive.manifest_headers', headers)
    if protocol in MIME_BY_PROTOCOL:
        list_item.setMimeType(MIME_BY_PROTOCOL[protocol])
    list_item.setContentLookup(False)
    return list_item


def apply_drm(list_item, config):
    list_item.setProperty('inputstream.adaptive.drm_legacy', '%s|%s|%s' % (
        LICENSE_TYPE, config['url'],
        urlencode({'X-AxDRM-Message': config['token']})))


def configure_inputstream(list_item, protocol, drm=False):
    if protocol not in MIME_BY_PROTOCOL:
        return True
    if not drm:
        list_item.setProperty('inputstream', ADAPTIVE_ADDON)
        return True

    import inputstreamhelper
    helper = inputstreamhelper.Helper(protocol, drm='widevine')
    if not helper.check_inputstream():
        return False
    list_item.setProperty('inputstream', helper.inputstream_addon)
    return True


def make_playable_item(main_content, media, url, protocol,
                       subtitle_language=None, enable_subtitles=True,
                       enable_art=True):
    metadata = content_mod.extract_metadata(main_content)
    duration = content_mod.duration_of(media)
    if duration:
        metadata['duration'] = duration
    list_item = build_list_item(metadata.get('title', ''),
                                extract_art(main_content) if enable_art
                                else None, metadata,
                                playable=True)
    list_item.setPath(url)
    apply_stream_headers(list_item, protocol)

    if enable_subtitles:
        subs = content_mod.subtitles_of(media, subtitle_language)
        if subs:
            list_item.setSubtitles(subs)
    return list_item


def _play(handle, list_item, url, protocol, drm=False):
    ku.log('playing %s (%s, drm=%s)' % (url, protocol, drm))
    xbmcplugin.setResolvedUrl(handle, True, list_item)


def resolve(handle, main_content, prefer_audio=False, subtitle_language=None,
            enable_subtitles=True, enable_art=True):
    media = content_mod.pick_media(main_content, prefer_audio=prefer_audio)
    url, protocol = content_mod.select_stream(media) if media else ('', '')
    if not url:
        reject(handle, ku.localize(30200, 'No playable stream found'))
        return

    drm = content_mod.is_drm(media)
    drm_settings = content_mod.drm_config(media) if drm else None
    if drm and drm_settings is None:
        reject(handle, ku.localize(
            30203, 'ERR did not allow this title to play here'))
        return
    list_item = make_playable_item(main_content, media, url, protocol,
                                   subtitle_language=subtitle_language,
                                   enable_subtitles=enable_subtitles,
                                   enable_art=enable_art)
    if not configure_inputstream(list_item, protocol, drm=drm):
        reject(handle, ku.localize(30202,
                                   'Widevine is required for this stream'))
        return
    if drm:
        apply_drm(list_item, drm_settings)
    _play(handle, list_item, url, protocol, drm)


def live_session_id():
    return str(random.randint(10 ** 13, 10 ** 14 - 1))


def resolve_live(handle, label, payload):
    info = {'title': label, 'studio': 'ERR'}
    audio_only = content_mod.live_is_audio(payload)
    if not audio_only:
        info['mediatype'] = 'video'
    list_item = build_list_item(label, metadata=info, playable=True)
    drm = None if audio_only else content_mod.live_drm(payload,
                                                       live_session_id())
    if drm and configure_inputstream(list_item, 'mpd', drm=True):
        url, protocol = drm['manifest'], 'mpd'
        apply_drm(list_item, drm)
    else:
        url, protocol = absolutize(payload['src']), 'hls'
        if not audio_only:
            list_item.setProperty('inputstream', ADAPTIVE_ADDON)
    list_item.setPath(url)
    apply_stream_headers(list_item, protocol)
    list_item.setProperty('IsLive', 'true')
    _play(handle, list_item, url, protocol, drm=protocol == 'mpd')
