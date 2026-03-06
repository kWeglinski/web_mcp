"""Retry utilities with exponential backoff."""

import asyncio
import random
from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

T = TypeVar("T")
P = ParamSpec("P")


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    retryable_exceptions: tuple = (Exception,),
    jitter: bool = False,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator to add retry logic with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay in seconds for exponential backoff
        retryable_exceptions: Tuple of exception types to catch and retry
        jitter: Whether to add random jitter (±25%) to delay

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_error = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_error = e
                    if attempt < max_attempts - 1:
                        # Exponential backoff: base_delay * 2^attempt
                        delay = base_delay * (2**attempt)
                        if jitter:
                            # Add ±25% randomization to prevent thundering herd
                            delay = delay * (0.75 + random.random() * 0.5)
                        await asyncio.sleep(delay)
            raise last_error

        return wrapper

    return decorator


def with_retry_sync(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    retryable_exceptions: tuple = (Exception,),
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Synchronous version of with_retry decorator.

    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay in seconds for exponential backoff
        retryable_exceptions: Tuple of exception types to catch and retry

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_error = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_error = e
                    if attempt < max_attempts - 1:
                        delay = base_delay * (2**attempt)
                        import time

                        time.sleep(delay)
            raise last_error

        return wrapper

    return decorator


class RetryableError(Exception):
    """Exception that indicates the operation can be retried."""

    pass


class NonRetryableError(Exception):
    """Exception that indicates the operation should not be retried."""

    pass


def retryable[**P, T](func: Callable[P, T]) -> Callable[P, T]:
    """Decorator to mark a function as having retryable errors."""
    return func


def non_retryable[**P, T](func: Callable[P, T]) -> Callable[P, T]:
    """Decorator to mark a function as having non-retryable errors."""
    return func
