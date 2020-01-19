from abc import ABC, abstractmethod
from io import BytesIO
import random
from typing import BinaryIO
from urllib.parse import urljoin

import requests


class AbstractFileSystem(ABC):
    def read(self, fid: str) -> bytes:
        """
        Get a file by fid
        :param fid: File ID
        :return:
        """
        with BytesIO() as fp:
            self.download(fid, fp)
            fp.seek(0)
            return fp.read()

    @abstractmethod
    def download(self, fid: str, fp: BinaryIO, chunk_size: int = 81920):
        """
        Write file's data to fp
        :param chunk_size: chunk_size while downloading as a reference
        :param fp: File like object to write data
        :param fid: File ID
        :return:
        """
        pass

    def write(self, content: bytes) -> str:
        """
        Save a file and return file ID
        :param content: file content
        :return:
        """
        with BytesIO(content) as fp:
            return self.upload(fp)

    @abstractmethod
    def upload(self, fp: BinaryIO) -> str:
        """
        Save a file and return file ID
        :param fp: file pointer (basically any BinaryIO can read data)
        :return:
        """
        pass

    @abstractmethod
    def delete(self, fid: str):
        """
        Remove a file from FS via using FID
        :param fid:
        :return:
        """
        pass


class WeedFileSystem(AbstractFileSystem):
    def __init__(self, master_address: str):
        """
        Weed FS interface
        :param master_address: For example http://127.0.0.1:9333/
        """
        self._master_address = master_address

    def download(self, fid: str, fp: BinaryIO, chunk_size: int = 81920):
        with requests.get(
                random.choice(self._get_file_urls(fid)),
                stream=True
        ) as resp:
            resp.raise_for_status()
            chucks = (c for c in resp.iter_content(chunk_size=chunk_size) if c)
            for chunk in chucks:
                fp.write(chunk)

    def upload(self, fp: BinaryIO) -> str:
        assigned_info = self._assign_fid()
        url = "http://{}/".format(assigned_info["url"])
        fid = assigned_info["fid"]
        self._save_file(url, fid, fp)
        return fid

    def delete(self, fid: str):
        requests.delete(
            random.choice(self._get_file_urls(fid))
        ).raise_for_status()

    def _get_file_urls(self, fid: str) -> list:
        return [
            urljoin("http://{}/".format(location["url"]), fid)
            for location in self._query_locations(fid)["locations"]
        ]

    def _assign_fid(self):
        resp = requests.get(urljoin(self._master_address, "/dir/assign"))
        resp.raise_for_status()
        return resp.json()

    def _query_locations(self, fid: str) -> dict:
        resp = requests.get(urljoin(self._master_address, "/dir/lookup"), params={"volumeId": fid})
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _save_file(url: str, fid: str, fp: BinaryIO):
        resp = requests.post(urljoin(url, fid), files={"file": fp})
        resp.raise_for_status()
        return resp.json()
