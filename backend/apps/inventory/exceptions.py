"""
Exceptions for the inventory domain.
"""


class InventoryException(Exception):
    """Base exception for inventory domain errors."""
    pass


class StockRecordNotFoundError(InventoryException):
    """Raised when an operation targets a variant with no associated StockRecord."""
    pass


class InsufficientStockError(InventoryException):
    """Raised when an operation requests more stock than is available."""
    pass


class InvalidReservationError(InventoryException):
    """Raised when reservation or release parameters violate stock rules."""
    pass


class InvalidStockAdjustmentError(InventoryException):
    """Raised when an inventory adjustment payload or target state is invalid."""
    pass

