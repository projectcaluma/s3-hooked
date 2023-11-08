import pathlib
import re
from typing import NamedTuple

import pytest
from aioresponses import aioresponses
from requests.status_codes import codes as http_codes
from yarl import URL

from proxy.app import create_app
from proxy.ciphers import encrypt
from proxy.conf import settings as conf_settings
from proxy.events import post_upload, pre_upload_before_check


@pytest.fixture
def sample_binary():
    return b"You can read binary?"


@pytest.fixture
def sample_token(sample_binary, s3_file_upload_url):
    return encrypt(s3_file_upload_url.name, sample_binary)


@pytest.fixture
def s3_file_upload_url():
    file_name = "Sample_file"
    return pathlib.Path("bucket") / f"some-id-before_{file_name}.pdf"


@pytest.fixture
def cli(aiohttp_server, aiohttp_client, unused_tcp_port_factory, loop):
    port = unused_tcp_port_factory()
    app = loop.run_until_complete(create_app())
    server = loop.run_until_complete(aiohttp_server(app, port=port))
    return loop.run_until_complete(aiohttp_client(server))


@pytest.fixture(params=[None])
def settings(request):
    """
    Override default settings for this test.

    Parametrize the fixture by setting `indirect=True` and passing in a dictionary of
    the settings to override.
    """

    if request.param is not None:
        for variable, value in request.param.items():
            setattr(conf_settings, variable, value)
    return conf_settings


@pytest.fixture
def _flush_hooks():
    pre_upload_before_check.hooks = []
    pre_upload_before_check.hooks = []
    post_upload.hooks = []


class MockRequest(NamedTuple):
    method: str = "get"
    pattern: str = ".*$"
    status_code: int = http_codes.OK
    content_type: str = "text/plain"


@pytest.fixture(params=[MockRequest()])
def mock_store_request(request):
    return request.param


@pytest.fixture
def mock_store(s3host_url, s3_file_upload_url, mock_store_request):
    with aioresponses(passthrough=["http://127.0.0.1"]) as m:
        pattern = re.compile(rf"^{s3host_url}/{mock_store_request.pattern}")
        getattr(m, mock_store_request.method.lower())(
            pattern,
            status=mock_store_request.status_code,
        )
        yield m


@pytest.fixture
def s3host_url():
    return URL.build(
        scheme="http",
        host=conf_settings.OBJECT_STORE_HOST,
        port=conf_settings.OBJECT_STORE_PORT,
    )


@pytest.fixture
def _load_default_hooks():
    from proxy import default_hooks  # noqa: F401 ignore unused import
