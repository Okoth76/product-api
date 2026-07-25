from sqlmodel import SQLModel, Field, Relationship
from pydantic import field_validator, model_validator
from datetime import datetime
from typing import Optional
from typing import List
import re


class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, min_length=2, max_length=100)
    description: str = Field(min_length=10, max_length=500)
    brand: str = Field(index=True)
    category: str = Field(index=True)
    price: float = Field(gt=0)
    stock: int = Field(ge=0)
    warranty_months: int = Field(ge=0)
    sku: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    supplier_id: Optional[int] = Field(default=None, foreign_key="supplier.id")
    supplier: Optional["Supplier"] = Relationship(back_populates="products")


class ProductCreate(SQLModel):
    name: str
    description: str
    brand: str
    category: str
    price: float
    stock: int
    warranty_months: int
    sku: str

    # ✅ Name validation
    @field_validator("name")
    def validate_name(cls, v):
        if not v[0].isupper():
            raise ValueError("Name must start with a capital letter")
        if re.search(r'[^a-zA-Z0-9\s-]', v):
            raise ValueError("Name cannot contain special characters")
        if len(v.split()) < 1:
            raise ValueError("Name must contain at least one word")
        return v

    # ✅ Brand standardization
    @field_validator("brand")
    def validate_brand(cls, v):
        allowed = ["HP", "Dell", "Lenovo", "Apple", "Samsung", "Intel", "AMD", "Corsair", "Logitech", "Other"]
        v = v.strip().title()
        if v.upper() in [b.upper() for b in allowed]:
            return v
        raise ValueError(f"Brand {v} not allowed")

    # ✅ Category validation
    @field_validator("category")
    def validate_category(cls, v):
        allowed = ["Laptops", "Monitors", "Storage", "Processors", "Memory", "Keyboards", "Mice", "Accessories"]
        if v.title() not in allowed:
            raise ValueError(f"Category {v} not allowed")
        return v.title()

    # ✅ Price validation
    @field_validator("price")
    def validate_price(cls, v):
        if v < 100:
            raise ValueError("Price must be at least 100 KSh")
        if v > 500000:
            raise ValueError("Price cannot exceed 500,000 KSh")
        return round(v, 2)

    # ✅ SKU validation
    @field_validator("sku")
    def validate_sku(cls, v):
        pattern = r"^[A-Z]{3,4}-[A-Z]{2,4}-[0-9]{4}$"
        if not re.match(pattern, v):
            raise ValueError("SKU must follow format CAT-BRAND-XXXX")
        return v

    # ✅ Warranty range validation
    @field_validator("warranty_months")
    def validate_warranty_range(cls, v):
        if v < 0 or v > 36:
            raise ValueError("Warranty must be between 0 and 36 months")
        return v

    # ✅ Cross-field check: price vs warranty (runs after all fields are validated)
    @model_validator(mode="after")
    def validate_warranty_vs_price(self):
        if self.price and self.price > 50000 and self.warranty_months < 12:
            raise ValueError("Products over 50,000 KSh must have at least 12 months warranty")
        return self


class ProductUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    warranty_months: Optional[int] = None
    sku: Optional[str] = None
    supplier_id: Optional[int] = None


class Supplier(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    contact_person: str
    email: str = Field(unique=True, index=True)
    phone: str
    is_active: bool = Field(default=True)

    products: List["Product"] = Relationship(back_populates="supplier")


class SupplierCreate(SQLModel):
    name: str
    contact_person: str
    email: str
    phone: str

    # ✅ Name validation
    @field_validator("name")
    def validate_name(cls, v):
        if not v[0].isupper():
            raise ValueError("Name must start with a capital letter")
        if re.search(r'[^a-zA-Z0-9\s-]', v):
            raise ValueError("Name cannot contain special characters")
        return v

    # ✅ Email validation
    @field_validator("email")
    def validate_email(cls, v):
        pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        if not re.match(pattern, v):
            raise ValueError("Invalid email format")
        return v

    # ✅ Phone validation
    @field_validator("phone")
    def validate_phone(cls, v):
        if not re.match(r"^\+?\d{7,15}$", v):
            raise ValueError("Invalid phone number")
        return v