from pydantic import BaseModel

from tbot.utils.classifiers import ResponseStatus, TDictAny


class WSResponse(BaseModel):
    status: ResponseStatus
    result: list[TDictAny] | str
