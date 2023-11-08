import asyncio
import re

import aiohttp
import pytest
from aiohttp import web
from aioresponses import aioresponses
from pytest_lazyfixture import lazy_fixture
from requests.status_codes import codes as http_codes

from proxy.conf import settings
from proxy.conftest import MockRequest
from proxy.events import post_upload, pre_upload_before_check, pre_upload_unsafe

match_bucket_key_params = r"(?P<bucket>[^/]+)/(?P<key>[^/\?]+)/?\??(?P<params>(.*)?)$"
match_bucket_only = r"(?P<bucket>[^/\?]+)/?\??(?P<params>(.*)?)$"
match_host_root_only = r"([^/\?]*)\??(?P<params>(.*)?)$"


@pytest.mark.usefixtures("_flush_hooks", "mock_store_request")
@pytest.mark.parametrize(
    "mock_store_request,request_url,request_method,expected_status",
    [
        (
            MockRequest(
                method=settings.request_methods.put,
                pattern=match_bucket_key_params,  # r"(?P<bucket>[^/]+)/(?P<key>[^/\?]+)\??(?P<params>(.*)?)$",
                status_code=http_codes[r"\o/"],
            ),
            lazy_fixture("s3_file_upload_url"),
            settings.request_methods.put,
            http_codes.ok,
        ),
        (
            MockRequest(
                method=settings.request_methods.put,
                pattern=match_bucket_only,
                status_code=http_codes.bad_request,
            ),
            "bucket",
            settings.request_methods.put,
            http_codes.bad_request,
        ),
        (
            MockRequest(method=settings.request_methods.put),
            "",
            settings.request_methods.put,
            http_codes.bad_request,
        ),
        (
            MockRequest(method=settings.request_methods.options),
            "",
            settings.request_methods.options,
            http_codes.ok,
        ),
    ],
    indirect=["mock_store_request"],
)
async def test_upload(
    request,
    cli,
    sample_binary,
    sample_token,
    mock_store,
    mocker,
    s3host_url,
    request_url,
    request_method,
    settings,
    expected_status,
):
    headers = {"Content-Type": "text/plain", "X-Foo": "bar"}
    params = {"X-param-1": "param-1", "X-param-2": "param-2"}
    cli_request = getattr(cli, request_method.lower())
    resp = await cli_request(
        str(request_url),
        params=params,
        headers=headers,
        data=sample_binary,
    )
    assert resp.status == expected_status

    if expected_status < http_codes.bad_request:
        mock_store.assert_called_once()
        match_url = s3host_url.joinpath(str(request_url)).with_query(params)
        req_args, req_kwargs = mock_store.requests.get(
            (request_method.upper(), match_url),
        )[0]

        # ensure the object store host was queried with all the request properties
        # the proxy has received.
        for header, value in headers.items():
            assert req_kwargs["headers"].get(header) == value

        for param, value in params.items():
            assert req_kwargs["params"].get(param) == value

        if request_method == settings.request_methods.put:
            assert req_kwargs["data"] == sample_binary


def test_regexp_example(settings, s3host_url, s3_file_upload_url):
    loop = asyncio.get_event_loop()
    session = aiohttp.ClientSession()

    pattern = re.compile(rf"^{s3host_url}/.*$")
    with aioresponses() as m:
        m.put(pattern, status=http_codes.ok)

        resp = loop.run_until_complete(
            session.put(
                f"{s3host_url}/{s3_file_upload_url}?param-1=bla",
            ),
        )

        assert resp.status == http_codes.ok


@pytest.mark.usefixtures("_flush_hooks")
@pytest.mark.parametrize(
    "mocked_event, name, success, value, expected_response_status",
    [
        (
            pre_upload_before_check,
            "hook_encrypt_data",
            False,
            b"nom nom",
            http_codes.bad_request,
        ),
        (
            pre_upload_before_check,
            "hook_encrypt_data",
            True,
            b"decrypted",
            http_codes.ok,
        ),
        (pre_upload_unsafe, "check_check", False, None, http_codes.bad_request),
        (post_upload, "check_check", False, None, http_codes.ok),
    ],
)
async def test_upload_hook_result_handling(
    cli,
    mocker,
    s3_file_upload_url,
    sample_binary,
    mocked_event,
    name,
    success,
    value,
    expected_response_status,
):
    mocked_event.register_hook(lambda request, data: (success, value), name=name)

    mocker.patch(
        "proxy.handlers.proxy_pass",
        return_value=web.Response(status=http_codes.ok),
    )
    resp = await cli.put(
        str(s3_file_upload_url),
        params={"X-param-1": "param-1"},
        headers={"Content-Type": "text/plain"},
        data=sample_binary,
    )
    assert resp.status == expected_response_status

    mocked_event.hooks = []


@pytest.mark.usefixtures("_load_default_hooks")
@pytest.mark.parametrize(
    "fetch_url,encrypted_data,decrypted_data,expected_status",
    [
        (
            lazy_fixture("s3_file_upload_url"),
            lazy_fixture("sample_token"),
            lazy_fixture("sample_binary"),
            http_codes.ok,
        ),
        (
            lazy_fixture("s3_file_upload_url"),
            b"something else",
            b"",
            http_codes.bad_request,
        ),
        ("/bucket", None, b"", http_codes.ok),
        ("/", None, b"", http_codes.ok),
        ("", None, b"", http_codes.ok),
    ],
)
async def test_fetch(
    cli,
    fetch_url,
    encrypted_data,
    decrypted_data,
    expected_status,
    mocker,
):
    mocker.patch(
        "proxy.handlers.proxy_pass",
        return_value=web.Response(status=http_codes.ok, body=encrypted_data),
    )
    resp = await cli.get(str(fetch_url))
    assert resp.status == expected_status
    assert await resp.read() == decrypted_data


@pytest.mark.parametrize(
    "settings",
    [{"ALLOWED_METHODS": ["GET", "PUT"]}],
    indirect=True,
)
async def test_settings(settings, cli):
    resp = await cli.post("/")
    assert resp.status == 405
