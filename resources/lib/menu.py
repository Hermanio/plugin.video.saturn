# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
from collections import Counter

from . import constants as C
from .helpers import dicts


def _listed_kids(section, fallbacks):
    kids = section.get('kids')
    if kids:
        return kids
    known = (fallbacks or {}).get((section.get('name') or '').lower(), ())
    return [{'name': name, 'link': link} for name, link in known]


def section_children(section, fallbacks=None):
    children = []
    for kid in dicts(_listed_kids(section, fallbacks)):
        link = kid.get('link') or ''
        if link in C.LIVE_LINKS:
            continue
        children.append({'name': kid.get('name') or '',
                         'path': link.strip('/')})
    return children


def flat_entries(sections, fallbacks=None):
    entries = []
    seen = set()
    for section in sections or []:
        name = section.get('name') or ''
        for child in section_children(section, fallbacks):
            path = child['path']
            if not path or path in seen:
                continue
            seen.add(path)
            entries.append({'label': child['name'], 'path': path,
                            'section': name})
    return _qualify_shared_labels(entries)


def _qualify_shared_labels(entries):
    counts = Counter(entry['label'] for entry in entries)
    for entry in entries:
        if counts[entry['label']] > 1 and entry['section']:
            entry['label'] = '%s (%s)' % (entry['label'], entry['section'])
    return entries


def is_audio(section_name):
    return (section_name or '').lower() == 'audio'
