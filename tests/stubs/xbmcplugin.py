# SPDX-License-Identifier: GPL-3.0-or-later
SORT_METHOD_UNSORTED = 'unsorted'
SORT_METHOD_LABEL = 'label'
SORT_METHOD_EPISODE = 'episode'
SORT_METHOD_VIDEO_YEAR = 'year'

DIRECTORY = []
RESOLVED = []
STATE = {'content': None, 'category': None, 'ended': None, 'end_calls': 0,
         'sort_methods': []}


def addDirectoryItems(handle, items, totalItems=0):
    DIRECTORY.extend({'url': url, 'listitem': listitem, 'is_folder': folder}
                     for url, listitem, folder in items)
    return True


def endOfDirectory(handle, succeeded=True):
    STATE['end_calls'] += 1
    if STATE['ended'] is None:
        STATE['ended'] = {'succeeded': succeeded}


def setContent(handle, content):
    STATE['content'] = content


def setPluginCategory(handle, category):
    STATE['category'] = category


def addSortMethod(handle, sortMethod, labelMask='', label2Mask=''):
    STATE['sort_methods'].append((sortMethod, labelMask))


def setResolvedUrl(handle, succeeded, listitem):
    RESOLVED.append({'succeeded': succeeded, 'listitem': listitem})


def reset():
    del DIRECTORY[:]
    del RESOLVED[:]
    STATE.update({'content': None, 'category': None, 'ended': None,
                  'end_calls': 0, 'sort_methods': []})
