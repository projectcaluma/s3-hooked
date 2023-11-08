import logging
from typing import Final, Optional

import aiohttp
from aiohttp import web
from yarl import URL

from proxy.conf import settings
from proxy.events import (
    post_retrieve_data,
    post_upload,
    pre_upload_before_check,
    pre_upload_unsafe,
)
from proxy.utils import extract_object_props, make_error_response

log = logging.getLogger("aiohttp.server")


routes: Final = web.RouteTableDef()


def to_response(client_resp: aiohttp.ClientResponse, content=None) -> web.Response:
    """Create a server response from the client response."""

    interesting_headers = [
        "Cookie",
        "Host",
        "Referer",
        "User-Agent",
        "Accept",
        "Accept-Language",
    ]

    headers = {
        k: client_resp.headers[k]
        for k in interesting_headers
        if k in client_resp.headers
    }
    if content:
        headers["Content-Length"] = str(len(content))

    return web.Response(
        body=content,
        status=client_resp.status,
        headers=headers,
        reason=client_resp.reason,
    )


async def proxy_pass(
    request: web.Request,
    data: Optional[bytes] = None,
) -> web.Response:
    """
    Make a proxied HTTP request to a s3 object storage service.

    :param request (web.Request): The aiohttp request object representing the HTTP
                                  request to be proxied.
    :param data (optional): The data to be sent in the request body. It is used for
                            PUT requests.

    Returns
    -------
        web.Response: The response object representing the result of the proxied HTTP
                      request.
    """
    upstream_host = URL.build(
        scheme="https" if settings.OBJECT_STORE_SSL_ENABLED else "http",
        host=settings.OBJECT_STORE_HOST,
        port=settings.OBJECT_STORE_PORT,
    )

    headers = request.headers.copy()
    if data:
        headers["Content-Length"] = str(len(data))
    make_request = getattr(request.app["client_session"], request.method.lower())
    async with make_request(
        str(upstream_host.joinpath(request.path.lstrip("/"))),
        headers=headers,
        data=data,
        params=request.query,
        # proxy=upstream_host,
    ) as resp:
        resp.raise_for_status()
        content = await resp.read()
        log.debug(
            "Proxy passing request {request} to {upstream_host}. Result: {resp}",
            extra={
                "request": request,
                "upstream_host": upstream_host,
                "resp": resp,
            },
        )
        return to_response(resp, content=content)


async def handle_get(request: web.Request) -> web.Response:
    response = await proxy_pass(request)
    s3obj = extract_object_props(request)
    content = response.body
    if content and s3obj is not None:
        log.debug("Decrypting {s3obj} ..", extra={"s3obj": s3obj})
        results = await post_retrieve_data(request, content)
        if not all(res[1] for res in results):
            return make_error_response(
                results,
                "Retrieval of {s3obj} failed.",
                status_code=400,
            )
        decrypted = next(filter(lambda x: x[0] == "hook_decrypt_data", results), None)
        if decrypted:
            content = decrypted[2]
    return to_response(response, content=content)


async def handle_put(request: web.Request) -> web.Response:
    """
    Handle upload of a file.

    The `handle_put` function handles the upload of a file. It extracts the bucket and
    object name from the request, reads the content of the file, and performs
    pre-upload hooks to check if the upload is allowed. If the pre-upload hooks pass,
    it performs additional checks on the file's content. If all checks pass, it
    encrypts the file and uploads it to the object storage. Finally, it triggers
    post-upload hooks if the upload is successful.

    :param request: The aiohttp request object representing the upload request.
    :type request: web.Request
    :return: The aiohttp response object representing the result of the upload.
    :rtype: web.Response
    """
    s3obj = extract_object_props(request)
    log.debug(
        "Request received to upload and encrypt {s3obj_name}",
        extra={"s3obj_name": s3obj},
    )
    if s3obj is None:
        # for uploading an object both bucket and object name are required.
        return web.Response(
            status=400,
            reason="Failed to get bucket and object-id from upload request.",
        )

    content = await request.content.read()
    log.debug(
        "Hooks to be called by pre_upload_before_check: {hooks}.",
        extra={"hooks": pre_upload_before_check},
    )
    results = await pre_upload_before_check(request, content)
    if not all(res[1] for res in results):
        return make_error_response(
            results,
            "Pre-upload hook failed",
            status_code=400,
        )
    encrypted = content
    encrypted_result = next(
        filter(lambda x: x[0] == "hook_encrypt_data", results),
        None,
    )
    if encrypted_result:
        encrypted = encrypted_result[2]

    # perform additional checks after pre-upload hook that are not considered safe
    # before checks above
    log.debug("Hooks pre_upload_unsafe: {hooks}", extra={"hooks": pre_upload_unsafe})
    check_results = await pre_upload_unsafe(request, data=content)

    if not all(res[1] for res in check_results):
        return make_error_response(
            results,
            "Upload failed sanity checks.",
            status_code=400,
        )

    response = await proxy_pass(request, data=encrypted)

    if response.status < 400:
        await post_upload(request)
    return response


@routes.view(r"/{tail:.*}")
async def handle(request: web.Request) -> web.Response:
    if request.method not in ["GET", "PUT"]:
        try:
            return await proxy_pass(request)
        except aiohttp.client.ClientError as e:
            make_error_response(
                [
                    (
                        str(request),
                        False,
                        f"Failed to pass request {request} to upstream.",
                    ),
                ],
                reason=e,
                status_code=400,
            )

    if request.method == "GET":
        return await handle_get(request)

    if request.method == "PUT":
        return await handle_put(request)

    return web.Response(reason="Method not allowed.", status=405)
