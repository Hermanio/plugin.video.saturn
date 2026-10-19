# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
import os

import xbmc
import xbmcaddon
import xbmcgui

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_ICON = ADDON.getAddonInfo('icon')
ADDON_FANART = ADDON.getAddonInfo('fanart')
MENU_IMAGE_DIR = os.path.join(ADDON.getAddonInfo('path'), 'resources',
                              'images', 'menu')


def image(name):
    return os.path.join(MENU_IMAGE_DIR, name)


def log(message, level=xbmc.LOGINFO):
    xbmc.log('[%s] %s' % (ADDON_ID, message), level)


def debug(message):
    log(message, xbmc.LOGDEBUG)


def error(message):
    log(message, xbmc.LOGERROR)


def localize(string_id, default=''):
    return ADDON.getLocalizedString(string_id) or default


def get_setting(key):
    return ADDON.getSettings().getString(key)


def get_setting_bool(key):
    return ADDON.getSettings().getBool(key)


def notify(message, icon=xbmcgui.NOTIFICATION_INFO):
    xbmcgui.Dialog().notification(ADDON_NAME, message, icon, 4000)


def get_search_phrase(heading):
    return (xbmcgui.Dialog().input(heading,
                                   type=xbmcgui.INPUT_ALPHANUM) or '').strip()


INFO_SETTERS = (
    ('title', 'setTitle', False), ('originaltitle', 'setOriginalTitle', False),
    ('plot', 'setPlot', False), ('plotoutline', 'setPlotOutline', False),
    ('studio', 'setStudios', True), ('genre', 'setGenres', True),
    ('director', 'setDirectors', True), ('country', 'setCountries', True),
    ('writer', 'setWriters', True), ('mediatype', 'setMediaType', False),
    ('premiered', 'setPremiered', False), ('aired', 'setFirstAired', False),
    ('year', 'setYear', False), ('season', 'setSeason', False),
    ('episode', 'setEpisode', False), ('duration', 'setDuration', False),
    ('tvshowtitle', 'setTvShowTitle', False),
)


def apply_info(list_item, metadata):
    tag = list_item.getVideoInfoTag()
    for key, setter, is_list in INFO_SETTERS:
        if key in metadata:
            value = metadata[key]
            if is_list and not isinstance(value, list):
                value = [value]
            getattr(tag, setter)(value)
    if metadata.get('cast'):
        tag.setCast([xbmc.Actor(name, '', index, '')
                     for index, name in enumerate(metadata['cast'])])
