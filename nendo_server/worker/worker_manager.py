# -*- encoding: utf-8 -*-
"""The Nendo API Server worker manager."""

import subprocess
from abc import ABC, abstractmethod
from logging import Logger
from typing import List, Optional, Tuple

from config import Settings
from redis import Redis
from rq import Connection, Queue, Worker
from rq.command import send_shutdown_command


class WorkerManager(ABC):
    """Class for managing action queues and workers."""
    server_config: Settings
    logger: Logger
    redis: Redis
    user_ids: List[str]

    @abstractmethod
    def init_queues_and_workers(self, user_ids = List[str]):
        raise NotImplementedError

    @abstractmethod
    def get_user_queues(self, user_id: str):
        raise NotImplementedError

    @abstractmethod
    def spawn_cpu_workers(self, user_id: str):
        raise NotImplementedError

    @abstractmethod
    def spawn_gpu_workers(self):
        raise NotImplementedError


class LocalWorkerManager(WorkerManager):
    """Local manager for action queues and workers."""

    def __init__(self, server_config, logger, redis):
        self.server_config = server_config
        self.logger = logger
        self.redis = redis

    def _get_user_ids_from_cpu_workers(self):
        all_user_ids = set()
        with Connection(self.redis):
            workers = Worker.all()
            for worker in workers:
                for queue_name in worker.queue_names():
                    all_user_ids.add(queue_name[:36])
        return list(all_user_ids)

    def _get_user_worker_pids(self, queue_id):
        # Check if a all workers of the user are already running
        worker_pids = []
        with Connection(self.redis):
            workers = Worker.all()
            for worker in workers:
                if queue_id in worker.queue_names():
                    worker_pids.append(worker.pid)
        return worker_pids

    def get_user_queues(self, user_id: str) -> Tuple[Queue, Optional[Queue]]:
        cpu_queue = Queue(user_id, connection=self.redis)
        gpu_queue = None
        if self.server_config.use_gpu:
            gpu_queue = Queue(f"{user_id}-gpu", connection=self.redis)
        return cpu_queue, gpu_queue

    def get_gpu_queues(self) -> List[Queue]:
        user_ids = self._get_user_ids_from_cpu_workers()
        return [Queue(f"{user_id}-gpu", connection=self.redis) for user_id in user_ids]

    def spawn_cpu_workers(self, user_id: str):
        cfg = self.server_config
        existing_user_worker_pids = self._get_user_worker_pids(user_id)

        # spawn user's CPU workers
        for _ in range(cfg.num_user_cpu_workers - len(existing_user_worker_pids)):
            subprocess.Popen(
                [  # noqa: S603, S607
                    "rq",
                    "worker",
                    "-u",
                    (f"redis://{cfg.redis_user}:{cfg.redis_password}@"
                     f"{cfg.redis_host}:{cfg.redis_port}/{cfg.redis_db}"),
                    user_id,
                ],
                start_new_session=True,
            )

    def spawn_gpu_workers(self, user_ids: Optional[List[str]] = None):
        cfg = self.server_config
        if not user_ids:
            user_ids = self._get_user_ids_from_cpu_workers()
        gpu_queues = [user_id+"-gpu" for user_id in user_ids]

        # first, gracefully terminate all existing workers
        with Connection(self.redis):
            workers = Worker.all()
            for worker in workers:
                for queue_name in worker.queue_names():
                    if "-gpu" in queue_name:
                        send_shutdown_command(self.redis, worker.name)
        # then, (re-)spawn gpu workers with user gpu queues
        for _ in range(cfg.num_gpu_workers):
            subprocess.Popen(
                [  # noqa: S603, S607
                    "rq",
                    "worker",
                    "--dequeue-strategy",
                    "round_robin",
                    "-u",
                    (f"redis://{cfg.redis_user}:{cfg.redis_password}@"
                     f"{cfg.redis_host}:{cfg.redis_port}/{cfg.redis_db}"),
                    *gpu_queues,
                ],
                start_new_session=True,
            )

    def init_queues_and_workers(self, user_ids = List[str]):
        for user_id in user_ids:
            cpu_queue, gpu_queue = self.get_user_queues(user_id)
            self.spawn_cpu_workers(user_id)
        if self.server_config.use_gpu:
            self.spawn_gpu_workers(user_ids)


# remote is currently the same as local
class RemoteWorkerManager(LocalWorkerManager):
    """Remote manager for action queues and workers."""
