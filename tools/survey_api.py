# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import re
import sys
from urllib.parse import urlparse
from urllib.request import Request, urlopen

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resources.lib import categories, constants as C, menu
from resources.lib.api import ApiError, ErrApi
from resources.lib.helpers import default_headers

KNOWN_BLOCK_KEYS = {'data', 'header', 'headerUrl', 'highTimeline',
                    'liveBlock', 'manual', 'userBasedTimeline'}
KNOWN_MANUAL_KEYS = {'banner', 'highTimeline', 'userBasedTimeline',
                     'userBasedTimelineLimit', 'userBasedTimelineSource'}
KNOWN_TYPES = {'movie', 'episode', 'clip'} | set(C.FOLDER_TYPES) | \
    set(C.SKIP_TYPES)
PROGRAMME_TYPES = {'movie', 'episode', 'series', 'clip'}
FRONT_ENDS = ('jupiter.err.ee', 'lasteekraan.err.ee')
USED_HOSTS = {urlparse(value).netloc for name, value in vars(C).items()
              if name.startswith('EP_')}


def fetch_text(url):
    handle = urlopen(Request(url, headers=default_headers()), timeout=30)
    return handle.read().decode('utf-8', 'replace')


def bundle(host):
    base = 'https://%s/' % host
    scripts = set(re.findall(r'(?:main|chunk)-[A-Za-z0-9]+\.js',
                             fetch_text(base)))
    return '\n'.join(fetch_text(base + script) for script in sorted(scripts))


def programme_ids(category):
    return {item['id'] for item in categories.flatten_items(category)
            if item.get('type') in PROGRAMME_TYPES
            and item.get('hasActiveMedia')}


def offered():
    jupiter = C.DOMAINS[C.DEFAULT_DOMAIN]
    entries = menu.flat_entries(ErrApi(log=lambda m: None).get_menu(),
                                jupiter.get('section_fallbacks'))
    paths = [(C.DEFAULT_DOMAIN, entry['path'], entry['label'])
             for entry in entries]
    return paths + [(key, domain['path'], domain['label'])
                    for key, domain in C.DOMAINS.items() if domain.get('path')]


def survey_categories(findings, paths):
    print('== Categories')
    listed = {}
    for key, path, label in paths:
        try:
            category = ErrApi(domain=key, log=lambda m: None).get_category(
                path)
        except ApiError as exc:
            findings.append('category: %s/%s failed: %s' % (key, path, exc))
            continue
        titles = categories.flatten_items(category)
        listed.setdefault(key, set()).update(programme_ids(category))
        print('-- %s/%s "%s": %d titles' % (key, path, label, len(titles)))
        if not titles:
            findings.append('category: %s/%s lists no titles' % (key, path))
        for block in category.get('frontPage') or []:
            if isinstance(block, dict):
                survey_row(findings, '%s/%s' % (key, path), block)
    return listed


def survey_row(findings, where, block):
    manual = block['manual'] if isinstance(block.get('manual'), dict) else {}
    items = [i for i in block.get('data') or [] if isinstance(i, dict)]
    types = {i.get('type') or '?' for i in items}
    if block.get('liveBlock'):
        kind = 'live'
    elif block.get('userBasedTimeline') or manual.get('userBasedTimeline'):
        kind = 'personal'
    elif manual.get('banner'):
        kind = 'banner'
    else:
        kind = 'curated' if manual.get('highTimeline') else 'automatic'
    print('   %-9s %3d  %-44s %s' % (
        kind, len(items), (block.get('header') or '<untitled>')[:44],
        ','.join(sorted(types))))
    extra = set(block) - KNOWN_BLOCK_KEYS | \
        {'manual.' + k for k in set(manual) - KNOWN_MANUAL_KEYS}
    if extra:
        findings.append('row: %s "%s" has unknown keys %s' % (
            where, block.get('header'), sorted(extra)))
    if types - KNOWN_TYPES - {'?'}:
        findings.append('row: %s "%s" carries item types %s' % (
            where, block.get('header'), sorted(types - KNOWN_TYPES - {'?'})))


def survey_menus(findings, paths, listed):
    print('\n== Menus')
    sites = set()
    offered_paths = {(key, path) for key, path, _label in paths}
    for key, domain in C.DOMAINS.items():
        api = ErrApi(domain=key, log=lambda m: None)
        print('-- %s (menu %s)' % (key, domain['menu_id']))
        try:
            sections = api.get_menu()
        except ApiError as exc:
            findings.append('menu: %s failed: %s' % (key, exc))
            continue
        for section in sections:
            kids = section.get('kids') or []
            print('   %s -> %s' % (section.get('name'), section.get('link')))
            for item in kids or [section]:
                link = item.get('link') or ''
                if kids:
                    print('     %s -> %s' % (item.get('name'), link))
                host = urlparse(link).netloc if '//' in link else ''
                if host and host != domain['domain']:
                    sites.add(host)
                    if host not in USED_HOSTS:
                        findings.append('site: %s/%s links to %s' % (
                            key, item.get('name'), host))
                elif not host and link not in C.LIVE_LINKS and \
                        (key, link.strip('/')) not in offered_paths:
                    try:
                        category = api.get_category(link)
                    except ApiError as exc:
                        findings.append('menu: %s/%s -> %s failed: %s' % (
                            key, item.get('name'), link, exc))
                        continue
                    missing = programme_ids(category) - \
                        listed.get(key, set())
                    if missing:
                        findings.append(
                            'menu: %s/%s -> %s has %d programmes Saturn '
                            'lists nowhere' % (key, item.get('name'), link,
                                               len(missing)))
    return sites


def survey_endpoints(findings, sites):
    print('\n== Endpoints')
    sources = {}
    for host in FRONT_ENDS + tuple(sorted(sites)):
        try:
            sources[host] = bundle(host)
        except OSError as exc:
            findings.append('bundle: %s failed: %s' % (host, exc))
    for host, source in sources.items():
        calls = set(re.findall(r'/api/v?\d?/?[A-Za-z][A-Za-z0-9_/-]+',
                               source))
        calls |= {'/api' + path for path in
                  re.findall(r'baseUrl\}(/v\d/[^`]*)`', source)}
        print('-- %s: %d calls' % (host, len(calls)))
        for path in sorted(calls):
            print('     ' + path)
    everything = '\n'.join(sources.values())
    for name, value in sorted(vars(C).items()):
        if name.startswith('EP_'):
            method = urlparse(value).path.rstrip('/').rsplit('/', 1)[-1]
            if method not in everything:
                findings.append('endpoint: Saturn calls %s; no ERR front end '
                                'does' % urlparse(value).path)


def main():
    findings = []
    paths = offered()
    listed = survey_categories(findings, paths)
    sites = survey_menus(findings, paths, listed)
    survey_endpoints(findings, sites)
    print('\n== Findings (%d)' % len(findings))
    for finding in findings:
        print(' - ' + finding)


if __name__ == '__main__':
    main()
