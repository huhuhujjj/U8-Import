import importlib.util
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest


spec = importlib.util.spec_from_file_location(
    'check_u8_connection', Path(__file__).resolve().parents[2] / 'scripts/check_u8_connection.py'
)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


@pytest.mark.parametrize('auth_code,account_code,expected,calls', [
    ('0', '999', 0, 2), ('0', '998', 1, 2), ('2001', '999', 1, 1),
])
def test_read_only_probe_redacts_credentials(monkeypatch, capsys, auth_code, account_code, expected, calls):
    monkeypatch.setenv('U8_APP_KEY', 'test-app-key')
    monkeypatch.setenv('U8_APP_SECRET', 'test-app-secret')
    requests = []

    def handler(request):
        requests.append(request)
        assert request.method == 'GET'
        assert request.url.host == 'api.yonyouup.com'
        if request.url.path == '/system/token':
            assert request.url.params['from_account'] == 'megsky'
            return httpx.Response(200, json={
                'errcode': auth_code, 'errmsg': 'test-app-key test-app-secret test-token',
                'token': {'id': 'test-token'},
            })
        assert request.url.path == '/api/account/get'
        assert request.url.params['to_account'] == 'megsky'
        assert request.url.params['id'] == '999'
        assert request.url.params['token'] == 'test-token'
        assert 'app_secret' not in request.url.params
        return httpx.Response(200, json={'errcode': '0', 'account': {'code': account_code}})

    original = httpx.Client
    monkeypatch.setattr(probe.httpx, 'Client', lambda **kwargs: original(
        **kwargs, transport=httpx.MockTransport(handler)
    ))
    args = SimpleNamespace(credentials_html=None, from_account='megsky', to_account='megsky',
                           account='999', ds_sequence=None)
    assert probe.check(args) == expected
    assert len(requests) == calls
    output = capsys.readouterr().out
    for value in ('test-app-key', 'test-app-secret', 'test-token'):
        assert value not in output
