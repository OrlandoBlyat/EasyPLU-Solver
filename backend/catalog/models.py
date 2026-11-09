from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    product_id: str
    plu: str
    name: str
    category: str
    image_url: str | None
    ignore: bool = False


