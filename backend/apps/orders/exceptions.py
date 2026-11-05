"""Order domain exceptions.

All of these are business-rule failures surfaced to the storefront as HTTP 400
responses; they never indicate a server fault.
"""


class OrderError(Exception):
    """Base class for order placement failures."""


class EmptyCartError(OrderError):
    """Raised when checkout is attempted with no cart or no items."""


class OrderValidationError(OrderError):
    """Raised when submitted customer/shipping data fails a business rule."""


class UnavailableItemError(OrderError):
    """Raised when a cart line can no longer be purchased (stock/catalog)."""
