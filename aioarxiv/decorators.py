from typing import TypeVar, Type, Optional, Any
from functools import wraps
import inspect

T = TypeVar("T")  # Type variable for the decorated class
R = TypeVar("R")  # Type variable for the context manager return type


def refcount_context(cls: Type[T]) -> Type[T]:
    """
    A decorator that adds reference-counted context management to an async class.

    The decorated class must:
    1. Implement __aenter__ and __aexit__ methods
    2. Be used as an async context manager

    Args:
        cls: The class to decorate

    Returns:
        The decorated class with reference counting capabilities

    Raises:
        TypeError: If the decorated class doesn't implement required async context manager methods
    """
    # Verify the class implements the required methods
    if not inspect.iscoroutinefunction(getattr(cls, "__aenter__", None)):
        raise TypeError(f"{cls.__name__} must implement async __aenter__")
    if not inspect.iscoroutinefunction(getattr(cls, "__aexit__", None)):
        raise TypeError(f"{cls.__name__} must implement async __aexit__")

    # Store original methods
    orig_aenter = cls.__aenter__
    orig_aexit = cls.__aexit__

    # Add reference count attribute to instance state
    orig_init = cls.__init__

    @wraps(orig_init)
    def new_init(self: T, *args: Any, **kwargs: Any) -> None:
        orig_init(self, *args, **kwargs)
        # Use a private name to avoid conflicts
        object.__setattr__(self, "_refcount_context_count", 0)
        object.__setattr__(self, "_refcount_context_value", None)

    cls.__init__ = new_init

    @wraps(orig_aenter)
    async def new_aenter(self: T) -> Any:
        """
        Enhanced __aenter__ that implements reference counting.
        Only calls the original __aenter__ on first entry.
        """
        try:
            count = object.__getattribute__(self, "_refcount_context_count")
            if count == 0:
                context_value = await orig_aenter(self)
                object.__setattr__(self, "_refcount_context_value", context_value)
            object.__setattr__(self, "_refcount_context_count", count + 1)
            return object.__getattribute__(self, "_refcount_context_value")
        except Exception:
            # Reset count on error
            object.__setattr__(self, "_refcount_context_count", 0)
            object.__setattr__(self, "_refcount_context_value", None)
            raise

    @wraps(orig_aexit)
    async def new_aexit(
        self: T,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> Optional[bool]:
        """
        Enhanced __aexit__ that implements reference counting.
        Only calls the original __aexit__ when all references are released.
        """
        try:
            count = object.__getattribute__(self, "_refcount_context_count")
            if count <= 0:
                raise RuntimeError("Context manager exit called more times than enter")

            object.__setattr__(self, "_refcount_context_count", count - 1)

            if count == 1:  # Last reference
                result = await orig_aexit(self, exc_type, exc_val, exc_tb)
                object.__setattr__(self, "_refcount_context_value", None)
                return result
            return None
        except Exception as e:
            if not isinstance(e, RuntimeError):  # Don't reset on expected runtime errors
                # Reset count on unexpected error
                object.__setattr__(self, "_refcount_context_count", 0)
                object.__setattr__(self, "_refcount_context_value", None)
            raise

    # Replace the methods
    cls.__aenter__ = new_aenter
    cls.__aexit__ = new_aexit

    # Verify the class after modification
    if not isinstance(cls, type):
        raise TypeError("Decorator must be applied to a class")

    return cls
