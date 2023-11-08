import logging
from typing import Final, NoReturn

from aiohttp import ClientSession, web

log: Final = logging.getLogger("aiohttp.server")

# This file is created since make_app is not reusable if it's
# imported from the same module where web.run_app() is called.
# The test will fail with complaining that the port is already
# in use.


async def client_session_ctx(app) -> NoReturn:
    app["client_session"] = ClientSession()
    yield
    await app["client_session"].close()


async def create_app() -> web.Application:
    # load registered hooks
    from proxy import hooks  # noqa: F401
    from proxy.handlers import routes  # avoid circular import

    app = web.Application()
    app.add_routes(routes)

    app.cleanup_ctx.append(client_session_ctx)

    return app


if __name__ == "__main__":  # pragma: no cover
    web.run_app(create_app(), port=8000)
