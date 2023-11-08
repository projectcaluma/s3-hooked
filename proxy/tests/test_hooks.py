import pytest
from aiohttp.test_utils import make_mocked_request

from proxy.ciphers import decrypt
from proxy.events import (
    Event,
    on,
    pre_upload_before_check,
)


@pytest.mark.parametrize("blocking", [True, False])
async def test_events(s3_file_upload_url, sample_binary, blocking):
    test_event = Event(blocking=blocking)

    @on(test_event, pos=1)
    def some_action(request, data=None):
        return True, "some_action"

    @on(test_event, pos=3)
    def some_third_action(request, data=None):
        return True, "some_third_action"

    @on(test_event, pos=2)
    def some_second_action(request, data=None):
        return True, "some_second_action"

    request = make_mocked_request(
        "PUT",
        "/bucket/some-id-before_Sample_file.pdf",
        payload=sample_binary,
        headers={"Content-Type": "application/pdf"},
    )

    result = await test_event(request, sample_binary)
    assert [r[0] for r in result] == [
        "some_action",
        "some_second_action",
        "some_third_action",
    ]


@pytest.mark.parametrize(
    "pos,expected,raised_from_task",
    [
        ("A", ValueError, False),
        (0, ValueError, False),
        (0, "Hook caused an error.", True),
        (None, ValueError, False),
    ],
)
async def test_events_exceptions(
    s3_file_upload_url,
    sample_binary,
    pos,
    expected,
    raised_from_task,
):
    test_event = Event()
    request = make_mocked_request(
        "PUT",
        str(s3_file_upload_url),
        headers={"Content-Type": "application/pdf"},
    )

    def raise_error():
        raise ValueError(expected)

    @on(test_event)
    def some_action_hook(request, data=None):
        try:
            raise_error()
        except ValueError as e:
            return False, str(e)

    if raised_from_task:

        @on(test_event)
        def run_parallel(request, data=None):
            return True, "This task was not cancelled."

        result = await test_event(request, sample_binary)
        assert expected in [res[2] for res in result if res[0] == "some_action_hook"]

    else:
        with pytest.raises(expected):
            if pos is None:
                # register same hook twice
                test_event.register_hook(
                    lambda request, data=None: None,
                    name="some_action_hook",
                )
            # register on same pos twice
            test_event.register_hook(
                lambda request, data=None: None,
                name="some_action",
                pos=pos,
            )


@pytest.mark.usefixtures("_load_default_hooks")
async def test_default_hooks(settings, s3_file_upload_url, sample_binary):
    request = make_mocked_request(
        settings.request_methods.put,
        str(s3_file_upload_url),
    )
    result = await pre_upload_before_check(request, sample_binary)
    assert decrypt(request.url.name, result[0][2]) == sample_binary
