# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

import pytest

from .conftest import ADDON_DIR

pytestmark = pytest.mark.compliance

ADDON_ID = 'plugin.video.saturn'
PACKAGE_SH = os.path.join(ADDON_DIR, 'package.sh')


@pytest.fixture(scope='module')
def built_zip(tmp_path_factory):
    out_dir = tmp_path_factory.mktemp('dist')
    result = subprocess.run([PACKAGE_SH, str(out_dir)], capture_output=True,
                            text=True, cwd=ADDON_DIR)
    assert result.returncode == 0, result.stderr
    zips = [p for p in os.listdir(str(out_dir)) if p.endswith('.zip')]
    assert len(zips) == 1, zips
    return os.path.join(str(out_dir), zips[0])


@pytest.fixture(scope='module')
def extracted(built_zip, tmp_path_factory):
    target = tmp_path_factory.mktemp('extracted')
    with zipfile.ZipFile(built_zip) as archive:
        archive.extractall(str(target))
    return os.path.join(str(target), ADDON_ID)


def test_zip_is_named_for_the_version_in_addon_xml(built_zip):
    version = ET.parse(os.path.join(ADDON_DIR, 'addon.xml')).getroot().get(
        'version')
    assert os.path.basename(built_zip) == '%s-%s.zip' % (ADDON_ID, version)
    assert zipfile.ZipFile(built_zip).testzip() is None


def shipped_files():
    script = open(PACKAGE_SH, encoding='utf-8').read()
    shipped = re.search(r'SHIPPED=\(([^)]*)\)', script).group(1).split()
    found = set()
    for entry in shipped:
        path = os.path.join(ADDON_DIR, entry)
        if os.path.isfile(path):
            found.add(entry)
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = [d for d in dirnames if d != '__pycache__']
            found.update(os.path.relpath(os.path.join(dirpath, name),
                                         ADDON_DIR) for name in filenames
                         if not name.endswith('.pyc'))
    return {'%s/%s' % (ADDON_ID, name) for name in found}


def test_zip_holds_one_folder_with_exactly_the_shipped_files(built_zip):
    names = zipfile.ZipFile(built_zip).namelist()
    assert {name.split('/')[0] for name in names} == {ADDON_ID}
    assert {n for n in names if not n.endswith('/')} == shipped_files()


def test_zip_includes_every_file_addon_xml_names(built_zip):
    root = ET.parse(os.path.join(ADDON_DIR, 'addon.xml')).getroot()
    names = set(zipfile.ZipFile(built_zip).namelist())
    wanted = [ext.get('library') for ext in root.findall('extension')
              if ext.get('library')]
    wanted += [asset.text for asset in root.find(
        "extension[@point='xbmc.addon.metadata']/assets")]
    for name in wanted:
        assert '%s/%s' % (ADDON_ID, name) in names, name


def test_the_same_source_builds_the_same_zip(tmp_path_factory):
    digests = set()
    for _ in range(2):
        out_dir = tmp_path_factory.mktemp('repeat')
        subprocess.run([PACKAGE_SH, str(out_dir)], capture_output=True,
                       check=True, cwd=ADDON_DIR)
        zip_path = os.path.join(str(out_dir), os.listdir(str(out_dir))[0])
        with open(zip_path, 'rb') as handle:
            digests.add(hashlib.sha256(handle.read()).hexdigest())
    assert len(digests) == 1


def test_kodi_addon_checker_clean(extracted):
    result = subprocess.run(
        [sys.executable, '-m', 'kodi_addon_checker', '--branch=omega',
         extracted],
        capture_output=True, text=True)
    output = result.stdout + result.stderr
    output = re.sub(r'\x1b\[[0-9;]*m', '', output)
    assert 'PO files are valid' in output, 'the checker never ran:\n' + output
    problems = [line for line in output.splitlines()
                if line.startswith('ERROR:') or line.startswith('WARN:')]
    assert not [p for p in problems if p.startswith('ERROR:')], \
        'addon checker errors:\n' + '\n'.join(problems)

    source = ET.parse(os.path.join(ADDON_DIR, 'addon.xml')).getroot().find(
        "extension[@point='xbmc.addon.metadata']/source").text
    allowed = ('WARN: 404 Client Error: Not Found for url: %s' % source,)
    unexpected = [p for p in problems
                  if not p.startswith(allowed)
                  and not p.startswith('WARN: We found no problems and')]
    assert not unexpected, \
        'addon checker complaints:\n' + '\n'.join(unexpected)
