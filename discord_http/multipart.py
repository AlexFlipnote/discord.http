import json

from io import BufferedIOBase
from typing import Union, Optional

from .file import File

__all__ = (
    "MultipartData",
)


class MultipartData:
    def __init__(self):
        self.boundary = "---------------discord.http"
        self.bufs: list[bytes] = []

    @property
    def content_type(self) -> str:
        """ `str`: The content type of the multipart data """
        return f"multipart/form-data; boundary={self.boundary}"

    def attach(
        self,
        name: str,
        data: Union[File, BufferedIOBase, dict, str],
        *,
        filename: Optional[str] = None,
        content_type: Optional[str] = None
    ) -> None:
        """
        Attach data to the multipart data

        Parameters
        ----------
        name: `str`
            Name of the file data
        data: `Union[File, io.BufferedIOBase, dict, str]`
            The data to attach
        filename: `Optional[str]`
            Filename to be sent on Discord
        content_type: `Optional[str]`
            The content type of the file data
            (Defaults to 'application/octet-stream' if not provided)
        """
        if not data:
            return None

        string = f"\r\n--{self.boundary}\r\nContent-Disposition: form-data; name=\"{name}\""
        if filename:
            string += f"; filename=\"{filename}\""

        match data:
            case x if isinstance(x, File):
                string += f"\r\nContent-Type: {content_type or 'application/octet-stream'}\r\n\r\n"
                data = data.data  # type: ignore

            case x if isinstance(x, BufferedIOBase):
                string += f"\r\nContent-Type: {content_type or 'application/octet-stream'}\r\n\r\n"

            case x if isinstance(x, dict):
                string += "\r\nContent-Type: application/json\r\n\r\n"
                data = json.dumps(data)

            case _:
                string += "\r\n\r\n"
                data = str(data)

        self.bufs.append(string.encode("utf8"))

        if getattr(data, "read", None):
            # Check if the data has a read method
            # If it does, it's a file-like object
            data = data.read()  # type: ignore

        if isinstance(data, str):
            # If the data is a string, encode it to bytes
            # Sometimes data.read() returns a string due to things like StringIO
            data = data.encode("utf-8")  # type: ignore

        self.bufs.append(data)  # type: ignore

        return None

    def finish(self) -> bytes:
        """ `bytes`: Return the multipart data to be sent to Discord """
        self.bufs.append(f"\r\n--{self.boundary}--\r\n".encode("utf8"))
        return b"".join(self.bufs)
