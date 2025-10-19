# app/services/exceptions.py

class ServiceError(Exception):
    """Clase base para errores de la capa de servicio."""

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class InvalidQuantityError(ServiceError):
    """Lanzada cuando una cantidad es inválida (e.g., <= 0)."""
    pass


class InsufficientStockError(ServiceError):
    """Lanzada cuando no hay suficiente stock para una operación."""
    pass


class InsufficientReservationError(ServiceError):
    """Lanzada cuando se intenta liberar más stock del que está reservado."""
    pass


class DomainValidationError(ServiceError):
    """Entrada de dominio inválida."""
    pass


class ResourceNotFoundError(ServiceError):
    """Recurso no encontrado."""
    pass


class ConflictError(ServiceError):
    """Conflicto de estado en la operación."""
    pass
