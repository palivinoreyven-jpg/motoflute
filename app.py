from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class Fitment:
    make: str       # e.g., "Honda"
    model: str      # e.g., "Click 125i"
    years: str      # e.g., "2018-2026"

@dataclass
class MotorPart:
    item_id: int
    name: str
    description: str
    category: str
    subcategory: str
    price: float
    stock_quantity: int
    # Stores list of compatible motorcycles
    fitment_compatibility: List[Fitment] = field(default_factory=list)

    def is_compatible(self, make: str, model: str) -> bool:
        """Checks if this part fits a specific bike make and model."""
        for bike in self.fitment_compatibility:
            if bike.make.lower() == make.lower() and bike.model.lower() == model.lower():
                return True
        return False


# --- Example Usage & Inventory Setup ---

# 1. Create inventory items
part_1 = MotorPart(
    item_id=40291,
    name="NGK Iridium Spark Plug CPR9EAIX-9",
    description="High-performance spark plug with iridium tip.",
    category="Electrical",
    subcategory="Spark Plugs",
    price=450.00,
    stock_quantity=25,
    fitment_compatibility=[
        Fitment("Honda", "Click 125i", "2018-2026"),
        Fitment("Honda", "Click 150i", "2018-2025"),
        Fitment("Yamaha", "NMAX 155", "2020-2026")
    ]
)

part_2 = MotorPart(
    item_id=50112,
    name="Brembo Ceramic Front Brake Pads",
    description="Premium ceramic brake pads for superior stopping power.",
    category="Braking System",
    subcategory="Brake Pads",
    price=1200.00,
    stock_quantity=10,
    fitment_compatibility=[
        Fitment("Yamaha", "NMAX 155", "2015-2026"),
        Fitment("Yamaha", "Aerox 155", "2017-2026")
    ]
)

# Store all items in a master inventory list
inventory = [part_1, part_2]


# --- Search Function ---

def search_parts_by_bike(make: str, model: str) -> List[MotorPart]:
    """Returns a list of parts that fit the requested motorcycle."""
    matching_parts = [part for part in inventory if part.is_compatible(make, model)]
    return matching_parts


# --- Test the System ---

print("=== Searching parts for Yamaha NMAX 155 ===")
results = search_parts_by_bike("Yamaha", "NMAX 155")

for part in results:
    print(f"[{part.item_id}] {part.name} - ₱{part.price:.2f} ({part.subcategory})")
