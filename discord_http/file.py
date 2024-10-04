import io

from typing import Union, Optional

__all__ = (
    "File",
)


class File:
    def __init__(
        self,
        data: Union[io.BufferedIOBase, str],
        *,
        filename: Optional[str] = None,
        spoiler: bool = False,
        title: Optional[str] = None,
        description: Optional[str] = None,
        duration_secs: Optional[int] = None,
        waveform: Optional[str] = None
    ):
        self.spoiler = spoiler
        self.title = title
        self.description = description
        self.duration_secs = duration_secs
        self.waveform = waveform
        self._filename = filename

        if isinstance(data, io.IOBase):
            if not (data.seekable() and data.readable()):
                raise ValueError(f"File buffer {data!r} must be seekable and readable")
            if not filename:
                raise ValueError("Filename must be specified when passing a file buffer")

            self.data: io.BufferedIOBase = data
            self._original_pos = data.tell()
            self._owner = False
        else:
            if not self._filename:
                self._filename = data
            self.data = open(data, "rb")
            self._original_pos = 0
            self._owner = True

        self._closer = self.data.close
        self.data.close = lambda: None

    def __str__(self) -> str:
        return self.filename

    def __repr__(self) -> str:
        return f"<File filename='{self.filename}'>"

    @property
    def filename(self) -> str:
        """ `str`: The filename of the file """
        return f"{'SPOILER_' if self.spoiler else ''}{self._filename}"

    def reset(self, *, seek: Union[int, bool] = True) -> None:
        """ Reset the file buffer to the original position """
        if seek:
            self.data.seek(self._original_pos)

    def close(self) -> None:
        """ Close the file buffer """
        self.data.close = self._closer
        if self._owner:
            self.data.close()

    def to_dict(self, index: int) -> dict:
        """ `dict`: The file as a dictionary """
        payload = {
            "id": index,
            "filename": self.filename
        }

        if self.title:
            payload["title"] = self.title
        if self.description:
            payload["description"] = self.description
        if self.duration_secs:
            payload["duration_secs"] = self.duration_secs
        if self.waveform:
            payload["waveform"] = self.waveform

        return payload
