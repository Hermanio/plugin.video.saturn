# SPDX-License-Identifier: GPL-3.0-or-later
import io
import json
from urllib.error import HTTPError

import pytest

from resources.lib import constants as C
from resources.lib.api import ApiError, ErrApi


class FakeUrlopen:
    def __init__(self, payload=None, error=None):
        self.payload = payload if payload is not None else {'data': 'ok'}
        self.error = error
        self.calls = []

    def __call__(self, request, timeout=None):
        self.calls.append({'url': request.full_url,
                           'referer': request.get_header('Referer'),
                           'timeout': timeout})
        if self.error:
            raise self.error
        return io.BytesIO(json.dumps(self.payload).encode('utf-8'))


@pytest.fixture
def api():
    return ErrApi()


def test_a_request_carries_the_websites_headers(api, monkeypatch):
    fake = FakeUrlopen({'data': [1, 2]})
    monkeypatch.setattr('resources.lib.api.urlopen', fake)
    assert api.get_json('https://example.invalid/x', {'b': 2}) == \
        {'data': [1, 2]}
    assert fake.calls[0]['url'] == 'https://example.invalid/x?b=2'
    assert fake.calls[0]['referer']
    assert fake.calls[0]['timeout']


@pytest.mark.parametrize('error,message', [
    (HTTPError('https://example.invalid/boom', 503, 'Service Unavailable',
               {}, None), '503'),
    (OSError('connection reset'), 'connection reset'),
])
def test_a_failed_request_is_an_api_error(api, monkeypatch, error, message):
    monkeypatch.setattr('resources.lib.api.urlopen', FakeUrlopen(error=error))
    with pytest.raises(ApiError) as excinfo:
        api.get_json('https://example.invalid/boom', {})
    assert message in str(excinfo.value)


def _canned(payload):
    seen = []

    def get_json(url, params=None):
        seen.append(json.loads((params or {})['options']))
        return payload

    return get_json, seen


def test_search_all_covers_both_media_in_one_request():
    api = ErrApi()
    api.get_json, seen = _canned({
        'video': {'contents': [{'id': 'v'}], 'totalFound': 7, 'limit': 50},
        'audio': {'contents': [{'id': 'a'}], 'totalFound': 3, 'limit': 50}})
    result = api.search_all(phrase='muumi')
    assert len(seen) == 1
    assert seen[0]['searchTypes'] == ['video', 'audio']
    assert [c['id'] for c in result['contents']] == ['v', 'a']
    assert result['audio_ids'] == {'a'}
    assert result['has_more'] is False


def test_search_all_pins_every_query_to_jupiters_root():
    api = ErrApi(domain='lasteekraan')
    api.get_json, seen = _canned({})
    api.search_all(phrase='karukalli')
    assert seen[0]['category'] == C.DOMAINS['jupiter']['root_id']


def test_search_all_reports_more_when_either_half_is_full():
    api = ErrApi()
    api.get_json, _ = _canned({
        'video': {'contents': [{'id': 1}], 'limit': 50},
        'audio': {'contents': [{'id': i} for i in range(50)], 'limit': 50}})
    assert api.search_all(phrase='x')['has_more'] is True


def test_search_all_survives_a_domain_that_answers_with_a_bare_list():
    api = ErrApi()
    api.get_json = lambda url, params=None: []
    assert api.search_all(phrase='x') == {
        'contents': [], 'audio_ids': set(), 'has_more': False}


def _pages(*pages):
    seen = []

    def get_json(url, params=None):
        seen.append(dict(params))
        return pages[len(seen) - 1]

    return get_json, seen


def test_a_stations_programmes_are_read_to_the_last_page():
    api = ErrApi()
    api.get_json, seen = _pages(
        {'status': 'success', 'totalPages': 2,
         'data': {'results': [{'id': 1}]}},
        {'status': 'success', 'totalPages': 2,
         'data': {'results': [{'id': 2}]}})
    assert api.get_radio_programmes(404) == [{'id': 1}, {'id': 2}]
    assert [p['page'] for p in seen] == [1, 2]
    assert seen[0]['active'] == 'true'
    assert seen[0]['primaryCategoryIds[]'] == 404


def test_a_failed_programme_listing_is_an_api_error():
    api = ErrApi()
    api.get_json, _ = _pages({'status': 'error', 'message': 'nope'})
    with pytest.raises(ApiError):
        api.get_radio_programmes(404)
