"""U8 OpenAPI transport and durable purchase-order reconciliation."""
import json
from copy import deepcopy
import os
from pathlib import Path
import re
import threading
import time
from decimal import Decimal, InvalidOperation
from collections import Counter

import httpx
from sqlalchemy import select

from app.models.entities import OrderExecution
from app.services.import_service import get_job, rows_for
from app.business.purchase_order import payload,order_key
from .exceptions import U8BusinessError, U8UncertainError


class LiveU8Client:
    mode = 'U8'

    def __init__(self, factory, transport=None):
        self.factory = factory
        self.account = os.getenv('U8_ACCOUNT', '999')
        self.from_account = os.getenv('U8_FROM_ACCOUNT', 'megsky')
        self.to_account = os.getenv('U8_TO_ACCOUNT', 'megsky')
        self.sequence = os.getenv('U8_DS_SEQUENCE', '')
        self.key = os.getenv('U8_APP_KEY', '')
        self.secret = os.getenv('U8_APP_SECRET', '')
        document = os.getenv('U8_CREDENTIALS_HTML')
        if document and not (self.key and self.secret):
            html = Path(document).read_text(encoding='utf-8-sig')
            match = re.search(r'^\s*spec:\s*(\{.*\}),\s*$', html, re.MULTILINE)
            if not match: raise ValueError('凭据文件中没有 OpenAPI 定义')
            params = json.loads(match.group(1))['paths']['/system/token']['get']['parameters']
            values = {p['name']: p.get('example') for p in params}
            self.key, self.secret = values.get('app_key'), values.get('app_secret')
        if not self.key or not self.secret: raise ValueError('未配置 U8 应用凭据')
        from app.observability import SECRETS
        SECRETS.update([self.key,self.secret])
        self.http = httpx.Client(base_url='https://api.yonyouup.com', timeout=45,
                                 follow_redirects=False, transport=transport)
        self.token = ''
        self.expires = 0
        self.lock = threading.Lock()

    @property
    def target(self):
        return {'mode': 'U8', 'account': self.account, 'from_account': self.from_account,
                'to_account': self.to_account, 'ds_sequence': self.sequence, 'app_key': self.key}

    def _redact(self, value):
        result = str(value)
        for secret in (self.key, self.secret, self.token):
            if secret: result = result.replace(secret, '[REDACTED]')
        return result[:1000]

    def _request(self, method, path, params, body=None):
        # Read-only/auth requests are safe to retry after transient network
        # failures. Never retry POST: a timed-out write may already have been
        # accepted by U8 and repeating it could create a duplicate order.
        attempts = 3 if method == 'GET' else 1
        last_error = None
        for attempt in range(attempts):
            try:
                response = self.http.request(method, path, params=params, json=body)
                if method == 'GET' and response.status_code in (502, 503, 504) and attempt < attempts - 1:
                    time.sleep(0.4 * (attempt + 1))
                    continue
            except httpx.RequestError as exc:
                last_error = exc
                if attempt >= attempts - 1:
                    raise U8UncertainError('U8 连接失败或超时，已自动重试3次，请检查 U8 服务或稍后回查') from None
                time.sleep(0.4 * (attempt + 1))
                continue
            if response.status_code != 200:
                raise U8UncertainError(f'U8 HTTP {response.status_code}，结果需回查')
            try: data = response.json()
            except ValueError: raise U8UncertainError('U8 返回了非 JSON 响应') from None
            if not isinstance(data, dict): raise U8UncertainError('U8 响应结构异常')
            # U8 sometimes returns HTTP 200 with 20006 when its SQL Server TLS
            # connection is closed mid-request. Read-only calls can be retried;
            # writes must never be repeated because the first request may commit.
            if (method == 'GET' and str(data.get('errcode')) == '20006'
                    and attempt < attempts - 1):
                time.sleep(0.4 * (attempt + 1))
                continue
            return data
        else:
            raise U8UncertainError('U8 连接失败或超时，请稍后回查') from last_error

    def _auth(self):
        with self.lock:
            if time.monotonic() < self.expires: return
            data = self._request('GET', '/system/token', {
                'from_account': self.from_account, 'app_key': self.key, 'app_secret': self.secret,
            })
            token = data.get('token') or {}
            if str(data.get('errcode')) != '0' or not token.get('id'):
                raise U8BusinessError('U8 认证失败：' + self._redact(data.get('errmsg', '')))
            self.token = str(token['id'])
            from app.observability import SECRETS
            SECRETS.add(self.token)
            self.expires = time.monotonic() + max(1, int(token.get('expiresIn', 7200)) - 60)

    def call(self, path, params=None, body=None):
        self._auth()
        query = {'from_account': self.from_account, 'to_account': self.to_account,
                 'app_key': self.key, 'token': self.token}
        if self.sequence: query['ds_sequence'] = self.sequence
        data = self._request('POST' if body is not None else 'GET', path, query | (params or {}), body)
        if 'errcode' in data and str(data['errcode']) != '0':
            raise U8BusinessError(f"U8 {self._redact(data['errcode'])}：{self._redact(data.get('errmsg', ''))}",str(data['errcode']))
        return data

    def connection(self):
        data = self.call('/api/account/get', {'id': self.account})
        account = data.get('account') or {}
        if str(data.get('errcode')) != '0' or str(account.get('code', account.get('id'))) != self.account:
            raise U8BusinessError('U8 返回账套与目标账套不一致')
        return {'mode': 'U8', 'account': self.account, 'name': account.get('name', ''),
                'from_account': self.from_account, 'to_account': self.to_account, 'connected': True}

    def list_orders(self, page=1, code='', date_begin='', date_end='', vendor='', remark=''):
        params = {'page_index': page, 'rows_per_page': 20}
        if code: params.update(code_begin=code, code_end=code)
        if date_begin: params['date_begin'] = date_begin
        if date_end: params['date_end'] = date_end
        if vendor: params['vendorname'] = vendor
        if remark: params['remark'] = remark
        try: data = self.call('/api/purchaseorderlist/batch_get', params)
        except U8BusinessError as exc:
            if exc.code=='20002': return {'items': [], 'total': 0, 'pages': 0, 'page': page}
            raise
        if str(data.get('errcode')) != '0' or not isinstance(data.get('purchaseorderlist'), list):
            raise U8UncertainError('采购订单列表尚未返回有效结果')
        return {'items': data['purchaseorderlist'], 'total': int(data.get('row_count', 0)),
                'pages': int(data.get('page_count', 0)), 'page': page}

    def order(self, code):
        data = self.call('/api/purchaseorder/get', {'id': code})
        order = data.get('purchaseorder')
        if str(data.get('errcode')) != '0' or not isinstance(order, dict) or not isinstance(order.get('entry'), list):
            raise U8UncertainError('U8 尚未返回完整采购订单')
        # This account stores the imported contract number in define1 even
        # though the API schema names the standard field contractcode.
        if not order.get('contractcode') and order.get('define1'):
            order['contractcode'] = order['define1']
        # U8's order query omits several optional header fields. Recover the
        # original submitted values from the durable execution linked to this
        # ERP number so the UI can show the complete order consistently.
        if self.factory:
            with self.factory() as db:
                execution = db.scalar(select(OrderExecution).where(OrderExecution.erp_business_id == code))
                if not execution:
                    execution = next((item for item in db.scalars(select(OrderExecution))
                                      if str(item.erp_business_id or '').strip() == str(code).strip()), None)
                if execution:
                    job = get_job(db, execution.job_id)
                    header = job.header
                    order.setdefault('currency_name', header.get('currency', '人民币'))
                    order.setdefault('currency_rate', str(header.get('exchange_rate', '1')))
                    if header.get('pay_condition') and not order.get('paycondition'):
                        order['paycondition'] = header['pay_condition']
                    if header.get('remark') and not order.get('remark'):
                        order['remark'] = header['remark']
        return order

    def master(self, kind, page=1, name='', code=''):
        if kind not in ('vendor', 'inventory'): raise ValueError('Unsupported master data')
        params = {'page_index': page, 'rows_per_page': 20}
        if name: params['name'] = name
        if code: params.update(code_begin=code, code_end=code)
        try: data = self.call(f'/api/{kind}/batch_get', params)
        except U8BusinessError as exc:
            if exc.code=='20002': return {'items': [], 'total': 0, 'pages': 0, 'page': page}
            raise
        if str(data.get('errcode')) != '0' or not isinstance(data.get(kind), list):
            raise U8UncertainError('主数据查询未返回有效结果')
        fields = ('code', 'name', 'specs', 'puunit_name', 'end_date', 'iimptaxrate')
        return {'items': [{k: row.get(k) for k in fields} for row in data[kind]],
                'total': int(data.get('row_count', 0)), 'pages': int(data.get('page_count', 0)), 'page': page}

    def _named_master(self, kind, name):
        data = self.call(f'/api/{kind}/batch_get', {'page_index': 1, 'rows_per_page': 100, 'name': name})
        rows = data.get(kind) or data.get(f'{kind}list') or []
        return rows if isinstance(rows, list) else []

    def _code_master(self, kind, code):
        data = self.call(f'/api/{kind}/batch_get', {
            'page_index': 1, 'rows_per_page': 20, 'code_begin': code, 'code_end': code,
        })
        rows = data.get(kind) or data.get(f'{kind}list') or []
        return rows if isinstance(rows, list) else []

    def resolve_header_names(self, header):
        """Translate friendly department/person names to U8 master codes."""
        for value_key, code_key, kind, label in (
            ('department', 'deptcode', 'department', '部门'),
            ('employee', 'personcode', 'person', '业务员'),
        ):
            supplied_code = str(header.get(code_key) or '').strip()
            value = str(header.get(value_key) or '').strip()
            if supplied_code:
                rows = self._code_master(kind, supplied_code)
                exact = [r for r in rows if str(r.get('code') or r.get(code_key) or r.get('id') or '').strip() == supplied_code]
                if len(exact) != 1:
                    raise U8BusinessError(f'{label}编码“{supplied_code}”在当前 U8 账套中无法唯一匹配')
                row = exact[0]
                if kind == 'department' and str(row.get('endflag', row.get('is_end', '1'))) in ('0', 'False', 'false'):
                    raise U8BusinessError(f'部门编码“{supplied_code}”不是末级部门，请选择末级部门')
                continue
            if not value:
                continue
            value = value
            rows = self._named_master(kind, value)
            exact = [r for r in rows if str(r.get('name') or r.get('personname') or r.get('deptname') or '').strip() == value]
            if not exact and kind == 'person':
                # Chinese names are occasionally entered with a homophone or
                # look-alike character; accept a unique one-character typo.
                def distance(a, b):
                    if abs(len(a)-len(b)) > 1: return 99
                    prev=list(range(len(b)+1))
                    for i,ca in enumerate(a,1):
                        cur=[i]
                        for j,cb in enumerate(b,1): cur.append(min(cur[-1]+1,prev[j]+1,prev[j-1]+(ca!=cb)))
                        prev=cur
                    return prev[-1]
                fuzzy=[r for r in rows if distance(value, str(r.get('name') or '').strip()) <= 1]
                if len(fuzzy) == 1: exact = fuzzy
            if len(exact) != 1:
                raise U8BusinessError(f'{label}“{value}”无法唯一匹配 U8 主数据，请填写准确名称或编码')
            row = exact[0]
            if kind == 'department' and str(row.get('endflag', row.get('is_end', '1'))) in ('0', 'False', 'false'):
                raise U8BusinessError(f'部门“{value}”不是末级部门，请选择末级部门')
            code = row.get('code') or row.get('deptcode') or row.get('personcode') or row.get('id')
            if not code: raise U8BusinessError(f'{label}“{value}”未返回有效编码')
            header[code_key] = str(code)
        return header

    def get_vendor(self, code):
        return any(str(r['code']) == code and not r.get('end_date') for r in self.master('vendor', code=code)['items'])

    def get_inventory(self, code):
        return any(str(r['code']) == code and not r.get('end_date') for r in self.master('inventory', code=code)['items'])

    def _context(self, key):
        with self.factory() as db:
            execution = db.scalar(select(OrderExecution).where(OrderExecution.order_key == key))
            if not execution: raise U8UncertainError('缺少持久化订单执行记录')
            job = get_job(db, execution.job_id)
            if job.header.get('_target') != self.target:
                raise U8BusinessError('任务账套或应用与当前连接配置不一致')
            return payload(job.header, rows_for(db, job.id)), dict(execution.remote_state or {})

    def _save(self, key, state):
        with self.factory() as db:
            execution = db.scalar(select(OrderExecution).where(OrderExecution.order_key == key).with_for_update())
            execution.remote_state = state
            db.commit()

    @staticmethod
    def marker(body):
        return '[U8IMPORT:'+order_key(body['header'])[:24]+']'

    @staticmethod
    def body(body):
        header = body['header']
        # Keep the UI's friendly names as input aliases, but emit the field
        # names used by purchaseorder/add.  U8 stores the contract number in
        # define1 in this account; contractcode is retained for deployments
        # that expose the standard field.
        purchase_type_input = header.get('purchase_type_code') or header.get('purchase_type')
        # The UI accepts the friendly name, while U8's purchase_type_code is
        # a short master-data code. Keep explicit codes intact and translate
        # the default display name used by the form.
        purchase_type = {'普通采购': '03'}.get(str(purchase_type_input), purchase_type_input) or '03'
        department = header.get('deptcode') or header.get('department')
        employee = header.get('personcode') or header.get('employee')
        contract = header.get('contractcode') or header.get('contract_no')
        order = {'code': header['order_reference'], 'date': header['order_date'],
                 'vendorcode': header['vendor_code'],
                 'operation_type_code': header.get('purchase_type', '普通采购'),
                 'purchase_type_code': purchase_type,
                 'currency_name': header.get('currency', header.get('currency_name', '人民币')),
                 'currency_rate': str(header.get('exchange_rate', header.get('currency_rate', '1'))),
                 'remark': header.get('remark', '')[:160]+' '+LiveU8Client.marker(body)}
        if department: order['deptcode'] = department
        if employee: order['personcode'] = employee
        if contract:
            order['contractcode'] = contract
            order['define1'] = contract
        if header.get('pay_condition'): order['paycondition'] = header['pay_condition']
        field = 'taxprice' if header['price_mode'] == 'INCLUSIVE' else 'price'
        order['entry'] = [dict(inventorycode=r['inventory_code'], quantity=r['quantity'],
                               rowno=i, **{field: r['price'], 'taxrate': str(header.get('tax_rate', '13'))})
                          for i, r in enumerate(body['entries'], 1)]
        return {'purchaseorder': order}

    def verified(self, actual, body, erp_code=None):
        expected = self.body(body)['purchaseorder']
        if erp_code: expected['code'] = erp_code
        for key in ('code', 'vendorcode', 'date'):
            found, wanted = str(actual.get(key)), str(expected[key])
            if key == 'date': found, wanted = found[:10], wanted[:10]
            if found != wanted:
                raise U8UncertainError('回查订单头与提交内容不一致')
        field = 'taxprice' if body['header']['price_mode'] == 'INCLUSIVE' else 'price'
        def signature(row):
            values = [Decimal(str(row.get(k))) for k in ('quantity', field)]
            if not all(v.is_finite() for v in values): raise ValueError()
            return (str(row.get('inventorycode')), *values)
        try:
            if Counter(map(signature, actual['entry'])) != Counter(map(signature, expected['entry'])):
                raise U8UncertainError('回查物料、数量、单价或明细数不一致')
        except (InvalidOperation, ValueError, KeyError):
            raise U8UncertainError('回查明细字段不完整') from None
        return {'id': str(actual['code']), 'mode': 'U8', 'payload': body}

    def query_purchase_order(self, key):
        body, state = self._context(key)
        self.connection()
        if state.get('erp_id'):
            return self.verified(self.order(state['erp_id']), body, state['erp_id'])
        if state.get('requestid'):
            data = self.call('/result', {'requestid': state['requestid']})
            if str(data.get('errcode')) == '0' and data.get('id'):
                state['erp_id'] = str(data['id']); self._save(key, state)
                return self.verified(self.order(state['erp_id']), body, state['erp_id'])
        if state.get('submitted'):
            marker=self.marker(body)
            matches=self.list_orders(remark=marker)['items']
            exact=[r for r in matches if marker in str(r.get('remark',''))]
            if len(exact)==1:
                actual=self.order(str(exact[0]['code']))
                result=self.verified(actual,body,str(exact[0]['code']))
                state['erp_id']=result['id']; self._save(key,state)
                return result
            if len(exact)>1: raise U8UncertainError('存在多个相同业务标记的 U8 单据，需人工核对')
        matches = self.list_orders(code=body['header']['order_reference'])['items']
        exact = [r for r in matches if str(r.get('code')) == body['header']['order_reference']]
        if exact:
            if not state.get('submitted'):
                raise U8BusinessError('U8 已存在同编号订单，请更换新订单编号或查看原单')
            return self.verified(self.order(body['header']['order_reference']), body)
        if state.get('submitted'):
            raise U8UncertainError('U8 已提交，订单尚未查到；仅允许继续回查，不重复创建')
        return None

    def create_purchase_order(self, key, body):
        persisted, state = self._context(key)
        if persisted != body: raise U8BusinessError('提交内容与持久化任务不一致')
        if state.get('submitted'):
            return self.query_purchase_order(key)
        # Legacy tasks may contain names only. Resolve the outbound copy;
        # keep the persisted payload intact for identity and result checks.
        outbound = deepcopy(body)
        self.resolve_header_names(outbound['header'])
        self.connection()
        # Commit the attempt before network I/O. A crash must never trigger a blind second POST.
        state = {'submitted': True, 'biz_id': key}
        self._save(key, state)
        data = self.call('/api/purchaseorder/add', {'biz_id': key, 'sync': 1}, self.body(outbound))
        if data.get('tradeid'): state['requestid'] = str(data['tradeid'])
        if data.get('id'): state['erp_id'] = str(data['id'])
        self._save(key, state)
        return self.query_purchase_order(key)
