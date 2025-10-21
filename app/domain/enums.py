# app/domain/enums.py
import enum

class CartStatus(str, enum.Enum):
    active = "active"
    converted = "converted"
    abandoned = "abandoned"
