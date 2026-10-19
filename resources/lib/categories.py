# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
from . import constants as C
from .helpers import dicts


def _editorial_flags(block):
    manual = block.get('manual')
    return manual if isinstance(manual, dict) else {}


def category_blocks(category):
    blocks = []
    for index, block in enumerate(category.get('frontPage') or []):
        if not isinstance(block, dict):
            continue
        if block.get('userBasedTimeline') or block.get('liveBlock'):
            continue
        header = (block.get('header') or '').strip()
        items = dicts(block.get('data'))
        if not items:
            continue
        flags = _editorial_flags(block)
        blocks.append({
            'index': index,
            'header': header,
            'items': items,
            'banner': bool(flags.get('banner')),
        })
    return blocks


def _implicit_blocks(category):
    items = dicts(category.get('items'))
    return [{'items': items}] if items else []


def block_at(category, index):
    front = category.get('frontPage') or []
    index = int(index)
    block = front[index] if 0 <= index < len(front) else {}
    if not isinstance(block, dict):
        block = {}
    items = dicts(block.get('data'))
    return items, bool(_editorial_flags(block).get('highTimeline'))


def flatten_items(category):
    seen = set()
    flat = []
    for block in category_blocks(category) or _implicit_blocks(category):
        for item in block['items']:
            key = item.get('id')
            if key in seen:
                continue
            seen.add(key)
            flat.append(item)
    return flat


def radio_programmes(results):
    return [{
        'id': result['id'],
        'type': 'series',
        'heading': result.get('heading') or '',
        'photos': [{'photoUrlOriginal': C.PHOTO_BASE + result['photo']}]
        if result.get('photo') else [],
    } for result in dicts(results) if result.get('id')]
