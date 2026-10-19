# SPDX-License-Identifier: GPL-3.0-or-later
import os

from resources.lib import constants as C

from .conftest import ADDON_DIR

MENU_DIR = os.path.join(ADDON_DIR, 'resources', 'images', 'menu')
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


def test_every_menu_icon_is_shipped_as_a_distinct_png():
    wanted = set(C.MENU_ICONS.values()) | set(C.CATEGORY_ICONS.values()) \
        | set(C.SECTION_ICONS.values()) | {C.DEFAULT_CATEGORY_ICON}
    shipped = sorted(os.listdir(MENU_DIR))
    assert wanted <= set(shipped), sorted(wanted - set(shipped))
    pictures = set()
    for name in shipped:
        with open(os.path.join(MENU_DIR, name), 'rb') as handle:
            picture = handle.read()
        assert picture.startswith(PNG_SIGNATURE), name
        pictures.add(picture)
    assert len(pictures) == len(shipped), 'two menu icons are identical'
