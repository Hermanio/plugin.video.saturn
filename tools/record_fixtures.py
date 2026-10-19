# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resources.lib import categories, constants as C, content
from resources.lib.api import ErrApi

FIXTURE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'tests', 'fixtures')
UNREAD = {'rootContent', 'nextContent', 'parentContent', 'druidStats',
          'heroImage', 'horizontalPoster'}


def strip_unread(value):
    if isinstance(value, dict):
        return {key: '<redacted>' if key == 'jwt' and item
                else strip_unread(item)
                for key, item in value.items() if key not in UNREAD}
    if isinstance(value, list):
        return [strip_unread(item) for item in value]
    return value


def trim_category(category, blocks=6, per_block=6):
    front = []
    for block in (category.get('frontPage') or [])[:blocks]:
        front.append(dict(block, data=(block.get('data') or [])[:per_block]))
    return dict(category, frontPage=front)


def first_page(api, category_path, wanted):
    for item in categories.flatten_items(api.get_category(category_path)):
        page = api.get_content(item['id'])
        if wanted(item, page):
            return page
    raise SystemExit('nothing in %s fits a fixture today' % category_path)


def plain_hls_film(item, page):
    if item.get('type') != 'movie':
        return False
    media = content.pick_media(page['mainContent'])
    return media is not None and not content.is_drm(media) and \
        content.select_stream(media)[1] == 'hls'


def multi_season_series(item, page):
    seasons = (page.get('seasonList') or {}).get('items') or []
    media = content.pick_media(page['mainContent'])
    return item.get('type') == 'series' and len(seasons) >= 2 and \
        not (media and content.is_drm(media))


def monthly_programme(item, page):
    season_list = page.get('seasonList') or {}
    years = season_list.get('items') or []
    return season_list.get('type') == 'monthly' and years and \
        years[0].get('items')


def trim_series(page):
    season_list = page['seasonList']
    season_list['items'] = season_list['items'][:3]
    for season in season_list['items']:
        season['contents'] = (season.get('contents') or [])[:5]
    return page


def trim_monthly(page):
    season_list = page['seasonList']
    season_list['items'] = season_list['items'][:2]
    for year in season_list['items']:
        year['items'] = (year.get('items') or [])[:3]
        for month in year['items']:
            month['contents'] = (month.get('contents') or [])[:4]
    return page


def record(api):
    audio = next(item for item in categories.flatten_items(
        api.get_category('audio')) if item.get('hasActiveMedia'))
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    envelope = {'apiVersion': '2.0'}
    return {
        'menu.json': dict(envelope, data={'items': api.get_menu()}),
        'category_filmid.json': dict(envelope, data={
            'category': trim_category(api.get_category('filmid'))}),
        'content_movie.json': dict(envelope, data=first_page(
            api, 'filmid', plain_hls_film)),
        'content_series.json': dict(envelope, data=trim_series(first_page(
            api, 'sarjad', multi_season_series))),
        'content_monthly.json': dict(envelope, data=trim_monthly(first_page(
            api, 'v-saated', monthly_programme))),
        'content_audio.json': dict(envelope, data=api.get_content(
            audio['id'], C.AUDIO_ROOT_ID)),
        'radio_programmes.json': api.get_json(C.EP_RADIO_PROGRAMMES, {
            'active': 'true', 'sortOrder': 'asc', 'page': 1, 'limit': 8,
            'primaryCategoryIds[]': C.RADIO_STATION_IDS['vikerraadio']}),
        'search_video.json': {
            'video': api._search('', 1, 3, ['video'])['video']},
        'live_etv.json': api.get_live_media('etv'),
        'live_vikerraadio.json': api.get_live_media('vikerraadio'),
        'schedule_etv.json': [dict(entry, contents=[]) for entry in
                              api.get_schedule('etv', yesterday)[:10]],
    }


def main():
    fixtures = record(ErrApi(log=lambda m: None))
    for name, payload in sorted(fixtures.items()):
        path = os.path.join(FIXTURE_DIR, name)
        with open(path, 'w', encoding='utf-8') as handle:
            json.dump(strip_unread(payload), handle, ensure_ascii=False,
                      indent=1, sort_keys=True)
        print('%-28s %7.1f KB' % (name, os.path.getsize(path) / 1024.0))


if __name__ == '__main__':
    main()
