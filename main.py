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