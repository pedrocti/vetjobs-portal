from decimal import Decimal
from typing import Tuple, Dict, Any, Optional


def normalize_amount(value: Any) -> int:
    """
    Converts any incoming amount safely into integer (gateway-safe).
    Prevents float bugs and type mismatch errors.
    """
    try:
        if value is None:
            return 0

        amount = Decimal(str(value))
        return int(amount)
    except Exception:
        return 0


def safe_gateway_response(response: Dict[str, Any]) -> Optional[str]:
    """
    Extracts payment redirect URL safely from multiple gateways.
    """
    if not isinstance(response, dict):
        return None

    return (
        response.get("authorization_url")
        or response.get("link")
        or response.get("data", {}).get("authorization_url")
    )


def safe_gateway_reference(response: Dict[str, Any]) -> Optional[str]:
    """
    Extracts gateway reference safely across Paystack/Flutterwave.
    """
    if not isinstance(response, dict):
        return None

    return (
        response.get("reference")
        or response.get("tx_ref")
        or response.get("id")
    )