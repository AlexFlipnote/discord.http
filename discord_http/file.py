import io

from pathlib import Path

__all__ = (
    "File",
)


class File:
    """
    Represents a file to be uploaded to Discord.

    Attributes
    ----------
    data: io.BufferedIOBase
        The file data as a file-like object.
    spoiler: bool
        Whether the file is a spoiler.
    title: str | None
        The title of the file, if any.
    description: str | None
        The description of the file, if any.
    duration_secs: float | int | None
        The duration of the file in seconds, if applicable.
    waveform: str | None
        The waveform data for the file, if applicable.
    """

    __slots__ = (
        "_filename",
        "_finalizer",
        "_original_pos",
        "_owner",
        "data",
        "description",
        "duration_secs",
        "spoiler",
        "title",
        "waveform",
    )

    def __init__(
        self,
        data: io.BufferedIOBase | str,
        filename: str | None = None,
        *,
        spoiler: bool = False,
        title: str | None = None,
        description: str | None = None,
        duration_secs: float | int | None = None,
        waveform: str | None = None
    ):
        self.spoiler = spoiler
        self.title = title
        self.description = description
        self.duration_secs = duration_secs
        self.waveform = waveform
        self._filename = filename

        if isinstance(data, (str, Path)):
            self._filename = filename or Path(data).name
            self.data = open(data, "rb")  # noqa: SIM115
            self._owner = True
            self._original_pos = 0
        elif isinstance(data, io.IOBase):
            if not (data.seekable() and data.readable()):
                raise ValueError(f"File buffer {data!r} must be seekable and readable")
            if not filename:
                raise ValueError("Filename must be specified when passing a file buffer")

            self._filename = filename
            self.data = data
            self._owner = False
            self._original_pos = data.tell()
        else:
            raise TypeError(f"Expected str, Path, or IO object, got {type(data).__name__}")

    def __str__(self) -> str:
        return self.filename

    def __repr__(self) -> str:
        return f"<File filename={self.filename!r} spoiler={self.spoiler}>"

    def __enter__(self) -> "File":
        return self

    def __exit__(self, *args) -> None:  # noqa: ANN002
        self.close()

    def __del__(self) -> None:
        self.close()

    @property
    def filename(self) -> str:
        """ The filename of the file. """
        return f"{'SPOILER_' if self.spoiler else ''}{self._filename}"

    def reset(self, *, seek: int | bool = True) -> None:
        """ Reset the file buffer to the original position. """
        if seek:
            self.data.seek(self._original_pos)

    def close(self) -> None:
        """ Close the file buffer. """
        if self._owner:
            self.data.close()

    def to_dict(self, index: int) -> dict:
        """
        The file as a dictionary.

        Parameters
        ----------
        index:
            The index of the file

        Returns
        -------
            The file as a dictionary
        """
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
