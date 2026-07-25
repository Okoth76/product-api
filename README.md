MODEL VALIDATION

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

WHOLE MAIN.PY WITH ENDPOINTS

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel, Field, select, Session
from typing import List, Optional
from datetime import datetime
import logging

from database.session import get_session
from models.product import Product, ProductCreate, ProductUpdate, Supplier, SupplierCreate

app = FastAPI(title="TechVault Inventory API", version="1.0.0")


# LOGGING + ERROR RESPONSE FORMAT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def error_response(success: bool, status_code: int, message: str, path: str, errors=None):
    return {
        "success": success,
        "status_code": status_code,
        "message": message,
        "errors": errors,
        "timestamp": datetime.utcnow().isoformat(),
        "path": path
    }

# GLOBAL EXCEPTION HANDLERS

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(f"HTTP Exception: {exc.detail}")
    return JSONResponse(status_code=exc.status_code,
        content=error_response(False, exc.status_code, exc.detail, request.url.path))

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = [{"field": ".".join(str(loc) for loc in e["loc"]), "message": e["msg"], "type": e["type"]} for e in exc.errors()]
    return JSONResponse(status_code=422,
        content=error_response(False, 422, "Validation error", request.url.path, errors))

@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    logger.error(f"Integrity error: {exc}")
    return JSONResponse(status_code=409,
        content=error_response(False, 409, "Duplicate entry or constraint violation", request.url.path))

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(status_code=500,
        content=error_response(False, 500, "An internal error occurred", request.url.path))

# PRODUCT CRUD ENDPOINTS
@app.post("/products", response_model=Product, status_code=201)
def create_product(product: ProductCreate, session: Session = Depends(get_session)):
    db_product = Product(**product.dict())
    session.add(db_product)
    session.commit()
    session.refresh(db_product)
    return db_product

@app.get("/products", response_model=List[Product])
def list_products(session: Session = Depends(get_session)):
    return session.exec(select(Product)).all()

@app.get("/products/{product_id}", response_model=Product)
def get_product(product_id: int, session: Session = Depends(get_session)):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    return product

@app.patch("/products/{product_id}", response_model=Product)
def update_product(product_id: int, product_update: ProductUpdate, session: Session = Depends(get_session)):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    for key, value in product_update.dict(exclude_unset=True).items():
        setattr(product, key, value)
    product.updated_at = datetime.utcnow()
    session.commit()
    session.refresh(product)
    return product

@app.delete("/products/{product_id}", status_code=204)
def delete_product(product_id: int, session: Session = Depends(get_session)):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    session.delete(product)
    session.commit()
    return None

# SUPPLIER CRUD ENDPOINTS

@app.post("/suppliers", response_model=Supplier, status_code=201)
def create_supplier(supplier: SupplierCreate, session: Session = Depends(get_session)):
    db_supplier = Supplier(**supplier.dict())
    session.add(db_supplier)
    session.commit()
    session.refresh(db_supplier)
    return db_supplier

@app.get("/suppliers", response_model=List[Supplier])
def list_suppliers(session: Session = Depends(get_session)):
    return session.exec(select(Supplier)).all()

# BULK UPDATE ENDPOINT

@app.patch("/products/bulk-update")
def bulk_update_price(category: str, discount_percent: float, session: Session = Depends(get_session)):
    if discount_percent <= 0 or discount_percent > 100:
        raise HTTPException(400, "Discount percent must be between 0 and 100")

    products = session.exec(select(Product).where(Product.category == category)).all()
    if not products:
        raise HTTPException(404, "No products found in this category")

    updated = []
    for product in products:
        new_price = round(product.price * (1 - discount_percent / 100), 2)
        if new_price < 100:
            continue
        product.price = new_price
        product.updated_at = datetime.utcnow()
        updated.append(product)

    session.commit()
    return {"updated_count": len(updated), "category": category, "discount": discount_percent}

# STOCK ADJUSTMENT ENDPOINT

class StockAdjustment(SQLModel):
    product_id: int
    quantity_to_add: int = Field(gt=0)

@app.patch("/products/adjust-stock")
def adjust_stock(adjustments: List[StockAdjustment], session: Session = Depends(get_session)):
    results = {"success": [], "failed": []}
    for adj in adjustments:
        product = session.get(Product, adj.product_id)
        if not product:
            results["failed"].append({"product_id": adj.product_id, "reason": "Product not found"})
            continue
        new_stock = product.stock + adj.quantity_to_add
        if new_stock > 5000:
            results["failed"].append({"product_id": adj.product_id, "reason": "Stock exceeds limit"})
            continue
        product.stock = new_stock
        product.updated_at = datetime.utcnow()
        results["success"].append({"product_id": adj.product_id, "new_stock": new_stock})
    session.commit()
    return results


