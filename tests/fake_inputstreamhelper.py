# SPDX-License-Identifier: GPL-3.0-or-later
CALLS = []
AVAILABLE = [True]


class Helper:
    def __init__(self, protocol, drm=None):
        self.inputstream_addon = 'inputstream.adaptive'
        CALLS.append({'protocol': protocol, 'drm': drm})

    def check_inputstream(self):
        return AVAILABLE[0]


def reset():
    del CALLS[:]
    AVAILABLE[0] = True
