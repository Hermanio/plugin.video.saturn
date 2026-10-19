# SPDX-License-Identifier: GPL-3.0-or-later
import ast
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

from .conftest import ADDON_DIR

ADDON_ID = 'plugin.video.saturn'
LICENSE_ID = 'GPL-3.0-or-later'
LANGUAGES = ('resource.language.en_gb', 'resource.language.et_ee')
LIB_DIR = os.path.join(ADDON_DIR, 'resources', 'lib')


def read(*parts):
    return open(os.path.join(ADDON_DIR, *parts), encoding='utf-8').read()


def po_entries(language):
    text = read('resources', 'language', language, 'strings.po')
    assert 'Content-Type: text/plain; charset=UTF-8' in text
    entries = re.findall(r'msgctxt "#(\d+)"\nmsgid "(.*)"\nmsgstr "(.*)"',
                         text)
    assert len(entries) == text.count('msgctxt'), \
        '%s has a malformed entry' % language
    return [(int(sid), msgid, msgstr) for sid, msgid, msgstr in entries]


def lib_sources():
    return {name[:-3]: read('resources', 'lib', name)
            for name in sorted(os.listdir(LIB_DIR))
            if name.endswith('.py') and name != '__init__.py'}


@pytest.fixture(scope='module')
def root():
    return ET.parse(os.path.join(ADDON_DIR, 'addon.xml')).getroot()


@pytest.fixture(scope='module')
def meta(root):
    return root.find("extension[@point='xbmc.addon.metadata']")


def test_addon_id_is_the_one_kodi_installs(root):
    assert root.get('id') == ADDON_ID
    assert root.get('name') == 'Saturn'
    assert re.match(r'^\d+\.\d+\.\d+$', root.get('version'))


def test_the_plugin_is_the_only_entry_point_and_it_is_video(root):
    runnable = [ext for ext in root.findall('extension')
                if ext.get('point') != 'xbmc.addon.metadata']
    assert [ext.get('point') for ext in runnable] == [
        'xbmc.python.pluginsource']
    assert runnable[0].get('library') == 'addon.py'
    assert os.path.isfile(os.path.join(ADDON_DIR, 'addon.py'))
    assert 'video' in runnable[0].find('provides').text.split()


def test_the_metadata_the_kodi_repository_asks_for_is_there(root, meta):
    for tag in ('summary', 'description', 'license', 'platform', 'news',
                'website', 'source', 'email', 'language', 'disclaimer'):
        assert meta.find(tag) is not None, tag
    assert meta.find('email').text == 'kodi@ounapuu.ee'
    assert root.get('provider-name') == 'Herman Õunapuu'
    source = meta.find('source').text
    assert source == 'https://github.com/Hermanio/%s' % ADDON_ID
    assert meta.find('website').text != source
    assert {node.get('lang') for node in meta.findall('summary')} >= \
        {'en', 'et'}


def test_every_asset_exists(meta):
    assets = meta.find('assets')
    assert {node.tag for node in assets} >= {'icon', 'fanart', 'banner',
                                             'clearlogo'}
    for node in assets:
        assert os.path.isfile(os.path.join(ADDON_DIR, node.text)), node.text


def test_kodi_installs_an_engine_that_can_play_drm(root):
    imports = {imp.get('addon'): imp
               for imp in root.findall('requires/import')}
    adaptive = imports['inputstream.adaptive']
    assert adaptive.get('optional') is None
    assert adaptive.get('version') == '21.5.0'
    assert {'script.module.inputstreamhelper', 'xbmc.python'} <= set(imports)


def test_everything_is_licensed_gpl3_or_later(meta):
    assert meta.find('license').text == LICENSE_ID
    assert 'GNU GENERAL PUBLIC LICENSE' in read('LICENSE')
    assert 'Version 3' in read('LICENSE')
    assert LICENSE_ID in read('README.md')
    wrong = []
    for where in ('.', 'resources/lib', 'tests', 'tests/stubs', 'tools'):
        for name in sorted(os.listdir(os.path.join(ADDON_DIR, where))):
            if name.endswith('.py') and 'SPDX-License-Identifier: %s' \
                    % LICENSE_ID not in read(where, name)[:400]:
                wrong.append(os.path.join(where, name))
    assert not wrong, 'missing or wrong SPDX header: %s' % wrong


def test_every_shipped_python_file_opens_with_both_headers():
    header = ['# -*- coding: utf-8 -*-',
              '# SPDX-License-Identifier: %s' % LICENSE_ID]
    wrong = [os.path.join(where, name)
             for where in ('.', 'resources', 'resources/lib')
             for name in sorted(os.listdir(os.path.join(ADDON_DIR, where)))
             if name.endswith('.py')
             and read(where, name).splitlines()[:2] != header]
    assert not wrong, 'missing coding or SPDX header: %s' % wrong


def test_settings_are_well_formed():
    settings = ET.fromstring(read('resources', 'settings.xml')).findall(
        './/setting')
    valid_types = {'string', 'boolean', 'integer', 'number', 'list', 'slider',
                   'path', 'action'}
    for setting in settings:
        assert setting.get('id')
        assert setting.get('type') in valid_types, setting.get('id')


def test_no_setting_offers_an_empty_option_that_crashes_kodi():
    options = ET.fromstring(read('resources', 'settings.xml')).findall(
        './/option')
    assert options
    for option in options:
        assert (option.text or '').strip(), option.get('label')


def test_both_catalogues_define_the_same_strings_in_range():
    ids = {language: [sid for sid, _, _ in po_entries(language)]
           for language in LANGUAGES}
    english = ids[LANGUAGES[0]]
    assert english and len(english) == len(set(english))
    assert all(30000 <= sid <= 30299 for sid in english)
    assert set(ids[LANGUAGES[1]]) == set(english)


def test_english_is_the_source_and_estonian_is_complete():
    for sid, msgid, msgstr in po_entries('resource.language.en_gb'):
        assert msgid and msgstr == '', sid
    missing = [sid for sid, _msgid, msgstr in
               po_entries('resource.language.et_ee') if not msgstr.strip()]
    assert not missing, 'untranslated Estonian strings: %s' % missing


def test_every_string_is_defined_and_used():
    defined = {sid for sid, _, _ in po_entries(LANGUAGES[0])}
    called = set()
    mentioned = {int(i) for i in re.findall(
        r'\b(3\d{4})\b', read('resources', 'settings.xml'))}
    for source in lib_sources().values():
        called.update(int(i) for i in re.findall(r'localize\((\d+)', source))
        mentioned.update(int(i) for i in re.findall(r'\b(3\d{4})\b', source))
    assert called <= defined, 'undefined ids: %s' % sorted(called - defined)
    assert defined <= mentioned, 'unused ids: %s' % sorted(defined - mentioned)


def test_only_the_kodi_facing_modules_import_kodi():
    found = set()
    for name, source in lib_sources().items():
        for node in ast.walk(ast.parse(source)):
            modules = [a.name for a in node.names] \
                if isinstance(node, ast.Import) else \
                [node.module or ''] if isinstance(node, ast.ImportFrom) else []
            if any(module.startswith('xbmc') for module in modules):
                found.add(name)
    assert found == {'kodiutils', 'playqueue', 'router'}


def test_the_addon_never_names_itself_to_kodi():
    for name, source in lib_sources().items():
        assert not re.search(r'xbmcaddon\.Addon\(\s*id\s*=', source), name
        assert 'setInfo(' not in source, name
        assert not re.search(r'\.getSetting(?!s\()', source), name


def test_every_python_file_compiles():
    skip = {'.git', '__pycache__', '.venv', 'dist', '.pytest_cache'}
    for dirpath, dirnames, filenames in os.walk(ADDON_DIR):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for name in filenames:
            if name.endswith('.py'):
                path = os.path.join(dirpath, name)
                ast.parse(open(path, encoding='utf-8').read(), filename=path)


def test_every_python_file_follows_pep8():
    result = subprocess.run(
        [sys.executable, '-m', 'flake8', '--per-file-ignores=tools/*:E402',
         'addon.py', 'resources', 'tests', 'tools'],
        cwd=ADDON_DIR, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_no_fixture_carries_a_drm_token():
    fixtures = os.path.join(ADDON_DIR, 'tests', 'fixtures')
    leaked = [name for name in sorted(os.listdir(fixtures))
              if re.search(r'eyJ[\w-]+\.eyJ[\w-]+\.',
                           open(os.path.join(fixtures, name),
                                encoding='utf-8').read())]
    assert not leaked, leaked
