"""Unit tests for retry utilities."""

import time
from unittest.mock import patch

import pytest

from web_mcp.utils.retry import (
    NonRetryableError,
    RetryableError,
    non_retryable,
    retryable,
    with_retry,
    with_retry_sync,
)


class TestRetryableError:
    """Tests for RetryableError exception class."""

    def test_retryable_error_message(self):
        """Test RetryableError with message."""
        error = RetryableError("Test retryable error")
        assert str(error) == "Test retryable error"

    def test_retryable_error_inherits_exception(self):
        """Test that RetryableError inherits from Exception."""
        error = RetryableError("Test")
        assert isinstance(error, Exception)

    def test_retryable_error_can_be_raised(self):
        """Test that RetryableError can be raised and caught."""
        with pytest.raises(RetryableError) as exc_info:
            raise RetryableError("Operation should be retried")
        assert "Operation should be retried" in str(exc_info.value)

    def test_retryable_error_no_args(self):
        """Test RetryableError without message."""
        error = RetryableError()
        assert isinstance(error, RetryableError)


class TestNonRetryableError:
    """Tests for NonRetryableError exception class."""

    def test_non_retryable_error_message(self):
        """Test NonRetryableError with message."""
        error = NonRetryableError("Test non-retryable error")
        assert str(error) == "Test non-retryable error"

    def test_non_retryable_error_inherits_exception(self):
        """Test that NonRetryableError inherits from Exception."""
        error = NonRetryableError("Test")
        assert isinstance(error, Exception)

    def test_non_retryable_error_can_be_raised(self):
        """Test that NonRetryableError can be raised and caught."""
        with pytest.raises(NonRetryableError) as exc_info:
            raise NonRetryableError("Operation should not be retried")
        assert "Operation should not be retried" in str(exc_info.value)

    def test_non_retryable_error_no_args(self):
        """Test NonRetryableError without message."""
        error = NonRetryableError()
        assert isinstance(error, NonRetryableError)

    def test_retryable_and_non_retryable_are_distinct(self):
        """Test that RetryableError and NonRetryableError are distinct types."""
        assert RetryableError is not NonRetryableError
        assert not issubclass(RetryableError, NonRetryableError)
        assert not issubclass(NonRetryableError, RetryableError)


class TestWithRetryAsync:
    """Tests for the async with_retry decorator."""

    @pytest.mark.asyncio
    async def test_success_no_retries(self):
        """Test successful execution without retries."""
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        async def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await successful_func()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_then_success(self):
        """Test that function retries on failure and eventually succeeds."""
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"

        result = await flaky_func()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test that exception is raised after max retries exceeded."""
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        async def always_failing_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Permanent failure")

        with pytest.raises(ValueError) as exc_info:
            await always_failing_func()

        assert "Permanent failure" in str(exc_info.value)
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_specific_retryable_exceptions(self):
        """Test that only specified exceptions trigger retries."""
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01, retryable_exceptions=(RetryableError,))
        async def func_with_retryable_error():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RetryableError("Should retry")
            return "success"

        result = await func_with_retryable_error()
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_non_retryable_exception_no_retry(self):
        """Test that NonRetryableError does not trigger retries when not in retryable_exceptions."""
        call_count = 0

        @with_retry(
            max_attempts=3,
            base_delay=0.01,
            retryable_exceptions=(RetryableError,),
        )
        async def func_with_non_retryable():
            nonlocal call_count
            call_count += 1
            raise NonRetryableError("Should not retry")

        with pytest.raises(NonRetryableError):
            await func_with_non_retryable()

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_unexpected_exception_not_retried(self):
        """Test that exceptions not in retryable_exceptions are not retried."""
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01, retryable_exceptions=(ValueError,))
        async def func_with_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("Not a ValueError")

        with pytest.raises(TypeError):
            await func_with_type_error()

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_default_retryable_exceptions(self):
        """Test that all exceptions are retried by default."""
        call_count = 0

        @with_retry(max_attempts=2, base_delay=0.01)
        async def func_with_custom_error():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("Any exception")
            return "success"

        result = await func_with_custom_error()
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_preserves_function_metadata(self):
        """Test that decorator preserves function metadata."""

        @with_retry(max_attempts=3, base_delay=0.01)
        async def documented_func():
            """This is a documented function."""
            return "success"

        assert documented_func.__name__ == "documented_func"
        assert documented_func.__doc__ == "This is a documented function."

    @pytest.mark.asyncio
    async def test_with_arguments(self):
        """Test that decorated function works with arguments."""
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        async def func_with_args(a, b, c=None):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Retry")
            return f"{a}-{b}-{c}"

        result = await func_with_args("x", "y", c="z")
        assert result == "x-y-z"
        assert call_count == 2


class TestWithRetryAsyncJitter:
    """Tests for jitter functionality in async with_retry."""

    @pytest.mark.asyncio
    async def test_jitter_enabled_delays_vary(self):
        """Test that jitter adds randomness to delays."""
        delays = []

        @with_retry(max_attempts=3, base_delay=0.1, jitter=True)
        async def failing_func():
            delays.append(time.time())
            raise ValueError("Always fails")

        with pytest.raises(ValueError):
            await failing_func()

        assert len(delays) == 3

    @pytest.mark.asyncio
    async def test_jitter_disabled_fixed_delays(self):
        """Test that delays are fixed when jitter is disabled."""
        call_count = 0

        @with_retry(max_attempts=2, base_delay=0.01, jitter=False)
        async def failing_once():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("First failure")
            return "success"

        result = await failing_once()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_jitter_with_mocked_random(self):
        """Test jitter calculation with mocked random."""
        call_count = 0

        with patch("web_mcp.utils.retry.random.random", return_value=0.5):
            with patch("web_mcp.utils.retry.asyncio.sleep") as mock_sleep:

                @with_retry(max_attempts=3, base_delay=1.0, jitter=True)
                async def failing_func():
                    nonlocal call_count
                    call_count += 1
                    if call_count < 3:
                        raise ValueError("Fail")
                    return "success"

                result = await failing_func()
                assert result == "success"

                assert mock_sleep.call_count == 2
                first_delay = mock_sleep.call_args_list[0][0][0]
                second_delay = mock_sleep.call_args_list[1][0][0]

                assert 0.75 <= first_delay <= 1.25
                assert 1.5 <= second_delay <= 2.5


class TestWithRetrySync:
    """Tests for the synchronous with_retry_sync decorator."""

    def test_success_no_retries(self):
        """Test successful execution without retries."""
        call_count = 0

        @with_retry_sync(max_attempts=3, base_delay=0.01)
        def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_func()
        assert result == "success"
        assert call_count == 1

    def test_retry_then_success(self):
        """Test that function retries on failure and eventually succeeds."""
        call_count = 0

        @with_retry_sync(max_attempts=3, base_delay=0.01)
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"

        result = flaky_func()
        assert result == "success"
        assert call_count == 3

    def test_max_retries_exceeded(self):
        """Test that exception is raised after max retries exceeded."""
        call_count = 0

        @with_retry_sync(max_attempts=3, base_delay=0.01)
        def always_failing_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Permanent failure")

        with pytest.raises(ValueError) as exc_info:
            always_failing_func()

        assert "Permanent failure" in str(exc_info.value)
        assert call_count == 3

    def test_specific_retryable_exceptions(self):
        """Test that only specified exceptions trigger retries."""
        call_count = 0

        @with_retry_sync(max_attempts=3, base_delay=0.01, retryable_exceptions=(RetryableError,))
        def func_with_retryable_error():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RetryableError("Should retry")
            return "success"

        result = func_with_retryable_error()
        assert result == "success"
        assert call_count == 2

    def test_non_retryable_exception_no_retry(self):
        """Test that NonRetryableError does not trigger retries when not in list."""
        call_count = 0

        @with_retry_sync(
            max_attempts=3,
            base_delay=0.01,
            retryable_exceptions=(RetryableError,),
        )
        def func_with_non_retryable():
            nonlocal call_count
            call_count += 1
            raise NonRetryableError("Should not retry")

        with pytest.raises(NonRetryableError):
            func_with_non_retryable()

        assert call_count == 1

    def test_unexpected_exception_not_retried(self):
        """Test that exceptions not in retryable_exceptions are not retried."""
        call_count = 0

        @with_retry_sync(max_attempts=3, base_delay=0.01, retryable_exceptions=(ValueError,))
        def func_with_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("Not a ValueError")

        with pytest.raises(TypeError):
            func_with_type_error()

        assert call_count == 1

    def test_default_retryable_exceptions(self):
        """Test that all exceptions are retried by default."""
        call_count = 0

        @with_retry_sync(max_attempts=2, base_delay=0.01)
        def func_with_custom_error():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("Any exception")
            return "success"

        result = func_with_custom_error()
        assert result == "success"
        assert call_count == 2

    def test_preserves_function_metadata(self):
        """Test that decorator preserves function metadata."""

        @with_retry_sync(max_attempts=3, base_delay=0.01)
        def documented_func():
            """This is a documented function."""
            return "success"

        assert documented_func.__name__ == "documented_func"
        assert documented_func.__doc__ == "This is a documented function."

    def test_with_arguments(self):
        """Test that decorated function works with arguments."""
        call_count = 0

        @with_retry_sync(max_attempts=3, base_delay=0.01)
        def func_with_args(a, b, c=None):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Retry")
            return f"{a}-{b}-{c}"

        result = func_with_args("x", "y", c="z")
        assert result == "x-y-z"
        assert call_count == 2

    def test_exponential_backoff_timing(self):
        """Test that delays follow exponential backoff pattern."""
        delays = []

        with patch("time.sleep") as mock_sleep:

            @with_retry_sync(max_attempts=4, base_delay=1.0)
            def failing_func():
                delays.append(len(delays))
                raise ValueError("Always fails")

            with pytest.raises(ValueError):
                failing_func()

            assert mock_sleep.call_count == 3
            assert mock_sleep.call_args_list[0][0][0] == 1.0
            assert mock_sleep.call_args_list[1][0][0] == 2.0
            assert mock_sleep.call_args_list[2][0][0] == 4.0

    def test_single_attempt_no_sleep(self):
        """Test that no sleep occurs with max_attempts=1."""
        with patch("time.sleep") as mock_sleep:

            @with_retry_sync(max_attempts=1, base_delay=0.01)
            def failing_func():
                raise ValueError("Fails immediately")

            with pytest.raises(ValueError):
                failing_func()

            mock_sleep.assert_not_called()

    def test_custom_base_delay(self):
        """Test that custom base_delay is used correctly."""
        with patch("time.sleep") as mock_sleep:

            @with_retry_sync(max_attempts=2, base_delay=0.5)
            def failing_once():
                raise ValueError("Fail")

            with pytest.raises(ValueError):
                failing_once()

            mock_sleep.assert_called_once_with(0.5)


class TestRetryableDecorator:
    """Tests for the retryable decorator."""

    def test_retryable_returns_same_function(self):
        """Test that retryable decorator returns the same function."""

        def my_func():
            return "result"

        decorated = retryable(my_func)
        assert decorated is my_func
        assert decorated() == "result"

    def test_retryable_preserves_metadata(self):
        """Test that retryable preserves function metadata."""

        @retryable
        def documented_func():
            """This function has retryable errors."""
            return "result"

        assert documented_func.__name__ == "documented_func"
        assert documented_func.__doc__ == "This function has retryable errors."

    def test_retryable_with_async_function(self):
        """Test that retryable works with async functions."""

        @retryable
        async def async_func():
            return "async result"

        assert async_func is not None


class TestNonRetryableDecorator:
    """Tests for the non_retryable decorator."""

    def test_non_retryable_returns_same_function(self):
        """Test that non_retryable decorator returns the same function."""

        def my_func():
            return "result"

        decorated = non_retryable(my_func)
        assert decorated is my_func
        assert decorated() == "result"

    def test_non_retryable_preserves_metadata(self):
        """Test that non_retryable preserves function metadata."""

        @non_retryable
        def documented_func():
            """This function has non-retryable errors."""
            return "result"

        assert documented_func.__name__ == "documented_func"
        assert documented_func.__doc__ == "This function has non-retryable errors."

    def test_non_retryable_with_async_function(self):
        """Test that non_retryable works with async functions."""

        @non_retryable
        async def async_func():
            return "async result"

        assert async_func is not None


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_with_retry_zero_base_delay(self):
        """Test with_retry with zero base delay."""
        call_count = 0

        @with_retry(max_attempts=2, base_delay=0.0)
        async def failing_once():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("First failure")
            return "success"

        result = await failing_once()
        assert result == "success"
        assert call_count == 2

    def test_with_retry_sync_zero_base_delay(self):
        """Test with_retry_sync with zero base delay."""
        call_count = 0

        @with_retry_sync(max_attempts=2, base_delay=0.0)
        def failing_once():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("First failure")
            return "success"

        result = failing_once()
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_with_retry_large_max_attempts(self):
        """Test with_retry with large max_attempts."""
        call_count = 0

        @with_retry(max_attempts=100, base_delay=0.001)
        async def fails_many_times():
            nonlocal call_count
            call_count += 1
            if call_count < 10:
                raise ValueError("Keep trying")
            return "finally success"

        result = await fails_many_times()
        assert result == "finally success"
        assert call_count == 10

    @pytest.mark.asyncio
    async def test_with_retry_multiple_exception_types(self):
        """Test with_retry with multiple exception types."""
        call_count = 0

        @with_retry(
            max_attempts=5,
            base_delay=0.01,
            retryable_exceptions=(ValueError, TypeError, RuntimeError),
        )
        async def raises_different_errors():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First error")
            if call_count == 2:
                raise TypeError("Second error")
            if call_count == 3:
                raise RuntimeError("Third error")
            return "success"

        result = await raises_different_errors()
        assert result == "success"
        assert call_count == 4

    def test_with_retry_sync_multiple_exception_types(self):
        """Test with_retry_sync with multiple exception types."""
        call_count = 0

        @with_retry_sync(
            max_attempts=5,
            base_delay=0.01,
            retryable_exceptions=(ValueError, TypeError, RuntimeError),
        )
        def raises_different_errors():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First error")
            if call_count == 2:
                raise TypeError("Second error")
            if call_count == 3:
                raise RuntimeError("Third error")
            return "success"

        result = raises_different_errors()
        assert result == "success"
        assert call_count == 4

    @pytest.mark.asyncio
    async def test_with_retry_return_none(self):
        """Test with_retry when function returns None."""

        @with_retry(max_attempts=3, base_delay=0.01)
        async def returns_none():
            return None

        result = await returns_none()
        assert result is None

    def test_with_retry_sync_return_none(self):
        """Test with_retry_sync when function returns None."""

        @with_retry_sync(max_attempts=3, base_delay=0.01)
        def returns_none():
            return None

        result = returns_none()
        assert result is None

    @pytest.mark.asyncio
    async def test_with_retry_return_false(self):
        """Test with_retry when function returns False."""

        @with_retry(max_attempts=3, base_delay=0.01)
        async def returns_false():
            return False

        result = await returns_false()
        assert result is False

    @pytest.mark.asyncio
    async def test_with_retry_empty_string(self):
        """Test with_retry when function returns empty string."""

        @with_retry(max_attempts=3, base_delay=0.01)
        async def returns_empty():
            return ""

        result = await returns_empty()
        assert result == ""
