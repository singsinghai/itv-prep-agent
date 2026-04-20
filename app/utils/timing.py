import logging
import inspect
from functools import wraps
from time import perf_counter
from typing import Any, Callable


def timed(step_name: str | None = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        name = step_name or func.__qualname__

        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                logger = _resolve_logger(func, args)
                start = perf_counter()
                # logger.info("Step started: %s", name)
                try:
                    return await func(*args, **kwargs)
                finally:
                    elapsed = perf_counter() - start
                    logger.info("Step completed: %s (%.3fs)", name, elapsed)

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = _resolve_logger(func, args)
            start = perf_counter()
            # logger.info("Step started: %s", name)
            try:
                return func(*args, **kwargs)
            finally:
                elapsed = perf_counter() - start
                logger.info("Step completed: %s (%.3fs)", name, elapsed)

        return sync_wrapper

    return decorator


def _resolve_logger(func: Callable[..., Any], args: tuple[Any, ...]) -> logging.Logger:
    if args and hasattr(args[0], "_logger"):
        return getattr(args[0], "_logger")
    return logging.getLogger(func.__module__)
