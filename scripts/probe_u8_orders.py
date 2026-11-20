"""Read-only discovery of purchase-order and master-data API permissions."""
import argparse
import json
import httpx
from check_u8_connection import credentials, request, BASE_URL

parser=argparse.ArgumentParser()
parser.add_argument('--credentials-html', required=True)
args=parser.parse_args()
key,secret=credentials(args.credentials_html)
try:
    with httpx.Client(base_url=BASE_URL, timeout=30, follow_redirects=False) as client:
        auth=request(client,'/system/token',{'from_account':'megsky','app_key':key,'app_secret':secret})
        token=auth.get('token',{}).get('id')
        if not token: raise ValueError('Authentication failed')
        common={'from_account':'megsky','to_account':'megsky','app_key':key,'token':token}
        for path,params,listkey in [
            ('/api/purchaseorderlist/batch_get',{'page_index':1,'rows_per_page':2},'purchaseorderlist'),
            ('/api/vendor/batch_get',{'page_index':1,'rows_per_page':2},'vendor'),
            ('/api/inventory/batch_get',{'page_index':1,'rows_per_page':2},'inventory'),
        ]:
            data=request(client,path,common|params)
            message=str(data.get('errmsg',''))
            for value in (key,secret,token): message=message.replace(value,'[REDACTED]')
            rows=data.get(listkey,[])
            print(json.dumps({'path':path,'errcode':data.get('errcode'),'message':message,'count':data.get('row_count'),
                              'samples':[{k:r.get(k) for k in ('code','name','date','vendorcode','operation_type_code','purchase_type_code')} for r in rows[:2]]},ensure_ascii=False))
except (httpx.RequestError,ValueError,KeyError) as exc:
    print(json.dumps({'error_type':type(exc).__name__}))
    raise SystemExit(2)
