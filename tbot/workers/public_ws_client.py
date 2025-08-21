import asyncio
import argparse
from typing import Any
from asyncio import Queue

import zmq
import orjson
from loguru import logger
from overrides import override
from pydantic import ValidationError

from tbot.utils.helpers import validate
from tbot.config.const import SQL_WORKER_PORT
from tbot.workers.base import AbstractBaseWorker
from tbot.utils.classifiers import ResponseStatus
from tbot.exchanges.bybit.ws_client import PublicWS
from tbot.utils.exceptions import FailedLoadingException
from tbot.models.response.positions import GetPositionsResponse
from tbot.models.response.bot_groups import GetBotGroupsConfigResponse


class PublicWSWorker(AbstractBaseWorker):

    def __init__(self, args):
        super().__init__()

        self.stream_queue = Queue()
        self._ws_publish_port = None
        self._group_id = args.group_id
        self._public_ws = PublicWS("linear")
        self.set_shell_title(f"{self.WORKER} - ID: {self._group_id}")

    @override
    async def run(self):
        logger.info(f"{self.WORKER} started")

        await self.setup_socks_vault()
        await self._load_group_config()

        self.tasks.append(self.start_positions_monitor())
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
        self._ws_publish_port = res_obj.root[0].public_ws_port

    async def start_publisher(self):
        publisher = self.context.socket(zmq.PUB)
        publisher.bind(f"tcp://*:{self._ws_publish_port}")

        while 1:
            msg_filter, payload = await self.stream_queue.get()
            await publisher.send_multipart([msg_filter.encode("utf-8"), orjson.dumps(payload)])

    async def start_positions_monitor(self):
        params = {"bot_group_id": self._group_id, "is_active": True}
        payload = [b"get_positions", orjson.dumps(params)]

        sleep_time = 3
        while 1:
            if not self.socks_vault["sql"]["obj"]:
                logger.debug("SQL Worker offline, trying to reconnect...")
                await asyncio.sleep(sleep_time)
                await self.init_dealer_workers()
                continue

            res = await self.worker_query(payload, self.socks_vault["sql"])
            if not res or res.status == ResponseStatus.ERROR:
                await asyncio.sleep(sleep_time)
                continue

            try:
                res_obj = validate(GetPositionsResponse, res.result)
            except ValidationError as err:
                logger.error(err.json())
                await asyncio.sleep(sleep_time)
                continue

            active_tokens = {"tickers." + r.token for r in res_obj.root}
            existing_subs = set(self._public_ws.subscriptions)

            to_subscribe = active_tokens - existing_subs
            to_unsubscribe = existing_subs - active_tokens

            if not to_subscribe ^ to_unsubscribe:
                await asyncio.sleep(sleep_time)
                continue

            for ticker in to_subscribe:
                await self._public_ws.subscribe(ticker, self.handle_ticker_stream)

            for ticker in to_unsubscribe:
                await self._public_ws.unsubscribe(ticker)

            await asyncio.sleep(sleep_time)

    async def handle_ticker_stream(self, msg: dict[str, Any]):
        topic = msg["topic"]
        await self.stream_queue.put((topic, msg))


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-gi", "--group_id", type=int, required=True)

    args = parser.parse_args()
    await PublicWSWorker(args).run()


if __name__ == "__main__":
    asyncio.run(main())
