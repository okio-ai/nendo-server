# -*- encoding: utf-8 -*-
# ruff: noqa: S311, T201
"""The Nendo server actions handler."""
from __future__ import annotations

import datetime
import json
import os
import pprint
import random
import string
import time
import uuid
from typing import TYPE_CHECKING, List, Optional

import docker
import librosa
from docker.types import DeviceRequest
from dto.actions import ActionStatus
from nendo import NendoCollection, NendoTrack
from rq.command import send_stop_job_command
from rq.job import Job

if TYPE_CHECKING:
    from pydantic_settings import BaseSettings


def dockerized_func(
    user_id: str,
    image: str,
    script_path: str,
    command: str,
    plugins: List[str],
    nendo_cfg: BaseSettings,
    cfg: BaseSettings,
    use_gpu: bool = True,
    container_name: Optional[str] = None,
    exec_run: bool = False,
    replace_plugin_data: bool = False,
    env: Optional[dict] = None,
    func_timeout: int = 0,  # 0 means no timeout
) -> str:
    """Run python code in a docker container.

    Args:
    ----
        user_id (str): The ID of the user calling the action.
        image (str): The name of the docker image in which to run the code.
        plugins (List[str]): List of plugins to configure nendo with.
        command (str): The python code to run in the container, formatted as a string.
        cfg (BaseSettings): The Nendo configuration of the server.
        container_name (str, optional): The name of the docker container
            to use when running.
        exec_run (bool, optional): If True, an existing container with the name given as
            `container_name` will be used to run the code given as `command` in. If False,
            a new container will be created with the name `container_name` (no container
            with that name must exist). Defaults to False.
        replace_plugin_data (bool, optional): If True, newly created plugin data will
            replace existing plugin data. If False, the old plugin data will be kept.
            Defaults to False.
        env (dict, optional): Dictionary containing custom environment variables for the action.
            Can be used to configure Nendo and its plugins.
        func_timeout (int, optional): The timeout before the function will be considered
            stalled and the container will be killed. If 0, no timeout detection will be
            applied. Defaults to 0.

    Returns:
    -------
        str: The last line of the container log. This will be the `job.return` value
        of the RQ job, so make sure that your action code prints whatever it wants
        the `job.status` to assume as it's last call in the code.
    """
    use_gpu = use_gpu and cfg.use_gpu
    client = docker.from_env()
    image_name = image
    env_vars = {
        "LIBRARY_PLUGIN": cfg.container_library_plugin,
        "LIBRARY_PATH": cfg.container_library_path,
        "LOG_LEVEL": cfg.log_level,
        "USER_ID": user_id,
        "PLUGINS": json.dumps(plugins),
        "POSTGRES_HOST": cfg.container_postgres_host,
        "POSTGRES_USER": cfg.container_postgres_user,
        "POSTGRES_PASSWORD": cfg.container_postgres_password,
        "POSTGRES_DB": cfg.container_postgres_db,
        "USE_GPU": use_gpu,
        "REPLACE_PLUGIN_DATA": replace_plugin_data,
        "AUTO_RESAMPLE": nendo_cfg.auto_resample,
        "DEFAULT_SR": nendo_cfg.default_sr,
        "COPY_TO_LIBRARY": nendo_cfg.copy_to_library,
        "AUTO_CONVERT": nendo_cfg.auto_convert,
        "SKIP_DUPLICATE": nendo_cfg.skip_duplicate,
    }
    if env is not None:
        env_vars.update(env)
    volume_mounts = {
        os.path.join(
            cfg.container_host_base_path,
            "library",
        ): {
            "bind": cfg.container_library_path,
            "mode": "rw",
        },
        os.path.join(
            cfg.container_host_apps_path,
            script_path,
        ): {
            "bind": "/home/nendo/run.py",
            "mode": "ro",
        },
        "hf-models-cache": {
            "bind": "/home/nendo/.cache/",
            "mode": "rw",
        },
    }
    start_time = datetime.datetime.now(tz=datetime.timezone.utc)

    # start the container
    if exec_run is False:
        if use_gpu is True:
            # configure GPU access
            device_requests = []
            device_requests.append(DeviceRequest(count=-1, capabilities=[["gpu"]]))
            ulimits = [
                docker.types.Ulimit(name="memlock", soft=-1, hard=-1),
                docker.types.Ulimit(name="stack", soft=67108864, hard=67108864),
            ]
            container = client.containers.run(
                image_name,
                command,
                name=container_name,
                environment=env_vars,
                volumes=volume_mounts,
                shm_size="1G",
                ipc_mode="host",
                network=cfg.docker_network_name,
                device_requests=device_requests,
                detach=True,
                ulimits=ulimits,
            )
        else:
            container = client.containers.run(
                image_name,
                command,
                name=container_name,
                environment=env_vars,
                volumes=volume_mounts,
                network=cfg.docker_network_name,
                detach=True,
            )

        while True:
            # Check the current time and calculate elapsed time
            current_time = datetime.datetime.now(tz=datetime.timezone.utc)
            elapsed_time = (current_time - start_time).total_seconds()

            # Check if the timeout has been reached
            if (func_timeout > 0) and (elapsed_time > func_timeout):
                print(f"Timeout reached. Stopping container {container.id}")
                container.stop()
                break

            # Reload the container's state and check if it has stopped
            container.reload()
            if container.status == "exited":
                print(f"Container {container.id} has stopped.")
                break

            time.sleep(2)

        exit_code = container.attrs["State"]["ExitCode"]
        if exit_code != 0:
            err_log = container.logs(stderr=True, stdout=False)
            err_log = err_log.decode("utf-8").split("\n")
            # only get last 5 lines of err log
            if len(err_log) > 5:
                err_log = err_log[-5:]
            "\n".join(err_log)
            raise Exception(err_log)

        # get quantized track ID from logs
        log_lines = container.logs(stderr=True, stdout=True).decode("utf-8").split("\n")

        # clean up container
        container.remove()

        # Return the last line (excluding any empty line at the end)
        return log_lines[-2] if log_lines[-1] == "" else log_lines[-1]

    # exec_run
    container = client.containers.get(container_name)
    exit_code, output = container.exec_run(
        command,
        environment=env_vars,
    )
    if exit_code != 0:
        # only get last 5 lines of err log
        if len(output) > 5:
            output = output[-5:]
        "\n".join(output)
        raise Exception(output)
    output = output.decode("utf-8").split("\n")

    def is_valid_uuid4(arbitraty_string):
        try:
            return uuid.UUID(arbitraty_string).version == 4
        except ValueError:
            return False

    ids = [s for s in output if is_valid_uuid4(s.split("/",1))]
    return ids[-1]


class NendoActionsHandler:
    """Nendo actions handler."""

    def __init__(self, nendo_config, server_config, nendo_instance, logger, redis, worker_manager):
        self.nendo_config = nendo_config
        self.server_config = server_config
        self.nendo_instance = nendo_instance
        self.logger = logger
        self.redis = redis
        self.worker_manager = worker_manager

    def _generate_command(self, user_id, job_id, **kwargs):
        # args_str = " ".join(str(arg) for arg in args)
        kwargs_str = f"--user_id {user_id} --job_id {job_id} "
        for key, value in kwargs.items():
            if isinstance(value, bool):
                if value is True:
                    kwargs_str += f"--{key} "
            elif isinstance(value, str):
                kwargs_str += f'--{key}="{value}" '
            elif isinstance(value, (float, int, uuid.UUID)):
                kwargs_str += f"--{key}={value} "
            elif isinstance(value, list):
                kwargs_str += f"--{key} "
                for item in value:
                    kwargs_str += f"{item} "
            else:
                raise Exception(
                    f"Unsupported parameter type: {key} (type {type(value)})",
                )
        return f'python run.py {kwargs_str}'  # noqa: Q000

    def _get_all_job_ids(self, user_id: str):
        queues = self.worker_manager.get_user_queues(user_id)
        job_ids = []
        for queue in queues:
            if queue is not None:
                job_ids += queue.job_ids
                job_ids += queue.started_job_registry.get_job_ids()
                job_ids += queue.deferred_job_registry.get_job_ids()
                job_ids += queue.finished_job_registry.get_job_ids()
                job_ids += queue.failed_job_registry.get_job_ids()
                job_ids += queue.scheduled_job_registry.get_job_ids()
        return job_ids

    def create_action(
        self,
        user_id: str,
        action_name: str,
        gpu: bool,
        func,
        *args,
        **kwargs,
    ) -> str:
        cpu_queue, gpu_queue = self.worker_manager.get_user_queues(user_id)
        queue = gpu_queue if gpu else cpu_queue
        job = queue.enqueue(
            func,
            *args,
            **kwargs,
            description=action_name,
            result_ttl="172800",  # 2 days retention
        )
        job.meta["action_name"] = action_name
        job.meta["parameters"] = pprint.pformat(kwargs)
        job.meta["target_id"] = kwargs.get("target_id", "")
        job.save_meta()
        return job.id

    def create_docker_action(
        self,
        user_id: str,
        image: str,
        gpu: bool,
        script_path: str,
        plugins: list,
        action_name: str,
        container_name: str,
        exec_run: bool,
        replace_plugin_data: bool,
        run_without_target: bool,
        max_track_duration: float,
        max_chunk_duration: float,
        env: Optional[dict] = None,
        func_timeout: int = 0,
        **kwargs, # these are the parameters for the action script
    ) -> str:
        # get queues
        gpu = gpu and self.server_config.use_gpu
        cpu_queue, gpu_queue = self.worker_manager.get_user_queues(user_id)
        queue = gpu_queue if gpu else cpu_queue
        
        # assign job and container name
        letters_and_digits = string.ascii_letters + string.digits
        rnd_string = "".join(random.choice(letters_and_digits) for i in range(8))
        job_id = action_name.replace(" ", "_") + "_" + rnd_string
        container_name = container_name if exec_run is True else job_id
        
        target_id = kwargs.get("target_id", "")
        track_or_collection = self.nendo_instance.get_track_or_collection(
            target_id,
        )
        target = {}
        if track_or_collection is not None:
            target.update({
                "target_type": (
                    "track" if isinstance(track_or_collection, NendoTrack) else
                    "collection",
                )
            })
            target.update({
                "target_id": target_id,
            })
        target_collections = []
        skipped_tracks = []
        # apply chunking, if configured and applicable
        if (self.server_config.chunk_actions and not run_without_target and
            run_without_target is False
            and gpu is True
        ):
            track_ids = []
            # create a single chunk with the track in it
            if isinstance(track_or_collection, NendoTrack):
                # get track duration
                duration = track_or_collection.get_meta("duration")
                if duration is None:
                    duration = round(librosa.get_duration(
                        y=track_or_collection.signal,
                        sr=track_or_collection.sr
                    ), 1)
                # skip track if duration exceeds maximum
                if max_track_duration > 0. and duration > max_track_duration:
                    skipped_tracks.append(track_or_collection.get_meta("title"))
                else:
                    track_ids.append(track_or_collection.id)
                chunk_collection = self.nendo_instance.add_collection(
                    name=job_id,
                    user_id=user_id,
                    track_ids=track_ids,
                    collection_type="temp",
                )
                target_collections.append(chunk_collection.id)
            else:
                # split collection into chunks
                if isinstance(track_or_collection, NendoCollection):
                    tracks = track_or_collection.tracks()
                # split the library into chunks
                else:
                    tracks = self.nendo_instance.library.get_tracks(
                        user_id=user_id
                    )
                chunk_duration = 0.
                chunk_nr = 0
                chunk_collection = self.nendo_instance.library.add_collection(
                    name=f"{job_id}_{chunk_nr}",
                    user_id=user_id,
                    track_ids=[],
                    collection_type="temp",
                )
                target_collections.append(chunk_collection.id)
                for track in tracks:
                    # get track duration
                    duration = track.get_meta("duration")
                    if duration is None:
                        duration = round(librosa.get_duration(
                            y=track.signal,
                            sr=track.sr
                        ), 1)
                    # skip track if duration exceeds maximum
                    if max_track_duration > 0 and duration > max_track_duration:
                        skipped_tracks.append(track.get_meta("title"))
                    else:
                        # if it fits, append to last chunk
                        if (max_chunk_duration > 0. and 
                            (chunk_duration + duration <= max_chunk_duration)
                        ):
                            self.nendo_instance.library.add_track_to_collection(
                                track_id=track.id,
                                collection_id=chunk_collection.id,
                            )
                            chunk_duration += duration
                        # otherwise create new chunk
                        else:
                            chunk_nr += 1
                            chunk_collection = self.nendo_instance.library.add_collection(
                                name=f"{job_id}_{chunk_nr}",
                                user_id=user_id,
                                track_ids=[],
                                collection_type="temp",
                            )
                            target_collections.append(chunk_collection.id)
                            chunk_duration = 0.
        else:
            if isinstance(track_or_collection, NendoTrack):
                temp_collection = self.nendo_instance.library.add_collection(
                    name=job_id,
                    user_id=user_id,
                    track_ids=[track_or_collection.id],
                    collection_type="temp",
                )
                target_collections.append(temp_collection.id)
            elif isinstance(track_or_collection, NendoCollection):
                target_collections.append(track_or_collection.id)
            elif run_without_target is False:
                temp_collection = self.nendo_instance.library.add_collection(
                    name=job_id,
                    user_id=user_id,
                    track_ids=self.nendo_instance.library.get_tracks(),
                    collection_type="temp",
                )
                target_collections.append(temp_collection.id)
            else:
                target_collections.append("")

        # create actions
        for i, collection_id in enumerate(target_collections):
            kwargs["target_id"] = str(collection_id)
            command = self._generate_command(
                user_id,
                f"{job_id}_{i}",
                **kwargs,
            )
            action = queue.enqueue(
                dockerized_func,
                user_id,
                image,
                script_path,
                command,
                plugins,
                self.nendo_config,
                self.server_config,
                gpu,
                f"{container_name}_{i}",
                exec_run,
                replace_plugin_data,
                env,
                func_timeout,
                description=action_name,  # TODO improve description?
                job_id=f"{job_id}_{i}",  # use custom job id (for in-job status reporting)
                job_timeout="72h",  # TODO: make this configurable?
                result_ttl="172800",  # 2 days retention of completed jobs
            )
            action.meta["action_name"] = action_name
            action.meta["parameters"] = pprint.pformat(kwargs)
            action.meta["target"] = target
            action.save_meta()
        # add the skipped tracks to the last action's meta
        action.meta["errors"] = [
            f"Skipped {track}: Too long." for track in skipped_tracks
        ]
        action.save_meta()
        # return the last job's ID
        return action.id

    def get_action_status(self, user_id: str, action_id: str) -> str:
        try:
            job_ids = self._get_all_job_ids(user_id)
            if action_id in job_ids:
                job = Job.fetch(action_id, connection=self.redis)
            else:
                raise ValueError("Action not found in user's queue")
        except Exception as e:
            # Handle exceptions, like job not found or Redis connection issues
            self.logger.error(f"Error getting actions status: {e}")
            return None

        return ActionStatus(
            id=action_id,
            enqueued_at=str(job.enqueued_at),
            started_at=str(job.started_at),
            ended_at=str(job.ended_at),
            status=job.get_status(),
            meta=job.get_meta(),
            result=str(job.result),
            exc_info=job.exc_info,
        )

    def get_all_action_statuses(self, user_id: str) -> str:
        all_actions = []
        job_ids = self._get_all_job_ids(user_id)
        for job_id in job_ids:
            job = Job.fetch(job_id, connection=self.redis)
            all_actions.append(
                ActionStatus(
                    id=job.id,
                    enqueued_at=str(job.enqueued_at),
                    started_at=str(job.started_at),
                    ended_at=str(job.ended_at),
                    status=job.get_status(),
                    meta=job.get_meta(),
                    result=job.result,
                    exc_info=job.exc_info,
                ),
            )

        # TODO sort all_actions by timestamp?

        return all_actions

    def abort_action(self, user_id: str, action_id: str) -> bool:
        try:
            job_ids = self._get_all_job_ids(user_id)
            if action_id in job_ids:
                job = Job.fetch(action_id, connection=self.redis)
                job_status = job.get_status()
                if job_status == "queued":
                    job.cancel()
                else:
                    send_stop_job_command(self.redis, action_id)
            else:
                raise ValueError("Job not found in user's queue.")
            # also stop and clean up the running container
            client = docker.from_env()
            container = client.containers.get(action_id)
            container.kill()  # brutal, but .stop() might freeze
            container.remove()
            return True
        except Exception as e:
            # Handle exceptions, like job not found or Redis connection issues
            self.logger.error(f"Error aborting action: {e}")
            return False


class LocalActionsHandler(NendoActionsHandler):
    pass


class RemoteActionsHandler(NendoActionsHandler):
    pass
