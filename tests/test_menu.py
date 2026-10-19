# SPDX-License-Identifier: GPL-3.0-or-later
from resources.lib import constants as C
from resources.lib import menu

JUPITER_FALLBACKS = C.DOMAINS['jupiter']['section_fallbacks']


def sections(fixture):
    return fixture['data']['items']


def labelled(entries):
    return {entry['label']: entry for entry in entries}


def test_menu_links_become_paths_and_live_links_are_left_to_the_live_menu(
        audio_tab_menu_fixture):
    video, audio = sections(audio_tab_menu_fixture)
    kids = {k['name']: k for k in menu.section_children(video)}
    for kid in kids.values():
        assert kid['path'] and not kid['path'].startswith('/')
    assert kids['Filmid']['path'] == 'filmid'
    assert 'Otse' not in kids
    assert 'Otse' not in {k['name'] for k in menu.section_children(audio)}


def test_only_the_audio_section_plays_as_audio():
    assert menu.is_audio('Audio') and menu.is_audio('audio')
    assert not menu.is_audio('Video') and not menu.is_audio('')


def test_both_tabs_merge_into_one_list_without_live_links_or_repeats(
        audio_tab_menu_fixture):
    entries = menu.flat_entries(sections(audio_tab_menu_fixture))
    by_label = labelled(entries)
    paths = [e['path'] for e in entries]
    assert len(paths) == len(set(paths))
    assert not {'Video', 'Audio', 'Otse'} & set(by_label)
    assert all('kava' not in path for path in paths)
    assert by_label['Filmid']['section'] == 'Video'
    assert by_label['Muusika']['section'] == 'Audio'


def test_a_label_both_tabs_use_names_its_tab(audio_tab_menu_fixture,
                                             menu_fixture):
    by_label = labelled(menu.flat_entries(sections(audio_tab_menu_fixture)))
    assert by_label['Saated (Video)']['path'] == 'v-saated'
    assert by_label['Saated (Audio)']['path'] == 'audio'
    assert 'Saated' not in by_label
    alone = labelled(menu.flat_entries(sections(menu_fixture)))
    assert 'Saated' in alone and 'Filmid' in alone
    assert not [x for x in alone if x.startswith('Filmid (')]


def test_audio_categories_survive_err_moving_the_audio_tab_off_site(
        menu_fixture):
    audio = sections(menu_fixture)[1]
    assert audio['name'] == 'Audio' and not audio.get('kids')
    assert 'Muusika' not in labelled(menu.flat_entries(sections(menu_fixture)))
    by_label = labelled(menu.flat_entries(sections(menu_fixture),
                                          JUPITER_FALLBACKS))
    assert by_label['Muusika'] == {'label': 'Muusika', 'path': 'muusika',
                                   'section': 'Audio'}
    assert by_label['Saated (Audio)']['path'] == 'audio'
    assert by_label['Saated (Video)']['path'] == 'v-saated'


def test_errs_own_audio_tab_wins_over_the_fallback(audio_tab_menu_fixture):
    tabs = sections(audio_tab_menu_fixture)
    assert menu.flat_entries(tabs, JUPITER_FALLBACKS) == \
        menu.flat_entries(tabs)
