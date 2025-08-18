from decimal import Decimal

from pydantic import BaseModel, RootModel, Field


class QueryResponseData(BaseModel):
    token: str
    restart: bool
    order_name: str


GetPositionsResponse = RootModel[list[QueryResponseData]]
