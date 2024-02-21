from upload.extractor import (
    NendoTarExtractor,
    NendoZipExtractor,
)


class NendoExtractorFactory:
    def create(self, file_path):
        if file_path.lower().split(".")[-1] == "zip":
            extractor = NendoZipExtractor()

        elif (
            file_path.lower().split(".")[-1] == "tar"
            or file_path.lower().split(".")[-1] == "gz"
        ):
            extractor = NendoTarExtractor()
        else:
            raise Exception("Unable to create extractor for file type: " + file_path)

        return extractor
