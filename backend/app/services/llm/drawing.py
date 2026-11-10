"""The drawing a tool made, fetched for the canvas (ADR 0045).

A drawing tool answers over MCP with a receipt: counts, legend and quality,
but no node or link rows, which the model never reads and which outgrow the
MCP transport on a large network. The rows travel over REST instead, and the
receipt's own keys are laid over them so that what is not saved with the
network (a one-shot `viewport`, an `encoding_note`) still reaches the canvas.
"""

from typing import Any, Dict, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

# Receipt keys that describe the rows rather than belong to the drawing.
_RECEIPT_ONLY = ("rendered", "node_count", "link_count")


def is_receipt(result: Any) -> bool:
    """True for a drawing tool's result: it drew `network_id` and says so."""
    return (
        isinstance(result, dict)
        and result.get("rendered") is True
        and isinstance(result.get("network_id"), int)
        and "nodes" not in result
    )


def is_drawing(result: Any) -> bool:
    """True for a full payload the canvas can draw as it is."""
    return isinstance(result, dict) and "nodes" in result and "links" in result


async def fetch(network_id: int, with_quality: bool = True) -> Dict[str, Any]:
    """The network as drawn from its saved style. Raises on failure."""
    from app.services import network_service

    return await network_service.build_visualization(
        network_id, with_quality=with_quality
    )


async def from_receipt(receipt: Dict[str, Any]) -> Dict[str, Any]:
    """The full drawing a receipt stands for. Raises on failure."""
    # The receipt already carries layout_quality when the drawing has one.
    drawing = await fetch(receipt["network_id"], with_quality=False)
    drawing.update((k, v) for k, v in receipt.items() if k not in _RECEIPT_ONLY)
    return drawing


async def resolve(result: Any) -> Optional[Dict[str, Any]]:
    """The drawing in a tool result: fetched for a receipt, None when there is none.

    A full payload is still accepted as it is, for the deprecated tools that
    return one and for conversations replayed against an older service.
    """
    if is_drawing(result):
        return result
    if is_receipt(result):
        return await from_receipt(result)
    return None
