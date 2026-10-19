# SPDX-License-Identifier: GPL-3.0-or-later
import os

DEFAULT_SETTINGS = {
    'preferredLanguage': 'any',
    'enableImages': 'true',
    'enableSubtitles': 'true',
}
SETTINGS = dict(DEFAULT_SETTINGS)

_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

INFO = {
    'id': 'plugin.video.saturn',
    'name': 'Saturn',
    'path': _ROOT,
    'icon': os.path.join(_ROOT, 'icon.png'),
    'fanart': os.path.join(_ROOT, 'fanart.jpg'),
}


class Addon:
    def getAddonInfo(self, key):
        return INFO.get(key, '')

    def getSettings(self):
        return Settings()

    def getLocalizedString(self, string_id):
        return ''


class Settings:
    def getString(self, key):
        return SETTINGS.get(key, '')

    def getBool(self, key):
        return str(SETTINGS.get(key, '')).lower() in ('true', '1', 'yes')


def reset():
    SETTINGS.clear()
    SETTINGS.update(DEFAULT_SETTINGS)
