from tbot.utils.classifiers import DictStrAny


def get_positions(params: DictStrAny) -> str:
    query = """
        SELECT *
        FROM positions
        WHERE 1=1
    """

    for p in params.keys():
        query += f" AND {p} = %({p})s "

    return query
