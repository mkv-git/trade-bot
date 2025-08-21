from pydantic import BaseModel, RootModel


class BotGroupsConfigData(BaseModel):
    id: int
    trade_ws_port: int
    public_ws_port: int
    private_ws_port: int
    rest_api_ws_port: int


GetBotGroupsConfigResponse = RootModel[list[BotGroupsConfigData]]


class BotGroupsSecretsData(BaseModel):
    id: int
    api_key: str
    api_secret: str


GetBotGroupsSecretsResponse = RootModel[list[BotGroupsSecretsData]]
