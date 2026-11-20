from typing import Protocol
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models.entities import MockOrder
from .exceptions import U8BusinessError

class U8Client(Protocol):
    def get_inventory(self,code:str)->bool: ...
    def get_vendor(self,code:str)->bool: ...
    def create_purchase_order(self,key:str,payload:dict)->dict: ...
    def query_purchase_order(self,key:str)->dict|None: ...

class MockU8Client:
    """Durable simulated external ledger using independent transactions."""
    def __init__(self,session_factory):
        self.session_factory=session_factory
        self.create_calls=0
        self.query_calls=0
    def get_inventory(self,code):
        return code in {f'MAT-{i:03d}' for i in range(1,301)}
    def get_vendor(self,code): return code=='VENDOR-001'
    def query_purchase_order(self,key):
        self.query_calls+=1
        with self.session_factory() as db:
            order=db.scalar(select(MockOrder).where(MockOrder.order_key==key))
            return {'id':order.id,'payload':order.payload,'mode':'MOCK'} if order else None
    def create_purchase_order(self,key,payload):
        self.create_calls+=1
        if not self.get_vendor(payload['header']['vendor_code']): raise U8BusinessError('供应商不存在')
        if not all(self.get_inventory(r['inventory_code']) for r in payload['entries']): raise U8BusinessError('物料不存在')
        with self.session_factory() as db:
            order=MockOrder(order_key=key,payload=payload)
            db.add(order)
            try: db.commit()
            except IntegrityError:
                db.rollback()
                existing=self.query_purchase_order(key)
                if not existing or existing['payload']!=payload: raise U8BusinessError('订单标识内容冲突')
                return existing
            return {'id':order.id,'payload':order.payload,'mode':'MOCK'}
