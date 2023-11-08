import asyncio
from typing import Any, ByteString, Callable, List, Optional, Tuple, Union

from aiohttp import web
from pydantic import BaseModel


def on(event, name: Optional[str] = None, pos: Optional[int] = None):
    def _decorator(func):
        event.register_hook(func, name or func.__name__, pos)
        return func

    return _decorator


class Event(BaseModel):
    """Represents an event that will call hooks when the event is triggered."""

    hooks: List[
        Tuple[
            int,
            str,
            Callable[[web.Request, ...], Tuple[bool, Optional[Union[str, bytes]]]],
        ]
    ] = []

    blocking: bool = False

    def register_hook(
        self,
        hook: Callable[[web.Request, ...], Tuple[bool, Optional[Union[str, bytes]]]],
        name: str,
        pos: Optional[int] = None,
    ):
        """
        Register a hook for the event.

        :param hook: The hook function to be registered.
        :param pos: The position of the hook. If not provided, the hook will be
                    assigned a position based on the existing hooks.
        :param name: The name of the hook, defaults to the function-name.

        Raises
        ------
            ValueError: If `pos` is not an integer or if the same position is
                        registered twice.

        """
        if pos is not None:
            try:
                pos = int(pos)
            except ValueError as e:
                msg = "pos must be an integer"
                raise ValueError(msg) from e
            if pos in [p for p, _, _ in self.hooks]:
                msg = (
                    "Can't register pos {} twice. Make sure it is unique. Registered "
                    "hooks for event {}: {}".format(
                        pos,
                        self,
                        self.hooks,
                    )
                )
                raise ValueError(msg)

        if name in [n for _, n, _ in self.hooks]:
            msg = (
                f"Cannot register name {name} twice. Make sure hook name is unique."
                f" Registered hooks for event {self}: {self.hooks}"
            )
            raise ValueError(msg)

        # if pos is None, then int(pos) will throw the TypeError that will prompt us to
        # assign pos the next available slot.
        if pos is None:
            try:
                pos = max([p for p, _, _ in self.hooks]) + 1
            # If no hooks have been registered before the current hook will
            # be assigned slot 0
            except ValueError:
                pos = 0

        self.hooks.append((pos, name, hook))
        self.hooks = sorted(self.hooks, key=lambda x: x[0])

    async def __call__(
        self,
        request: web.Request,
        data: Optional[ByteString] = None,
        **kwargs,
    ) -> List[Tuple[str, bool, Any]]:
        """
        Call the event and trigger the registered hooks.

        Hooks registered to non-blocking events each spawn their own thread which
        allows for parallel execution of CPU-intense operations. This emphasises
        ease of implementation on the plugin side where all hooks can be defined as
        regular blocking functions. This ease of use comes at the cost of overhead
        due to threads where the event_loop execution of hooks would be more
        appropriate (e. g. those calling remote services).

        :param request (web.Request): The request parameter.
        :param data (bytes, optional): The data parameter.

        Returns
        -------
            List[Any]: A list of results from the hooks.

        """
        if not self.hooks:
            return self.hooks

        if self.blocking:
            results = []
            for _call_order_num, _name, hook in self.hooks:
                results.append((hook.__name__, *hook(request, data, **kwargs)))
            return results

        tasks = [
            asyncio.to_thread(hook, request=request, data=data)
            for _, name, hook in self.hooks
        ]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        # NOTE: An alternative implementation would take async functions for
        # for hooks and run them in the aiohttp's event_loop. The hook itself
        # could then spawn a thread where needed, thus enhancing efficiency
        # and control. This would however require more detailed on the user's
        # side in order to achieve parallelism.

        return list(
            zip(
                [name for _, name, _ in self.hooks],
                [success for success, _ in results],
                [res for _, res in results],
            ),
        )


# register operations on the data that are not safe. i. e. interpreting it with
# image processing etc.
pre_upload_unsafe = Event()

# register operations on the file before checks have been performed such as av
# scanning that can go along with encrypting the content.
pre_upload_before_check = Event()

# register callback hooks after successful upload
post_upload = Event()

post_retrieve_data = Event()
