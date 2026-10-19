# SPDX-License-Identifier: GPL-3.0-or-later
import re

INPUT_ALPHANUM = 0

NOTIFICATION_INFO = 'info'
NOTIFICATION_ERROR = 'error'

NOTIFICATIONS = []
DIALOGS = []
REJECTED_INFO = []
INPUT_TEXT = ['']

VIDEO_MEDIA_TYPES = {'video', 'set', 'musicvideo', 'movie', 'tvshow',
                     'season', 'episode'}


SETTERS = {
    'setTitle': ('title', str),
    'setOriginalTitle': ('originaltitle', str),
    'setPlot': ('plot', str),
    'setPlotOutline': ('plotoutline', str),
    'setTvShowTitle': ('tvshowtitle', str),
    'setStudios': ('studio', list),
    'setGenres': ('genre', list),
    'setDirectors': ('director', list),
    'setCountries': ('country', list),
    'setWriters': ('writer', list),
    'setYear': ('year', int),
    'setSeason': ('season', int),
    'setEpisode': ('episode', int),
    'setDuration': ('duration', int),
}


def _accepts(value, types, setter):
    if isinstance(value, types):
        return True
    REJECTED_INFO.append('%s(%r): expected %s, got %s'
                         % (setter, value, types, type(value).__name__))
    return False


class InfoTagVideo:
    def __init__(self):
        self.info = {}

    def __getattr__(self, setter):
        if setter not in SETTERS:
            raise AttributeError(setter)
        key, types = SETTERS[setter]

        def set_value(value):
            if _accepts(value, types, setter):
                self.info[key] = value
        return set_value

    def _set_date(self, key, value, setter):
        if not _accepts(value, str, setter):
            return
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', value):
            REJECTED_INFO.append('%s(%r): expected YYYY-MM-DD'
                                 % (setter, value))
            return
        self.info[key] = value

    def setPremiered(self, value):
        self._set_date('premiered', value, 'setPremiered')

    def setFirstAired(self, value):
        self._set_date('aired', value, 'setFirstAired')

    def setMediaType(self, value):
        if not _accepts(value, str, 'setMediaType'):
            return
        if value not in VIDEO_MEDIA_TYPES:
            REJECTED_INFO.append('setMediaType(%r): not a video media type'
                                 % value)
            return
        self.info['mediatype'] = value

    def setCast(self, value):
        if not _accepts(value, list, 'setCast'):
            return
        import xbmc
        for entry in value:
            if not isinstance(entry, xbmc.Actor):
                REJECTED_INFO.append('setCast(%r): expected xbmc.Actor'
                                     % (entry,))
                return
        self.info['cast'] = [a.getName() for a in value]


class ListItem:
    def __init__(self, label='', path='', offscreen=False):
        self.label = label
        self.path = path
        self.art = {}
        self.properties = {}
        self.subtitles = []
        self.mimetype = ''
        self.content_lookup = None
        self._video_tag = InfoTagVideo()

    def setArt(self, art):
        self.art.update(art)

    def getVideoInfoTag(self):
        return self._video_tag

    def setProperty(self, key, value):
        self.properties[key] = value

    def getProperty(self, key):
        return self.properties.get(key, '')

    def setPath(self, path):
        self.path = path

    def getPath(self):
        return self.path

    def setSubtitles(self, subtitles):
        self.subtitles = list(subtitles)

    def setMimeType(self, mimetype):
        self.mimetype = mimetype

    def setContentLookup(self, enabled):
        self.content_lookup = enabled


class Dialog:
    def notification(self, heading, message, icon=NOTIFICATION_INFO,
                     time=5000):
        NOTIFICATIONS.append({'heading': heading, 'message': message,
                              'icon': icon, 'time': time})

    def input(self, heading, defaultt='', type=INPUT_ALPHANUM, **_kwargs):
        DIALOGS.append({'heading': heading, 'input': True})
        return INPUT_TEXT[0]


def reset():
    del NOTIFICATIONS[:]
    del DIALOGS[:]
    del REJECTED_INFO[:]
    INPUT_TEXT[0] = ''
