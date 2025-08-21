import asyncio
import argparse
from asyncio import Queue

import zmq
import orjson
from loguru import logger
from overrides import override

from tbot.utils.helpers import validate
from tbot.config.const import SQL_WORKER_PORT
from tbot.workers.base import AbstractBaseWorker
from tbot.exchanges.bybit.ws_client import PrivateWS
from tbot.utils.exceptions import FailedLoadingException
from tbot.utils.classifiers import ResponseStatus, DictStrAny
from tbot.models.response.bot_groups import (
    GetBotGroupsConfigResponse,
    GetBotGroupsSecretsResponse,
)


class PrivateWSWorker(AbstractBaseWorker):

    def __init__(self, args):
        super().__init__()

        self.stream_queue = Queue()
        self._group_id = args.group_id
        self._api_key = None
        self._api_secret = None
        self._private_ws = None
        self._ws_publish_port = None
        self.set_shell_title(f"{self.WORKER} - ID: {self._group_id}")

    @override
    async def run(self):
        logger.info(f"{self.WORKER} started")

        await self.setup_socks_vault()
        await self._load_group_config()
        await self._load_group_secrets()

        self._private_ws = PrivateWS(
            "private", demo=True, api_key=self._api_key, api_secret=self._api_secret
        )

        await self._private_ws.subscribe("order", self._handle_messages)
        await self._private_ws.subscribe("wallet", self._handle_messages)
        await self._private_ws.subscribe("position", self._handle_messages)

        self.tasks.append(self.start_publisher())
        await asyncio.gather(*self.tasks)

        logger.info(f"{self.WORKER} finished.")

    @override
    async def setup_socks_vault(self):
        self.socks_vault = {
            "sql": {
                "obj": None,
                "identity": f"{self.WORKER}-{self._group_id}".encode("utf-8"),
                "connection": f"tcp://localhost:{SQL_WORKER_PORT}",
            },
        }

        await self.init_dealer_workers()

    async def _load_group_config(self):
        params = {"bot_group_id": self._group_id}
        payload = [b"get_bot_group_config", orjson.dumps(params)]

        res = await self.worker_query(payload, self.socks_vault["sql"])
        if not res or res.status == ResponseStatus.ERROR:
            raise FailedLoadingException("Group config loading failed")

        res_obj = validate(GetBotGroupsConfigResponse, res.result)
        self._ws_publish_port = res_obj.root[0].private_ws_port

    async def _load_group_secrets(self):
        params = {"bot_group_id": self._group_id, "permission": "R", "is_active": True}
        payload = [b"get_bot_group_secrets", orjson.dumps(params)]
        res = await self.worker_query(payload, self.socks_vault["sql"])
        if not res or res.status == ResponseStatus.ERROR:
            raise FailedLoadingException("Group secrets loading failed")

        res_obj = validate(GetBotGroupsSecretsResponse, res.result)
        self._api_key = res_obj.root[0].api_key
        self._api_secret = res_obj.root[0].api_secret

    async def _handle_wallet_stream(self, msg: DictStrAny):
        topic = msg['topic']
        await self.stream_queue.put((topic, msg))

    async def _handle_messages(self, msg: DictStrAny):
        topic = msg['topic']
        symbol = msg["data"][0]["symbol"]
        msg_filter = f"{topic}.{symbol}"

        await self.stream_queue.put((msg_filter, msg))

    async def start_publisher(self):
        publisher = self.context.socket(zmq.PUB)
        publisher.bind(f"tcp://*:{self._ws_publish_port}")

        while 1:
            msg_filter, payload = await self.stream_queue.get()
            await publisher.send_multipart([msg_filter.encode("utf-8"), orjson.dumps(payload)])


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-gi", "--group_id", type=int, required=True)

    args = parser.parse_args()
    await PrivateWSWorker(args).run()


if __name__ == "__main__":
    asyncio.run(main())
