import hmac
from decimal import Decimal
from typing import Any, Type

from pydantic import ValidationError

from tbot.utils.classifiers import MODEL


def generate_signature(api_secret: str, expires: int) -> str:
    signature = str(
        hmac.new(
            bytes(api_secret, "utf-8"), bytes(f"GET/realtime{expires}", "utf-8"), digestmod="sha256"
        ).hexdigest()
    )

    return signature


def validate(model: Type[MODEL], params: Any) -> MODEL:
    return model.model_validate(params)


def default_serializer(obj):
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError
