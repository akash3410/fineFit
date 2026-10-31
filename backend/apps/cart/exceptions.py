"""
Cart domain exceptions.

Cart operations raise these typed errors from the service layer; views map
them onto appropriate HTTP responses. They are deliberately separate from
``apps.inventory`` exceptions so the cart domain owns its own failure
vocabulary and never mutates inventory.
"""


class CartException(Exception):
    """Base class for all cart domain errors."""


class CartNotFoundError(CartException):
    """Raised when the referenced cart cannot be found."""


class CartItemNotFoundError(CartException):
    """Raised when a cart item is not found within the expected cart."""


class CartValidationError(CartException):
    """Raised when requested cart operation violates a business rule."""
