from copy import deepcopy
import json

import httpx
import pytest

from app.integrations.u8.live import LiveU8Client
from app.integrations.u8.exceptions import U8BusinessError, U8UncertainError


@pytest.fixture
def body():
    return {'header': {'order_reference': 'TEST-001', 'order_date': '2026-09-20',
                       'vendor_code': 'V01', 'price_mode': 'INCLUSIVE', 'tax_rate': '13'},
            'entries': [{'inventory_code': '0001', 'quantity': '2', 'price': '11.3', 'line_reference': '2'}]}


def make_client(monkeypatch, handler):
    monkeypatch.setenv('U8_APP_KEY', 'key-for-test')
    monkeypatch.setenv('U8_APP_SECRET', 'secret-for-test')
    def route(request):
        if request.url.path == '/system/token':
            return httpx.Response(200, json={'errcode': 0, 'token': {'id': 'private-token', 'expiresIn': 7200}})
        return handler(request)
    return LiveU8Client(None, transport=httpx.MockTransport(route))


def test_price_mode_and_reconciliation(body):
    expected = LiveU8Client.body(body)['purchaseorder']
    assert expected['entry'][0]['taxprice'] == '11.3'
    assert 'price' not in expected['entry'][0]
    assert expected['entry'][0]['rowno'] == 1
    client = object.__new__(LiveU8Client)
    assert client.verified(expected, body)['mode'] == 'U8'
    auto_numbered=deepcopy(expected);auto_numbered['code']='CG20260900001'
    assert client.verified(auto_numbered,body,'CG20260900001')['id']=='CG20260900001'
    wrong = deepcopy(expected); wrong['entry'][0]['quantity'] = '3'
    with pytest.raises(U8UncertainError): client.verified(wrong, body)
    wrong = deepcopy(expected); wrong['vendorcode'] = 'OTHER'
    with pytest.raises(U8UncertainError): client.verified(wrong, body)
    body['header']['price_mode'] = 'EXCLUSIVE'
    assert 'taxprice' not in LiveU8Client.body(body)['purchaseorder']['entry'][0]


def test_purchase_type_display_name_is_emitted_as_u8_code(body):
    body['header']['purchase_type'] = '普通采购'
    order = LiveU8Client.body(body)['purchaseorder']
    assert order['operation_type_code'] == '普通采购'
    assert order['purchase_type_code'] == '03'


def test_department_alias_is_not_hardcoded_for_another_account(body):
    body['header']['department'] = '运营中心-采购部'
    body['header']['_target'] = {'mode': 'U8', 'account': 'OTHER'}
    order = LiveU8Client.body(body)['purchaseorder']
    assert order['deptcode'] == '运营中心-采购部'


def test_supplied_master_codes_are_verified_against_current_account(monkeypatch, body):
    client = object.__new__(LiveU8Client)
    client._code_master = lambda kind, code: [{'code': 'D-OTHER', 'name': '其他部门', 'endflag': '1'}]
    body['header']['deptcode'] = '0502'
    with pytest.raises(U8BusinessError, match='部门'):
        client.resolve_header_names(body['header'])


@pytest.mark.parametrize('field', ['quantity', 'vendor_code', 'deptcode'])
def test_modified_payload_still_rejected_before_write(monkeypatch, body, field):
    calls=[]
    client=make_client(monkeypatch, lambda r:calls.append(r))
    monkeypatch.setattr(client, '_context', lambda key:(deepcopy(body), {}))
    changed=deepcopy(body)
    if field=='quantity': changed['entries'][0][field]='999'
    else: changed['header'][field]='OTHER'
    with pytest.raises(U8BusinessError, match='提交内容与持久化任务不一致'):
        client.create_purchase_order('stable-key',changed)
    assert calls==[]


def test_no_token_or_secret_in_errors(monkeypatch):
    client = make_client(monkeypatch, lambda r: httpx.Response(200, json={
        'errcode': '123', 'errmsg': 'key-for-test secret-for-test private-token'}))
    with pytest.raises(U8BusinessError) as caught: client.connection()
    assert 'secret-for-test' not in str(caught.value)
    assert 'private-token' not in str(caught.value)
    assert 'key-for-test' not in str(caught.value)


def test_redirect_does_not_forward_credentials(monkeypatch):
    seen=[]
    def handler(r):
        seen.append(r.url.host)
        return httpx.Response(302, headers={'location': 'https://example.org/steal'})
    client=make_client(monkeypatch, handler)
    with pytest.raises(U8UncertainError): client.connection()
    assert seen==['api.yonyouup.com']


def test_missing_list_is_unknown_not_empty(monkeypatch):
    client=make_client(monkeypatch, lambda r: httpx.Response(200, json={'tradeid':'pending'}))
    with pytest.raises(U8UncertainError): client.list_orders(code='TEST-001')


def test_timeout_after_write_recovers_without_second_post(monkeypatch,body):
    state={}; ledger=[]; posts=[]
    def handler(r):
        if r.url.path=='/api/account/get':
            return httpx.Response(200,json={'errcode':'0','account':{'code':'999'}})
        if r.url.path=='/api/purchaseorder/add':
            assert state.get('submitted')
            assert r.url.params['biz_id']=='stable-key'
            posts.append(r)
            ledger.append(json.loads(r.content)['purchaseorder'])
            raise httpx.ReadTimeout('timeout',request=r)
        if r.url.path=='/api/purchaseorderlist/batch_get':
            return httpx.Response(200,json={'errcode':0,'purchaseorderlist':[{'code':o['code']} for o in ledger]})
        if r.url.path=='/api/purchaseorder/get':
            return httpx.Response(200,json={'errcode':0,'purchaseorder':ledger[0]})
        raise AssertionError(r.url.path)
    client=make_client(monkeypatch,handler)
    monkeypatch.setattr(client,'_context',lambda key:(body,dict(state)))
    monkeypatch.setattr(client,'_save',lambda key,value:state.update(value))
    assert client.query_purchase_order('stable-key') is None
    with pytest.raises(U8UncertainError):client.create_purchase_order('stable-key',body)
    assert client.query_purchase_order('stable-key')['id']=='TEST-001'
    assert client.create_purchase_order('stable-key',body)['mode']=='U8'
    assert len(posts)==1


def test_submitted_but_absent_never_returns_not_found(monkeypatch,body):
    client=make_client(monkeypatch,lambda r:httpx.Response(200,json={'errcode':0,'purchaseorderlist':[]}))
    monkeypatch.setattr(client,'_context',lambda key:(body,{'submitted':True}))
    monkeypatch.setattr(client,'connection',lambda:None)
    with pytest.raises(U8UncertainError):client.query_purchase_order('key')


def test_existing_order_before_submission_is_conflict(monkeypatch,body):
    client=make_client(monkeypatch,lambda r:httpx.Response(200,json={'errcode':0,'purchaseorderlist':[{'code':'TEST-001'}]}))
    monkeypatch.setattr(client,'_context',lambda key:(body,{}))
    monkeypatch.setattr(client,'connection',lambda:None)
    with pytest.raises(U8BusinessError):client.query_purchase_order('key')


@pytest.mark.parametrize('code,empty',[('20002',True),('30021',False)])
def test_only_documented_no_match_code_means_empty(monkeypatch,code,empty):
    client=make_client(monkeypatch,lambda r:httpx.Response(200,json={'errcode':code,'errmsg':'no match or permission error'}))
    if empty:
        assert client.list_orders(code='MISSING')['items']==[]
        assert not client.get_inventory('MISSING')
    else:
        with pytest.raises(U8BusinessError): client.list_orders()


def test_async_result_uses_erp_assigned_number(monkeypatch,body):
    state={'submitted':True,'requestid':'request-1'}; paths=[]
    actual=LiveU8Client.body(body)['purchaseorder'];actual['code']='CG-AUTO-001'
    def handler(r):
        paths.append(r.url.path)
        if r.url.path=='/result':return httpx.Response(200,json={'errcode':'0','id':'CG-AUTO-001'})
        assert r.url.path=='/api/purchaseorder/get'
        assert r.url.params['id']=='CG-AUTO-001'
        return httpx.Response(200,json={'errcode':'0','purchaseorder':actual})
    client=make_client(monkeypatch,handler)
    monkeypatch.setattr(client,'_context',lambda key:(body,dict(state)))
    monkeypatch.setattr(client,'_save',lambda key,value:state.update(value))
    monkeypatch.setattr(client,'connection',lambda:None)
    assert client.query_purchase_order('key')['id']=='CG-AUTO-001'
    assert state['erp_id']=='CG-AUTO-001'
    paths.clear()
    assert client.query_purchase_order('key')['id']=='CG-AUTO-001'
    assert paths==['/api/purchaseorder/get']


def test_timeout_without_result_id_recovers_by_business_marker(monkeypatch,body):
    state={'submitted':True}; actual=LiveU8Client.body(body)['purchaseorder'];actual['code']='CG-AUTO-002'
    def handler(r):
        if r.url.path=='/api/purchaseorderlist/batch_get':
            assert r.url.params['remark']==LiveU8Client.marker(body)
            return httpx.Response(200,json={'errcode':0,'purchaseorderlist':[actual]})
        return httpx.Response(200,json={'errcode':0,'purchaseorder':actual})
    client=make_client(monkeypatch,handler)
    monkeypatch.setattr(client,'_context',lambda key:(body,dict(state)))
    monkeypatch.setattr(client,'_save',lambda key,value:state.update(value))
    monkeypatch.setattr(client,'connection',lambda:None)
    assert client.query_purchase_order('key')['id']=='CG-AUTO-002'
    assert state['erp_id']=='CG-AUTO-002'
