"""Payment provider integrations."""

class PaymentProviderError(Exception):
    """Base error for payment providers."""


class PaymentProviderConfigurationError(PaymentProviderError):
    """Raised when provider configuration is invalid or missing."""

