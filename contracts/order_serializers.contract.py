from typing import TypedDict, List
from decimal import Decimal
from uuid import UUID

class OrderItemContract(TypedDict):
    product_id: str
    quantity: int
    unit_price: Decimal

class CreateOrderRequestContract(TypedDict):
    customer_id: UUID
    items: List[OrderItemContract]
    total_amount: Decimal
    currency: str
    idempotency_key: str

class OrderResponseContract(TypedDict):
    order_id: UUID
    status: str
    created_at: str
    correlation_id: str

class IOrderServiceContract:
    def create_order(self, data: CreateOrderRequestContract) -> OrderResponseContract:
        ...

    def is_idempotent(self, idempotency_key: str) -> bool:
        ...
