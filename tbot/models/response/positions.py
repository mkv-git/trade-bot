from pydantic import BaseModel, RootModel


class PositionsData(BaseModel):
    token: str
    restart: bool
    order_name: str


GetPositionsResponse = RootModel[list[PositionsData]]
