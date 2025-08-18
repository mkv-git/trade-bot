from typing import Any

from tbot.utils.classifiers import TDictAny


def get_positions(params: TDictAny) -> str:
    query = """
        SELECT *
        FROM positions
        WHERE 1=1
    """

    for p in params.keys():
        query += f" AND {p} = %({p})s "

    return query
