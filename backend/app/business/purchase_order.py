import hashlib
import json
from decimal import Decimal, InvalidOperation

FIELDS=('inventory_code','quantity','price')
def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def normalize(raw,mapping):
    if set(mapping)!=set(FIELDS) or len(set(mapping.values()))!=3:
        raise ValueError('字段映射缺失或来源列重复')
    values={k:raw.get(mapping[k]) for k in FIELDS}
    code=str(values['inventory_code'] or '').strip()
    if not code: raise ValueError('inventory_code: 物料编码为空')
    result={'inventory_code':code}
    for key in ('quantity','price'):
        try:
            v=Decimal(str(values[key]).strip())
            if not v.is_finite() or abs(v)>Decimal('1e12') or (key=='quantity' and v<=0) or (key=='price' and v<0):
                raise ValueError()
            if v.as_tuple().exponent < -8: raise ValueError()
        except (InvalidOperation,ValueError):
            raise ValueError(f'{key}: 必须是有效数字，数量大于零，单价非负，小数不超过8位') from None
        result[key]=format(v.normalize(),'f')
    return result

def order_key(header):
    if header.get('_target',{}).get('mode')=='U8':
        return digest([header['_target'],'PURCHASE_ORDER',header['order_reference']])
    return digest(['MOCK','PURCHASE_ORDER',header['order_reference']])
def business_key(header,line_reference):
    return digest([order_key(header),line_reference])
def payload(header,rows):
    return {'header':header,'entries':[{'line_reference':r.line_reference,**r.normalized_data} for r in sorted(rows,key=lambda x:x.line_reference)]}
