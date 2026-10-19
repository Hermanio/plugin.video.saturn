# SPDX-License-Identifier: GPL-3.0-or-later
from resources.lib import content, schedule
from resources.lib.helpers import absolutize


def test_live_tv_and_radio_play_over_https_hls(live_tv_fixture,
                                               live_radio_fixture):
    for payload in (live_tv_fixture, live_radio_fixture):
        url = absolutize(payload['src'])
        assert url.startswith('https://') and '.m3u8' in url
    assert content.live_is_audio(live_tv_fixture) is False
    assert content.live_is_audio(live_radio_fixture) is True


def test_live_tv_finds_errs_widevine_stream(live_tv_fixture,
                                            live_radio_fixture):
    drm = content.live_drm(live_tv_fixture, '12345678901234')
    assert drm['manifest'] == \
        'https://live.err.ee/12345678901234/etv/etv.isml/manifest.mpd'
    assert drm['url'].startswith('https://drm-widevine-licensing.')
    assert drm['token']
    assert content.live_drm(live_radio_fixture, '1') is None
    assert content.live_drm({'config': {'drm': {'jwt': 'x'}}}, '1') is None


def test_a_days_schedule_lists_titled_programmes(schedule_fixture):
    programmes = schedule.parse_schedule(schedule_fixture)
    assert programmes
    for programme in programmes:
        assert programme['start'] > 0 and programme['title']
    label = schedule.programme_label(programmes[0])
    assert ':' in label[:6] and programmes[0]['title'] in label


def test_a_schedule_skips_rows_it_cannot_place():
    assert schedule.parse_schedule(None) == []
    assert schedule.parse_schedule(['nonsense', {}, {'name': 'x'}]) == []


def test_recorded_programmes_can_be_caught_up_on(schedule_fixture):
    playable = [p for p in schedule.parse_schedule(schedule_fixture)
                if schedule.is_playable(p)]
    assert playable, 'no catch-up entries in the recorded day'
    assert all(p['content_id'] and p['has_media'] for p in playable)
    assert schedule.is_playable({'start': 4102444800, 'has_media': True,
                                 'content_id': 1})
    assert not schedule.is_playable({'has_media': False, 'content_id': 5})
    assert not schedule.is_playable({'has_media': True, 'content_id': None})


def test_the_programme_on_now_is_found_with_an_exclusive_end():
    programmes = [{'start': 100, 'end': 200, 'title': 'a'},
                  {'start': 200, 'end': 300, 'title': 'b'}]
    for now, title in ((199, 'a'), (200, 'b'), (250, 'b')):
        assert schedule.current_programme(programmes, now=now)['title'] == \
            title
    assert schedule.current_programme(programmes, now=50) is None
    assert schedule.current_programme([], now=1) is None
