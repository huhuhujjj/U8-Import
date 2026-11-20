"""Source-column semantics only; source totals are not compared or submitted."""
import re


def compact(value):
    return re.sub(r'[\s_()（）\-]', '', str(value).lower())


def is_amount(value):
    name = compact(value)
    return any(word in name for word in ('金额', '合计', '总额', '税额', 'amount', 'total', 'money')) or name in ('sum', 'tax')


def basis(value):
    name = compact(value)
    # Negative forms must precede the positive substring (不含税 contains 含税).
    if any(word in name for word in ('不含税', '未税', '无税', 'excludingtax', 'exclusivetax', 'taxexclusive', 'excltax', 'netamount', 'netprice')) or name == 'money':
        return 'EXCLUSIVE'
    if any(word in name for word in ('含税', 'includingtax', 'inclusivetax', 'taxinclusive', 'incltax', 'gross', 'taxprice')) or name == 'sum':
        return 'INCLUSIVE'
    return None


def mapping_error(headers, mapping, header):
    label = headers.get(mapping.get('price'), '')
    if is_amount(label):
        return f'源列“{label}”是金额列，不能映射为单价'
    explicit = basis(label)
    if explicit and explicit != header.get('price_mode', 'EXCLUSIVE'):
        return f'单价列“{label}”与所选含税/不含税模式不一致，请确认税口径'
    return None
