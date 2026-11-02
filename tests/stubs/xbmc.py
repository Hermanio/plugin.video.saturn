# SPDX-License-Identifier: GPL-3.0-or-later
LOGDEBUG = 0
LOGINFO = 1
LOGERROR = 3

INSTALLED_ADDONS = {'inputstream.adaptive'}


def log(message, level=LOGINFO):
    return None


class Actor:
    def __init__(self, name='', role='', order=-1, thumbnail=''):
        self._name = name

    def getName(self):
        return self._name


class VideoStreamDetail:
    def __init__(self, width=0, height=0, aspect=0.0, duration=0, codec='',
                 stereomode='', language='', hdrtype=''):
        self.duration = duration


def getCondVisibility(condition):
    if condition.startswith('System.HasAddon('):
        return condition[len('System.HasAddon('):-1] in INSTALLED_ADDONS
    return False
