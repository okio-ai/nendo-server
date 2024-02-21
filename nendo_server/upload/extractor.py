# -*- encoding: utf-8 -*-
"""Extractor used for handling archives."""
import os
import shutil
import tarfile
import uuid
import zipfile
from abc import ABC, abstractmethod
from typing import List

from api.utils import AudioFileUtils
from pydantic import BaseModel


class ExtractionResult(BaseModel):
    extracted_files: List[str] = []
    extracted_dir: str = ""

    def destroy_extracted_dir(self):
        if os.path.exists(self.extracted_dir):
            shutil.rmtree(self.extracted_dir)


class NendoExtractor(ABC):
    @abstractmethod
    def extract(self, compressed_file: str) -> ExtractionResult:
        raise NotImplementedError

    def _file_path_contains_substrings(self, file_path, substrings):
        # Check if any substring is present in the file path
        return any(substring in file_path for substring in substrings)

    def _is_not_hidden_file(self, file_path):
        return not file_path.startswith(".")

    def _find_supported_files(self, directory):
        exclude_dirs = ["__MACOSX"]
        output_files = []
        audio_utils = AudioFileUtils()
        for root, _, files in os.walk(directory):
            for file in files:
                if (audio_utils.is_supported_filetype(file) and
                    self._is_not_hidden_file(file) and not
                    self._file_path_contains_substrings(root, exclude_dirs)
                ):
                        output_files.append(os.path.join(root, file))

        return output_files


class NendoZipExtractor(NendoExtractor):
    def extract(self, compressed_file: str) -> ExtractionResult:
        # Create a temporary directory to extract the files
        extraction_path = "/tmp/" + uuid.uuid4().hex
        os.makedirs(extraction_path, exist_ok=True)

        # Extract the zip file
        with zipfile.ZipFile(compressed_file, "r") as zip_ref:
            zip_ref.extractall(extraction_path)

        # Recursively find all .wav files in the extracted directory
        output_files = self._find_supported_files(extraction_path)

        return ExtractionResult(
            extracted_files=output_files, extracted_dir=extraction_path,
        )


class NendoTarExtractor(NendoExtractor):
    def extract(self, compressed_file: str) -> ExtractionResult:
        extraction_path = "/tmp/" + uuid.uuid4().hex

        # Check if the file is a .tar or .tar.gz file
        if compressed_file.endswith(".tar"):
            mode = "r"
        elif compressed_file.endswith(".tar.gz"):
            mode = "r:gz"
        else:
            raise ValueError("Invalid file format. Supported formats: .tar, .tar.gz")

        # Extract the files from the compressed file
        with tarfile.open(compressed_file, mode) as tar:
            tar.extractall(path=extraction_path)

        # Recursively find all .wav files in the extracted directory
        output_files = self._find_supported_files(extraction_path)

        return ExtractionResult(
            extracted_files=output_files, extracted_dir=extraction_path,
        )
