"""Authenticate and query one U8 account without writing ERP business data."""
import argparse
import json
import os
from pathlib import Path
import re
import sys

import httpx


BASE_URL = 'https://api.yonyouup.com'


def credentials(document):
    if document:
        html = Path(document).read_text(encoding='utf-8-sig')
        match = re.search(r'^\s*spec:\s*(\{.*\}),\s*$', html, re.MULTILINE)
        if not match:
            raise ValueError('No embedded OpenAPI JSON found')
        spec = json.loads(match.group(1))
        params = spec['paths']['/system/token']['get']['parameters']
        values = {p['name']: p.get('example') for p in params}
        key, secret = values.get('app_key'), values.get('app_secret')
    else:
        key, secret = os.getenv('U8_APP_KEY'), os.getenv('U8_APP_SECRET')
    if not isinstance(key, str) or not key or not isinstance(secret, str) or not secret:
        raise ValueError('Missing U8 app key or secret')
    return key, secret


def request(client, path, params):
    response = client.get(path, params=params)
    # Never include request URLs in errors: authentication uses query parameters.
    if response.status_code != 200:
        raise ValueError(f'HTTP {response.status_code} from {path}')
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError(f'Unexpected response structure from {path}')
    return data


def check(args):
    key, secret = credentials(args.credentials_html)
    sensitive = [key, secret]

    def report(stage, data):
        message = str(data.get('errmsg', ''))[:1000]
        for value in sensitive:
            message = message.replace(value, '[REDACTED]')
        print(json.dumps({'stage': stage, 'errcode': data.get('errcode'),
                          'message': message}, ensure_ascii=False))

    with httpx.Client(base_url=BASE_URL, timeout=30, follow_redirects=False) as client:
        data = request(client, '/system/token', {
            'from_account': args.from_account, 'app_key': key, 'app_secret': secret,
        })
        token_data = data.get('token')
        token = token_data.get('id') if isinstance(token_data, dict) else None
        if isinstance(token, str) and token:
            sensitive.append(token)
        report('authentication', data)
        if str(data.get('errcode')) != '0' or not isinstance(token, str) or not token:
            return 1
        params = {'from_account': args.from_account, 'to_account': args.to_account,
                  'app_key': key, 'token': token, 'id': args.account}
        if args.ds_sequence is not None:
            params['ds_sequence'] = str(args.ds_sequence)
        result = request(client, '/api/account/get', params)
        report('account_query', result)
        account = result.get('account')
        matched = isinstance(account, dict) and str(account.get('code', account.get('id'))) == args.account
        print(json.dumps({'stage': 'account_verification', 'expected_account': args.account,
                          'matched': matched}, ensure_ascii=False))
        return 0 if str(result.get('errcode')) == '0' and matched else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--credentials-html', help='Apifox HTML containing token credential examples')
    parser.add_argument('--from-account', default='megsky')
    parser.add_argument('--to-account', default='megsky')
    parser.add_argument('--account', default='999')
    parser.add_argument('--ds-sequence', type=int)
    args = parser.parse_args()
    try:
        return check(args)
    except httpx.RequestError as exc:
        print(json.dumps({'stage': 'transport', 'error_type': type(exc).__name__}))
        return 2
    except (ValueError, KeyError, OSError) as exc:
        print(json.dumps({'stage': 'configuration_or_response', 'error_type': type(exc).__name__}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
