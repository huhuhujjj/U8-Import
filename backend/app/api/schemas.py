from datetime import date
from decimal import Decimal
from typing import Literal, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid',str_strip_whitespace=True)
class OrderHeader(BaseModel):
    model_config = ConfigDict(extra='allow',str_strip_whitespace=True)
    order_reference: str = Field(default='',max_length=100)
    vendor_code: str = Field(min_length=1,max_length=100)
    order_date: date
    price_mode: Literal['EXCLUSIVE','INCLUSIVE'] = 'EXCLUSIVE'
    tax_rate: Decimal = Field(default=Decimal('13'), ge=0, le=100, decimal_places=4)
    currency_name: Literal['人民币'] = '人民币'
    purchase_type_code: str = Field(default='', max_length=30)
    deptcode: str = Field(default='', max_length=30)
    personcode: str = Field(default='', max_length=30)
    maker: str = Field(default='', max_length=50)
    remark: str = Field(default='', max_length=200)
class RowInput(StrictModel):
    source_row: int = Field(ge=1)
    line_reference: str = Field(min_length=1,max_length=100)
    raw_data: dict[str,Any]
    normalized_data: dict[str,Any]
class ImportInput(StrictModel):
    business_type: Literal['PURCHASE_ORDER'] = 'PURCHASE_ORDER'
    file_name: str = Field(min_length=1,max_length=255)
    mapping: dict[str,str]
    source_headers: dict[str,str] = {}
    header: OrderHeader
    rows: list[RowInput] = Field(min_length=1,max_length=10000)
    @field_validator('mapping')
    @classmethod
    def mapping_valid(cls,v):
        if set(v) != {'inventory_code','quantity','price'} or any(not x.strip() for x in v.values()) or len(set(v.values())) != 3:
            raise ValueError('必须为物料编码、数量和单价指定三个不同来源列')
        return v
    @model_validator(mode='after')
    def unique_lines(self):
        if len({r.line_reference for r in self.rows})!=len(self.rows):
            raise ValueError('订单明细标识重复')
        return self
class MappingInput(StrictModel):
    template_name: str = Field(min_length=1,max_length=100)
    mapping: dict[str,str]
    source_headers: dict[str,str] = {}
    _mapping = field_validator('mapping')(ImportInput.mapping_valid.__func__)
