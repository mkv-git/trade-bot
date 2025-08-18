from typing import Generic, Any

from pydantic import BaseModel

from tbot.utils.classifiers import REQ


class WSRequest(BaseModel, Generic[REQ]):
    ident: str
    process_name: str
    process_params: dict[str, Any] | None = None
