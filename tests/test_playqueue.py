# SPDX-License-Identifier: GPL-3.0-or-later
import re

import pytest
import xbmcgui
import xbmcplugin

from resources.lib import content
from resources.lib import playqueue
from resources.lib.helpers import extract_art

HANDLE = 7

DRM_MEDIA = {
    'type': 'video', 'restrictions': {'drm': True}, 'jwt': 'TOKEN123',
    'licenseServerUrl': {'widevine':
                         'https://drm-widevine-licensing.axprod.net/Acquire'},
    'src': {'dashNew': '//vod.err.ee/dash/drm/x/manifest.mpd'},
}
TV = {'src': '//live.err.ee/live/etv.m3u8', 'config': {'mediaType': 'video'}}
DRM_TV = dict(TV, config={'mediaType': 'video', 'drm': {
    'srcs': {'dash': 'https://live.err.ee/etv/etv.isml/manifest.mpd'},
    'licenseServerUrls': {'widevine': DRM_MEDIA['licenseServerUrl'][
        'widevine']},
    'jwt': 'LIVE456'}})
RADIO = {'src': '//live.err.ee/live/vikerraadio.m3u8',
         'config': {'mediaType': 'audio'}}


def resolved():
    return xbmcplugin.RESOLVED[0]['listitem']


def succeeded():
    return xbmcplugin.RESOLVED[0]['succeeded']


def test_a_row_carries_its_label_metadata_and_art(movie):
    item = playqueue.build_list_item('x', extract_art(movie),
                                     content.extract_metadata(movie))
    info = item.getVideoInfoTag().info
    assert item.label == 'x'
    assert info['studio'] == ['ERR'] and info['title'] and info['mediatype']
    assert item.art
    assert all(url.startswith('https://') for url in item.art.values())
    assert item.getProperty('IsPlayable') == ''
    playable = playqueue.build_list_item('y', playable=True)
    assert playable.getProperty('IsPlayable') == 'true'


@pytest.mark.parametrize('protocol,mimetype', [
    ('hls', 'application/x-mpegURL'),
    ('mpd', 'application/dash+xml'),
    ('file', ''),
])
def test_every_stream_carries_errs_headers(protocol, mimetype):
    item = xbmcgui.ListItem()
    playqueue.apply_stream_headers(item, protocol)
    for key in ('stream_headers', 'manifest_headers'):
        assert 'jupiter.err.ee' in item.getProperty(
            'inputstream.adaptive.' + key)
    assert item.mimetype == mimetype
    assert item.content_lookup is False


def test_a_plain_film_plays_through_adaptive_with_nothing_extra(
        movie, with_inputstreamhelper):
    playqueue.resolve(HANDLE, movie)
    assert succeeded() is True
    item = resolved()
    assert item.getPath().startswith('https://vod.err.ee/')
    assert item.getProperty('IsPlayable') == 'true'
    assert item.getProperty('inputstream') == 'inputstream.adaptive'
    assert item.getVideoInfoTag().info['duration'] == 4235
    assert item.subtitles
    assert all(s.startswith('https://') for s in item.subtitles)
    for key in ('manifest_type', 'license_key', 'license_type',
                'drm_legacy'):
        assert item.getProperty('inputstream.adaptive.' + key) == '', key
    assert with_inputstreamhelper.CALLS == []


def test_a_progressive_file_plays_with_errs_headers():
    main = {'heading': 'x', 'medias': [
        {'type': 'video', 'src': {'file': '//vod.err.ee/file/vod/1.mp4'}}]}
    playqueue.resolve(HANDLE, main)
    assert succeeded() is True
    assert resolved().getPath().endswith('.mp4')
    assert resolved().content_lookup is False


@pytest.mark.parametrize('medias', [
    [],
    [{'type': 'video', 'src': {}}],
    [{'type': 'video', 'restrictions': {'drm': True},
      'src': {'dashNew': '//vod.err.ee/dash/drm/x/manifest.mpd'}}],
])
def test_a_title_that_cannot_play_says_so(medias, with_inputstreamhelper):
    playqueue.resolve(HANDLE, {'heading': 'x', 'medias': medias})
    assert succeeded() is False
    assert xbmcgui.NOTIFICATIONS[0]['icon'] == xbmcgui.NOTIFICATION_ERROR


def test_a_geoblocked_title_is_still_tried_without_an_error():
    main = {'heading': 'x', 'medias': [
        {'type': 'video', 'restrictions': {'geoBlock': True},
         'src': {'hls': '//vod.err.ee/a/master.m3u8'}}]}
    playqueue.resolve(HANDLE, main)
    assert succeeded() is True
    assert not xbmcgui.NOTIFICATIONS


def test_an_unblocked_media_is_preferred_to_a_blocked_one():
    main = {'heading': 'x', 'medias': [
        {'type': 'video', 'restrictions': {'geoBlock': True},
         'src': {'hls': '//vod.err.ee/blocked/master.m3u8'}},
        {'type': 'video', 'src': {'hls': '//vod.err.ee/open/master.m3u8'}}]}
    playqueue.resolve(HANDLE, main)
    assert succeeded() is True
    assert '/open/' in resolved().getPath()


def test_audio_plays_the_audio_media_of_a_programme():
    main = {'heading': 'x', 'medias': [
        {'type': 'video', 'src': {'hls': '//vod.err.ee/v/master.m3u8'}},
        {'type': 'audio', 'src': {'hls': '//vod.err.ee/a/master.m3u8'}}]}
    playqueue.resolve(HANDLE, main, prefer_audio=True)
    assert '/a/' in resolved().getPath()


def test_a_drm_title_gets_widevine_and_errs_licence(with_inputstreamhelper):
    main = {'heading': 'x', 'medias': [dict(DRM_MEDIA)]}
    playqueue.resolve(HANDLE, main)
    assert succeeded() is True
    item = resolved()
    assert item.getProperty('inputstream') == 'inputstream.adaptive'
    assert with_inputstreamhelper.CALLS[0]['drm'] == 'widevine'
    assert item.getProperty('inputstream.adaptive.license_key') == ''
    keysystem, url, headers = item.getProperty(
        'inputstream.adaptive.drm_legacy').split('|')
    assert keysystem == 'com.widevine.alpha'
    assert url == DRM_MEDIA['licenseServerUrl']['widevine']
    assert headers == 'X-AxDRM-Message=TOKEN123'


def test_a_drm_title_without_widevine_says_so(with_inputstreamhelper):
    with_inputstreamhelper.AVAILABLE[0] = False
    playqueue.resolve(HANDLE, {'medias': [dict(DRM_MEDIA)]})
    assert succeeded() is False
    assert 'Widevine' in xbmcgui.NOTIFICATIONS[0]['message']


def test_a_drm_title_err_gave_no_licence_for_blames_err(
        with_inputstreamhelper):
    media = dict(DRM_MEDIA, jwt=None)
    playqueue.resolve(HANDLE, {'medias': [media]})
    assert succeeded() is False
    assert 'ERR did not allow' in xbmcgui.NOTIFICATIONS[0]['message']
    assert with_inputstreamhelper.CALLS == []


def test_live_tv_plays_through_adaptive(
        with_inputstreamhelper):
    playqueue.resolve_live(HANDLE, 'ETV', TV)
    assert succeeded() is True
    item = resolved()
    assert item.getProperty('IsLive') == 'true'
    assert item.getProperty('inputstream') == 'inputstream.adaptive'
    assert item.getProperty('inputstream.adaptive.manifest_type') == ''
    assert item.getVideoInfoTag().info['mediatype'] == 'video'
    assert with_inputstreamhelper.CALLS == []


def test_live_tv_plays_errs_widevine_stream_when_it_offers_one(
        with_inputstreamhelper):
    playqueue.resolve_live(HANDLE, 'ETV', DRM_TV)
    assert succeeded() is True
    item = resolved()
    assert re.match(r'^https://live\.err\.ee/\d{14}/etv/etv\.isml/'
                    r'manifest\.mpd$', item.getPath())
    assert item.getProperty('IsLive') == 'true'
    assert item.getProperty('inputstream') == 'inputstream.adaptive'
    assert with_inputstreamhelper.CALLS[0] == {'protocol': 'mpd',
                                               'drm': 'widevine'}
    assert item.getProperty('inputstream.adaptive.drm_legacy').endswith(
        '|X-AxDRM-Message=LIVE456')


def test_live_tv_without_widevine_falls_back_to_the_open_stream(
        with_inputstreamhelper):
    with_inputstreamhelper.AVAILABLE[0] = False
    playqueue.resolve_live(HANDLE, 'ETV', DRM_TV)
    assert succeeded() is True
    item = resolved()
    assert item.getPath() == 'https://live.err.ee/live/etv.m3u8'
    assert item.getProperty('inputstream') == 'inputstream.adaptive'
    assert item.getProperty('inputstream.adaptive.drm_legacy') == ''


def test_live_radio_plays_in_kodi_itself_as_audio(with_inputstreamhelper):
    playqueue.resolve_live(HANDLE, 'Vikerraadio', RADIO)
    assert succeeded() is True
    item = resolved()
    assert item.getProperty('IsLive') == 'true'
    assert item.getProperty('inputstream') == ''
    info = item.getVideoInfoTag().info
    assert info['title'] == 'Vikerraadio' and 'mediatype' not in info
    assert with_inputstreamhelper.CALLS == []
