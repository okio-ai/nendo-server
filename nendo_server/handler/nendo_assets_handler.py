# -*- encoding: utf-8 -*-
# ruff: noqa: S603, S607
from __future__ import annotations

import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Optional

from api.utils import AudioFileUtils
from upload.extractor_factory import NendoExtractorFactory

if TYPE_CHECKING:
    import logging
    import uuid

    from nendo import Nendo

class NendoAssetsHandler(ABC):
    nendo_instance: Nendo = None
    logger: logging.Logger = None

    @abstractmethod
    def get_audio_path(
        self,
        track_id: str,
        user_id: Optional[str] = None,
    ) -> str:
        """Get the path to an audio file.

        Args:
            track_id (str): The ID of the target track.
            user_id (str, optional): The ID of the user. Defaults to None.

        Returns:
            str: The path to the file.
        """
        raise NotImplementedError

    @abstractmethod
    def get_user_storage_used(self, user_id: str) -> int:
        """Get the storage used by the user with the given ID.

        Args:
            user_id (str): ID of the user.

        Returns:
            int: Amount of used storage in Kilobytes.
        """
        raise NotImplementedError

    @abstractmethod
    def get_user_storage_size(self, user_id: str) -> int:
        """Get the storage size for the user with the given ID.

        Args:
            user_id (str): ID of the user.

        Returns:
            int: Amount of available storage in Kilobytes.
        """
        raise NotImplementedError

    def user_reached_storage_limit(self, user_id: str) -> bool:
        """Check if the user reached the storage limit.

        Args:
            user_id (str): ID of the user.

        Returns:
            bool: True if the storage limit has been reached. False otherwise.
        """
        if (
            self.get_user_storage_size(user_id) > 0 and
            self.get_user_storage_used(user_id) > self.get_user_storage_size(user_id)
        ):
            return True
        return False

    def get_user_num_tracks(self, user_id: str) -> int:
        """Get the number of tracks in the user's library.

        Args:
            user_id (str): ID of the user.

        Returns:
            int: Number of tracks in user's library.
        """
        return self.nendo_instance.library_size(user_id)

    def add_to_library(
        self,
        file_path: str,
        user_id: Optional[uuid.UUID] = None,
    ) -> List[str]:
        # check the extension of the file is a supported audio file
        if AudioFileUtils().is_supported_filetype(file_path):
            track = self.nendo_instance.library.add_track(
                file_path=file_path,
                user_id=user_id,
            )
            # simple transcoding
            transcoded_library_path = os.path.join(
                track.resource.file_path,
                f"{os.path.splitext(track.resource.file_name)[0]}.mp3",
            )
            if os.path.splitext(file_path)[1] == ".mp3":
                shutil.copy(file_path, transcoded_library_path)
            else:
                subprocess.call([
                    "ffmpeg",
                    "-i",
                    file_path,
                    "-ab",
                    "320k",
                    transcoded_library_path,
                ])
            return [str(track.id)] if track is not None else []

        supported_compressed_types = ["zip", "tar", "gz"]
        if file_path.lower().split(".")[-1] not in supported_compressed_types:
            return []

        extractor = NendoExtractorFactory().create(file_path)
        if extractor is None:
            return []

        extraction_result = extractor.extract(file_path)
        try:
            all_track_ids = []
            for file in extraction_result.extracted_files:
                track = self.nendo_instance.library.add_track(
                    file_path=file, user_id=user_id,
                )

                if track is None:
                    self.logger.error(f"Failed to add file: {file}")
                else:
                    all_track_ids.append(str(track.id))
        except Exception as e:
            self.logger.error(f"Error adding files to library: {e}")
            extraction_result.destroy_extracted_dir()
            return []

        extraction_result.destroy_extracted_dir()
        return all_track_ids

    # def add_to_library_as_collection(
    #     self,
    #     file_path: str,
    #     collection_name: str,
    #     user_id: Optional[uuid.UUID] = None,
    # ) -> Optional[str]:
    #     # check the extension of the file is a supported audio file
    #     new_collection = self.nendo_instance.library.add_collection(
    #         name=collection_name,
    #         user_id=user_id,
    #     )
    #     if AudioFileUtils().is_supported_filetype(file_path):
    #         track = self.nendo_instance.library.add_track(
    #             file_path=file_path, user_id=user_id,
    #         )

    #         self.nendo_instance.library.add_track_to_collection(
    #             track_id=track.id,
    #             collection_id=new_collection.id,
    #         )

    #         return str(new_collection.id)

    #     supported_compressed_types = ["zip", "tar", "gz"]
    #     if file_path.lower().split(".")[-1] not in supported_compressed_types:
    #         return None

    #     extractor = NendoExtractorFactory().create(file_path)
    #     if extractor is None:
    #         return None

    #     extraction_result = extractor.extract(file_path)
    #     try:
    #         for file in extraction_result.extracted_files:
    #             track = self.nendo_instance.library.add_track(
    #                 file_path=file, user_id=user_id,
    #             )
    #             self.nendo_instance.library.add_track_to_collection(
    #                 track_id=track.id,
    #                 collection_id=new_collection.id,
    #             )

    #             if track is None:
    #                 self.logger.error(f"FAILED TO ADD FILE: {file}")

    #     except Exception as e:
    #         self.logger.error(f"Error adding files to library: {e}")
    #         extraction_result.destroy_extracted_dir()
    #         return None

    #     extraction_result.destroy_extracted_dir()
    #     return str(new_collection.id)


class LocalAssetsHandler(NendoAssetsHandler):
    def __init__(self, nendo_instance, config, logger):
        self.nendo_instance = nendo_instance
        self.config = config
        self.logger = logger

    def get_audio_path(self, track_id: str, user_id: Optional[str] = None) -> str:
        track = self.nendo_instance.library.get_track(
            track_id=track_id, user_id=user_id,
        )
        if track is None:
            return None

        return track.resource.src  # track.local(user_id=user_id)

    def get_collection_audio_paths(
        self, collection_id: str, bucket_name: str = "",
    ) -> List[str]:
        tracks = self.nendo_instance.library.get_collection_tracks(
            collection_id=collection_id,
        )
        if len(tracks) == 0:
            return None
        return [track.resource.src for track in tracks]

    def get_tracks_audio_paths(
        self, track_ids: List[str], bucket_name: str = "",
    ) -> List[str]:
        tracks_paths = []
        for track_id in track_ids:
            track = self.nendo_instance.library.get_track(
                track_id=track_id,
            )
            tracks_paths.append(track.resource.src)
        return tracks_paths

    def get_image_path(
        self,
        image_file_name: str,
        user_id: Optional[str] = None,
    ) -> str:
        # TODO this is hacky because images are not first class citizen yet
        return os.path.join(
            self.nendo_instance.config.library_path,
            "images/",
            image_file_name,
        )

    def get_user_storage_used(self, user_id: str) -> int:
        path = os.path.join(
            self.nendo_instance.config.library_path,
            user_id,
        )
        return int(subprocess.check_output(["du","-s", path]).split()[0].decode("utf-8"))

    def get_user_storage_size(self, user_id: str) -> int:
        # TODO allow per-user storage size
        return self.config.user_storage_size


class RemoteAssetsHandler(NendoAssetsHandler):
    def __init__(self, nendo_instance, config, logger):
        self.nendo_instance = nendo_instance
        self.config = config
        self.logger = logger

    def get_audio_path(self, track_id: str, user_id: Optional[str] = None) -> str:
        track = self.nendo_instance.library.get_track(
            track_id=track_id, user_id=user_id,
        )
        if track is None:
            return None

        return f"https://storage.googleapis.com/{user_id}/{track.resource.file_name}"

    def get_collection_audio_paths(
        self,
        collection_id: str,
        bucket_name: str = "",
    ) -> List[str]:
        tracks = self.nendo_instance.library.get_collection_tracks(
            collection_id=collection_id,
        )
        if len(tracks) == 0:
            return None
        return [
            f"https://storage.googleapis.com/{bucket_name}/{track.resource.file_name}"
            for track in tracks
        ]

    def get_tracks_audio_paths(
        self, track_ids: List[str], bucket_name: str = "",
    ) -> List[str]:
        raise NotImplementedError

    def get_image_path(
        self,
        image_id: str,
        user_id: str,
    ) -> str:
        # TODO implement
        raise NotImplementedError

    def get_user_storage_used(self, user_id: str) -> int:
        # TODO implement
        raise NotImplementedError

    def get_user_storage_size(self, user_id: str) -> int:
        # TODO allow per-user storage size
        # TODO implement
        raise NotImplementedError
