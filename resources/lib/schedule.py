# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
import time

from .helpers import dicts, safe_int, strip_html, timestamp_to_human


def parse_schedule(entries):
    programmes = []
    for entry in dicts(entries):
        start = safe_int(entry.get('startTime'))
        if not start:
            continue
        programmes.append({
            'start': start,
            'end': safe_int(entry.get('endTime')),
            'title': (entry.get('name') or entry.get('programName')
                      or '').strip(),
            'series': (entry.get('seriesTitle') or '').strip(),
            'plot': strip_html(entry.get('lead') or ''),
            'content_id': safe_int(entry.get('contentId')) or None,
            'has_media': bool(entry.get('mediaExist')),
        })
    return programmes


def current_programme(programmes, now=None):
    now = time.time() if now is None else now
    for programme in programmes:
        if programme['start'] <= now < (programme['end'] or 0):
            return programme
    return None


def is_playable(programme):
    return bool(programme.get('has_media') and programme.get('content_id'))


def programme_label(programme):
    clock = timestamp_to_human(programme['start'], '%H:%M')
    title = programme['title'] or programme['series']
    return ('%s  %s' % (clock, title)).strip()
