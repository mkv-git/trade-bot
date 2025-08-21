from pydantic import BaseModel

from tbot.utils.classifiers import ResponseStatus, DictStrAny


class WSResponse(BaseModel):
    status: ResponseStatus
    result: list[DictStrAny] | str
