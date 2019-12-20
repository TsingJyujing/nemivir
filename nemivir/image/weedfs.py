from typing import BinaryIO, Callable

import requests
from io import BytesIO
from urllib.parse import urljoin, urlencode


class WeedFiler:
    def __init__(
            self,
            filer_node: str,
    ):
        """
        API For weed filer
        :param filer_node:
        """
        self.filer_node = filer_node

    def write_file(self, file_path: str, io: BinaryIO):
        """
        Write file to filer server
        :param file_path:
        :param io:
        :return:
        """
        response = requests.post(
            urljoin(self.filer_node, file_path),
            files=dict(file=io)
        )
        response.raise_for_status()
        return response.json()

    def write_data(self, file_path: str, data: bytes):
        """
        Write a file by data
        :param file_path:
        :param data:
        :return:
        """
        with BytesIO(data) as io:
            return self.write_file(file_path, io)

    def __list_all(self, path: str, limit: int = 10000) -> list:
        """
        List all files in dir
        :param limit:
        :param path:
        :return:
        """
        response = requests.get(
            urljoin(self.filer_node, path),
            params=urlencode(dict(
                limit=limit
            )),
            headers={
                "Accept": "application/json"
            }
        )
        response.raise_for_status()
        data = response.json()["Entries"]
        return [] if data is None else data

    def list_dirs(self, path: str, limit: int = 10000) -> list:
        """
        List all files in dir
        :param limit:
        :param path:
        :return:
        """
        return [
            item for item in self.__list_all(path, limit)
            if "chucks" not in item
        ]

    def list_images(self, path: str, limit: int = 10000) -> list:
        """
        List all images in dir
        :param limit:
        :param path:
        :return:
        """
        return [item for item in self.__list_all(path, limit) if item["FullPath"].endswith(".img")]

    def delete_file(self, file_path: str) -> None:
        """
        Remove some file
        :param file_path:
        :return:
        """
        requests.delete(
            urljoin(self.filer_node, file_path)
        ).raise_for_status()

    def read_file(self, file_path: str) -> None:
        """
        Read some file and return binary data
        :param file_path:
        :return:
        """
        response = requests.get(
            urljoin(self.filer_node, file_path)
        )
        response.raise_for_status()
        return response.content

    def delete_dir(self, path: str, recursive: bool = True, ignore_recursive_error: bool = True) -> None:
        """
        Delete a dir (can in recursive way)
        :param path:
        :param recursive:
        :param ignore_recursive_error:
        :return:
        """
        requests.delete(
            urljoin(self.filer_node, path),
            params=urlencode(dict(
                recursive=str(recursive).lower(),
                ignoreRecursiveError=str(ignore_recursive_error).lower()
            )),
        ).raise_for_status()
