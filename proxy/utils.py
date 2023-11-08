from pathlib import Path
from typing import List, NamedTuple, Union

from aiohttp import web


class S3Object(NamedTuple):
    name: str
    bucket: str


def extract_object_props(request: web.Request) -> S3Object:
    try:
        _, bucket, name = Path(request.url.path).parts
    except ValueError:
        return None
    return S3Object(name=name, bucket=bucket)


def make_error_response(results: List[Union[str, bool]], reason: str, status_code: int):
    """
        Return a hint if a hook threw an error.

    w   :param results: List of bools or an error message
        :param reason: general reason for failing
        :param status_code: the status code of the response
        :return: web.Response
    """
    msg = ", ".join(
        [
            f"<{name}> : {result}"
            for name, success, result in results
            if success is False
        ],
    )
    return web.Response(
        status=status_code,
        reason=f"{reason}. {msg}." if len(msg) else f"{reason}.",
    )
