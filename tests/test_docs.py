# SPDX-License-Identifier: GPL-3.0-or-later
import os
import re
import subprocess
import xml.etree.ElementTree as ET

import pytest

from .conftest import ADDON_DIR

ADDON_ID = 'plugin.video.saturn'


def read(*parts):
    return open(os.path.join(ADDON_DIR, *parts), encoding='utf-8').read()


@pytest.fixture(scope='module')
def version():
    manifest = ET.parse(os.path.join(ADDON_DIR, 'addon.xml'))
    return manifest.getroot().get('version')


def test_news_opens_with_the_version(version):
    meta = ET.parse(os.path.join(ADDON_DIR, 'addon.xml')).getroot().find(
        "extension[@point='xbmc.addon.metadata']")
    news = meta.find('news').text
    assert news.startswith('%s - ' % version)
    assert '\n' not in news and '&' not in news, \
        'the release workflow reads <news> as one line of plain text'


def test_readme_does_not_hardcode_a_version():
    stale = re.findall(r'%s-\d+\.\d+\.\d+\.zip' % re.escape(ADDON_ID),
                       read('README.md'))
    assert not stale, stale


def test_readme_installs_from_the_zip_only():
    install = read('README.md').split('## Installing')[1].split('\n## ')[0]
    assert 'Install from zip file' in install
    for banned in ('cp -r', '~/.kodi/addons', '%APPDATA%'):
        assert banned not in install, banned


def test_readme_settings_table_matches_the_settings_dialog():
    labels = dict(re.findall(r'msgctxt "#(\d+)"\nmsgid "([^"]*)"',
                             read('resources', 'language',
                                  'resource.language.en_gb', 'strings.po')))
    settings = ET.parse(os.path.join(ADDON_DIR, 'resources', 'settings.xml'))
    expected = [labels[node.get('label')]
                for node in settings.getroot().findall('.//setting')]

    table = read('README.md').split('## Settings')[1].split('\n## ')[0]
    rows = [line.split('|')[1].strip() for line in table.splitlines()
            if line.startswith('|')][2:]
    assert rows == expected, '%s != %s' % (rows, expected)


def test_readme_documents_every_test_and_package_command():
    readme = read('README.md')
    for command in ('./run-tests.sh', './package.sh'):
        assert command in readme, command


def test_tests_readme_names_real_test_files():
    named = set(re.findall(r'`(test_[a-z_]+\.py)`',
                           read('tests', 'README.md')))
    assert named, 'tests/README.md names no test files'
    for name in sorted(named):
        assert os.path.isfile(os.path.join(ADDON_DIR, 'tests', name)), name


def _publish(tmp_path, tag):
    (tmp_path / 'addon.xml').write_text(
        '<addon version="1.2.3"><news>1.2.3 - Better.</news></addon>')
    fake = tmp_path / 'bin'
    fake.mkdir()
    (fake / 'gh').write_text('#!/bin/sh\nprintf "%s\\0" "$@" > "$GH_ARGS"\n')
    (fake / 'gh').chmod(0o755)
    (tmp_path / 'dist').mkdir()
    (tmp_path / 'dist' / 'plugin.video.saturn-1.2.3.zip').write_text('zip')
    workflow = read('.github', 'workflows', 'release.yml').splitlines()
    step = workflow[workflow.index('      - name: Publish the zip'):]
    run = step[step.index('        run: |') + 1:]
    env = dict(os.environ, GITHUB_REF_NAME=tag,
               GH_ARGS=str(tmp_path / 'gh.args'),
               PATH='%s:%s' % (fake, os.environ['PATH']))
    result = subprocess.run(
        ['bash', '-euo', 'pipefail', '-c',
         '\n'.join(line[10:] for line in run)],
        capture_output=True, text=True, cwd=str(tmp_path), env=env)
    args = tmp_path / 'gh.args'
    return result, args.read_text().split('\0')[:-1] if args.exists() else []


def test_a_release_carries_the_zip_and_the_news(tmp_path):
    result, args = _publish(tmp_path, 'v1.2.3')
    assert result.returncode == 0, result.stdout + result.stderr
    assert args[:4] == ['release', 'create', 'v1.2.3',
                        'dist/plugin.video.saturn-1.2.3.zip']
    assert args[args.index('--title') + 1] == 'Saturn 1.2.3'
    assert args[args.index('--notes') + 1] == '1.2.3 - Better.'


def test_a_tag_that_disagrees_with_addon_xml_publishes_nothing(tmp_path):
    result, args = _publish(tmp_path, 'v9.9.9')
    assert result.returncode != 0
    assert 'does not match addon.xml' in result.stdout
    assert args == []
