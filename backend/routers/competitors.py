import json
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from db import get_db
from dependencies.auth import get_current_admin
from services.audit import record_audit
from services.entitlements import require_feature

router = APIRouter()


class CompetitorInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    website: Optional[str] = Field(default=None, max_length=500)
    address: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=2000)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    referenceItemName: Optional[str] = Field(default=None, max_length=200)
    referencePriceCents: Optional[int] = Field(default=None, ge=0)
    status: Literal["active", "archived"] = "active"

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("currency")
    @classmethod
    def clean_currency(cls, value: str) -> str:
        if not value.isalpha():
            raise ValueError("currency must contain three letters")
        return value.upper()


class CompetitorProductInput(BaseModel):
    competitorId: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=200)
    category: Optional[str] = Field(default=None, max_length=120)
    sizeLabel: Optional[str] = Field(default=None, max_length=100)
    sizeValue: Optional[float] = Field(default=None, gt=0)
    sizeUnit: Optional[str] = Field(default=None, max_length=30)
    estimatedServings: Optional[float] = Field(default=None, gt=0)
    ingredientsSummary: Optional[str] = Field(default=None, max_length=2000)
    regularPriceCents: int = Field(ge=0)
    dealPriceCents: Optional[int] = Field(default=None, ge=0)
    includedItems: list[str] = Field(default_factory=list, max_length=50)
    deliveryFeeCents: Optional[int] = Field(default=None, ge=0)
    marketPositioning: Optional[str] = Field(default=None, max_length=120)
    sourceUrl: Optional[str] = Field(default=None, max_length=1000)
    sourceType: Literal["website", "menu", "delivery_app", "social", "in_store", "other"] = "other"
    confidence: float = Field(default=50, ge=0, le=100)


class CompetitorDealInput(BaseModel):
    competitorId: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    priceCents: Optional[int] = Field(default=None, ge=0)
    includedItems: list[str] = Field(default_factory=list, max_length=50)
    sourceUrl: Optional[str] = Field(default=None, max_length=1000)
    status: Literal["active", "expired", "archived"] = "active"


class ProductComparisonInput(BaseModel):
    ownItemId: int = Field(ge=1)
    competitorProductId: int = Field(ge=1)
    matchQuality: float = Field(ge=0, le=100)
    normalizationNotes: Optional[str] = Field(default=None, max_length=2000)
    competitorNormalizedPriceCents: Optional[int] = Field(default=None, ge=0)


def _row_to_dict(row: tuple) -> dict:
    return {
        "id": row[0], "name": row[1], "website": row[2], "address": row[3], "notes": row[4],
        "currency": row[5], "referenceItemName": row[6],
        "referencePriceCents": row[7],
        "observedAt": row[8].isoformat() if row[8] else None,
        "status": row[9],
        "verifiedAt": row[10].isoformat() if row[10] else None,
        "verifiedBy": row[11],
        "createdAt": row[12].isoformat() if row[12] else None,
        "updatedAt": row[13].isoformat() if row[13] else None,
    }


_SELECT_COLUMNS = """id, name, website, address, notes, currency, reference_item_name,
                     reference_price_cents, observed_at, status, verified_at, verified_by,
                     created_at, updated_at"""


@router.get("/competitors")
def list_competitors(admin: dict = Depends(get_current_admin), _feature=Depends(require_feature("analytics.competitors"))):
    tenant_id = int(admin["restaurant_id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT {_SELECT_COLUMNS} FROM competitors WHERE tenant_id = %s ORDER BY name",
                (tenant_id,),
            )
            rows = cur.fetchall()
    return [_row_to_dict(row) for row in rows]


@router.post("/competitors", status_code=201)
def create_competitor(body: CompetitorInput, admin: dict = Depends(get_current_admin), _feature=Depends(require_feature("analytics.competitors"))):
    tenant_id = int(admin["restaurant_id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    f"""INSERT INTO competitors
                       (tenant_id, name, website, address, notes, currency, reference_item_name,
                        reference_price_cents, observed_at, status)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       RETURNING {_SELECT_COLUMNS}""",
                    (
                        tenant_id, body.name, body.website, body.address, body.notes,
                        body.currency.upper(), body.referenceItemName, body.referencePriceCents,
                        datetime.now(timezone.utc) if body.referencePriceCents is not None else None,
                        body.status,
                    ),
                )
            except Exception as exc:
                if "competitors_tenant_id_name_key" in str(exc):
                    raise HTTPException(status_code=409, detail="A competitor with this name already exists")
                raise
            row = cur.fetchone()
            record_audit(
                cur, tenant_id=tenant_id, actor_type="admin", actor_id=str(admin["id"]),
                action="competitor.created", resource_type="competitor", resource_id=str(row[0]),
                after=body.model_dump(),
            )
    return _row_to_dict(row)


@router.put("/competitors/{competitor_id}")
def update_competitor(competitor_id: int, body: CompetitorInput, admin: dict = Depends(get_current_admin), _feature=Depends(require_feature("analytics.competitors"))):
    tenant_id = int(admin["restaurant_id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT {_SELECT_COLUMNS} FROM competitors WHERE tenant_id = %s AND id = %s",
                (tenant_id, competitor_id),
            )
            existing = cur.fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="Competitor not found")
            existing_data = _row_to_dict(existing)
            price_changed = body.referencePriceCents != existing_data["referencePriceCents"]
            try:
                cur.execute(
                    f"""UPDATE competitors SET
                          name = %s, website = %s, address = %s, notes = %s, currency = %s,
                          reference_item_name = %s, reference_price_cents = %s,
                          observed_at = CASE WHEN %s THEN %s ELSE observed_at END,
                          status = %s, updated_at = NOW()
                        WHERE tenant_id = %s AND id = %s
                        RETURNING {_SELECT_COLUMNS}""",
                    (
                        body.name, body.website, body.address, body.notes, body.currency.upper(),
                        body.referenceItemName, body.referencePriceCents,
                        price_changed, datetime.now(timezone.utc) if body.referencePriceCents is not None else None,
                        body.status, tenant_id, competitor_id,
                    ),
                )
            except Exception as exc:
                if "competitors_tenant_id_name_key" in str(exc):
                    raise HTTPException(status_code=409, detail="A competitor with this name already exists")
                raise
            row = cur.fetchone()
            record_audit(
                cur, tenant_id=tenant_id, actor_type="admin", actor_id=str(admin["id"]),
                action="competitor.updated", resource_type="competitor", resource_id=str(competitor_id),
                before=existing_data, after=body.model_dump(),
            )
    return _row_to_dict(row)


@router.delete("/competitors/{competitor_id}", status_code=204)
def delete_competitor(competitor_id: int, admin: dict = Depends(get_current_admin), _feature=Depends(require_feature("analytics.competitors"))):
    tenant_id = int(admin["restaurant_id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM competitors WHERE tenant_id = %s AND id = %s RETURNING id",
                (tenant_id, competitor_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Competitor not found")
            record_audit(
                cur, tenant_id=tenant_id, actor_type="admin", actor_id=str(admin["id"]),
                action="competitor.deleted", resource_type="competitor", resource_id=str(competitor_id),
            )
    return None


@router.post("/competitors/{competitor_id}/verify")
def verify_competitor(competitor_id: int, admin: dict = Depends(get_current_admin), _feature=Depends(require_feature("analytics.competitors"))):
    tenant_id = int(admin["restaurant_id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""UPDATE competitors SET verified_at = NOW(), verified_by = %s, updated_at = NOW()
                    WHERE tenant_id = %s AND id = %s
                    RETURNING {_SELECT_COLUMNS}""",
                (str(admin["id"]), tenant_id, competitor_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Competitor not found")
            record_audit(
                cur, tenant_id=tenant_id, actor_type="admin", actor_id=str(admin["id"]),
                action="competitor.verified", resource_type="competitor", resource_id=str(competitor_id),
            )
    return _row_to_dict(row)


def _require_competitor(cur, tenant_id: int, competitor_id: int) -> None:
    cur.execute("SELECT 1 FROM competitors WHERE tenant_id = %s AND id = %s", (tenant_id, competitor_id))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Competitor not found")


@router.get("/competitors/products")
def list_products(competitorId: Optional[int] = None, limit: int = 100, admin: dict = Depends(get_current_admin), _feature=Depends(require_feature("analytics.competitors"))):
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 200")
    tenant_id = int(admin["restaurant_id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, competitor_id, name, category, size_label, regular_price_cents,
                          deal_price_cents, source_url, captured_at, verified_at, confidence
                   FROM competitor_products WHERE tenant_id = %s AND (%s IS NULL OR competitor_id = %s)
                   ORDER BY captured_at DESC LIMIT %s""",
                (tenant_id, competitorId, competitorId, limit),
            )
            rows = cur.fetchall()
    return [{"id": r[0], "competitorId": r[1], "name": r[2], "category": r[3], "sizeLabel": r[4], "regularPriceCents": r[5], "dealPriceCents": r[6], "sourceUrl": r[7], "capturedAt": r[8].isoformat(), "verifiedAt": r[9].isoformat() if r[9] else None, "confidence": float(r[10])} for r in rows]


@router.post("/competitors/products", status_code=201)
def create_product(body: CompetitorProductInput, admin: dict = Depends(get_current_admin), _feature=Depends(require_feature("analytics.competitors"))):
    tenant_id = int(admin["restaurant_id"])
    actor_id = str(admin["id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            _require_competitor(cur, tenant_id, body.competitorId)
            cur.execute(
                """INSERT INTO competitor_products
                   (tenant_id, competitor_id, name, category, size_label, size_value, size_unit,
                    estimated_servings, ingredients_summary, regular_price_cents, deal_price_cents,
                    included_items, delivery_fee_cents, market_positioning, source_url, source_type, confidence)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s)
                   RETURNING id, captured_at""",
                (tenant_id, body.competitorId, body.name.strip(), body.category, body.sizeLabel,
                 body.sizeValue, body.sizeUnit, body.estimatedServings, body.ingredientsSummary,
                 body.regularPriceCents, body.dealPriceCents, json.dumps(body.includedItems),
                 body.deliveryFeeCents, body.marketPositioning, body.sourceUrl, body.sourceType, body.confidence),
            )
            row = cur.fetchone()
            record_audit(cur, tenant_id=tenant_id, actor_type="admin", actor_id=actor_id, action="competitor_product.created", resource_type="competitor_product", resource_id=str(row[0]), after=body.model_dump())
    return {"id": row[0], "capturedAt": row[1].isoformat()}


@router.get("/competitors/deals")
def list_deals(competitorId: Optional[int] = None, limit: int = 100, admin: dict = Depends(get_current_admin), _feature=Depends(require_feature("analytics.competitors"))):
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 200")
    tenant_id = int(admin["restaurant_id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, competitor_id, name, description, price_cents, included_items, status, captured_at, verified_at FROM competitor_deals WHERE tenant_id = %s AND (%s IS NULL OR competitor_id = %s) ORDER BY captured_at DESC LIMIT %s", (tenant_id, competitorId, competitorId, limit))
            rows = cur.fetchall()
    return [{"id": r[0], "competitorId": r[1], "name": r[2], "description": r[3], "priceCents": r[4], "includedItems": r[5], "status": r[6], "capturedAt": r[7].isoformat(), "verifiedAt": r[8].isoformat() if r[8] else None} for r in rows]


@router.post("/competitors/deals", status_code=201)
def create_deal(body: CompetitorDealInput, admin: dict = Depends(get_current_admin), _feature=Depends(require_feature("analytics.competitors"))):
    tenant_id = int(admin["restaurant_id"])
    actor_id = str(admin["id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            _require_competitor(cur, tenant_id, body.competitorId)
            cur.execute("INSERT INTO competitor_deals (tenant_id, competitor_id, name, description, price_cents, included_items, source_url, status) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s) RETURNING id, captured_at", (tenant_id, body.competitorId, body.name.strip(), body.description, body.priceCents, json.dumps(body.includedItems), body.sourceUrl, body.status))
            row = cur.fetchone()
            record_audit(cur, tenant_id=tenant_id, actor_type="admin", actor_id=actor_id, action="competitor_deal.created", resource_type="competitor_deal", resource_id=str(row[0]), after=body.model_dump())
    return {"id": row[0], "capturedAt": row[1].isoformat()}


@router.get("/competitors/comparisons")
def list_comparisons(limit: int = 100, admin: dict = Depends(get_current_admin), _feature=Depends(require_feature("analytics.competitors"))):
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 200")
    tenant_id = int(admin["restaurant_id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT pc.id, pc.own_item_id, m.name, pc.competitor_product_id, cp.name,
                                  pc.match_quality, pc.own_normalized_price_cents,
                                  pc.competitor_normalized_price_cents, pc.price_index,
                                  pc.approved_by_human, pc.approved_at
                           FROM product_comparisons pc
                           JOIN menu_items m ON m.id = pc.own_item_id AND m.restaurant_id = pc.tenant_id
                           JOIN competitor_products cp ON cp.id = pc.competitor_product_id AND cp.tenant_id = pc.tenant_id
                           WHERE pc.tenant_id = %s ORDER BY pc.created_at DESC LIMIT %s""", (tenant_id, limit))
            rows = cur.fetchall()
    return [{"id": r[0], "ownItemId": r[1], "ownItemName": r[2], "competitorProductId": r[3], "competitorProductName": r[4], "matchQuality": float(r[5]), "ownNormalizedPriceCents": r[6], "competitorNormalizedPriceCents": r[7], "priceIndex": float(r[8]) if r[8] is not None else None, "approvedByHuman": r[9], "approvedAt": r[10].isoformat() if r[10] else None} for r in rows]


@router.post("/competitors/comparisons", status_code=201)
def create_comparison(body: ProductComparisonInput, admin: dict = Depends(get_current_admin), _feature=Depends(require_feature("analytics.competitors"))):
    tenant_id = int(admin["restaurant_id"])
    actor_id = str(admin["id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(sale_price_cents, price_cents) FROM menu_items WHERE restaurant_id = %s AND id = %s", (tenant_id, body.ownItemId))
            own = cur.fetchone()
            if not own:
                raise HTTPException(status_code=404, detail="Menu item not found")
            cur.execute("SELECT COALESCE(deal_price_cents, regular_price_cents) FROM competitor_products WHERE tenant_id = %s AND id = %s", (tenant_id, body.competitorProductId))
            competitor = cur.fetchone()
            if not competitor:
                raise HTTPException(status_code=404, detail="Competitor product not found")
            own_price = int(own[0])
            competitor_price = body.competitorNormalizedPriceCents if body.competitorNormalizedPriceCents is not None else int(competitor[0])
            price_index = (own_price / competitor_price * 100) if competitor_price else None
            cur.execute("""INSERT INTO product_comparisons
                           (tenant_id, own_item_id, competitor_product_id, match_quality, normalization_notes,
                            own_normalized_price_cents, competitor_normalized_price_cents, price_index)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (tenant_id, own_item_id, competitor_product_id) DO UPDATE SET
                             match_quality = EXCLUDED.match_quality, normalization_notes = EXCLUDED.normalization_notes,
                             own_normalized_price_cents = EXCLUDED.own_normalized_price_cents,
                             competitor_normalized_price_cents = EXCLUDED.competitor_normalized_price_cents,
                             price_index = EXCLUDED.price_index, approved_by_human = false,
                             approved_by = NULL, approved_at = NULL, updated_at = NOW()
                           RETURNING id""", (tenant_id, body.ownItemId, body.competitorProductId, body.matchQuality, body.normalizationNotes, own_price, competitor_price, price_index))
            comparison_id = cur.fetchone()[0]
            record_audit(cur, tenant_id=tenant_id, actor_type="admin", actor_id=actor_id, action="competitor_comparison.created", resource_type="product_comparison", resource_id=str(comparison_id), after={**body.model_dump(), "priceIndex": price_index})
    return {"id": comparison_id, "priceIndex": price_index, "approvedByHuman": False}


@router.post("/competitors/comparisons/{comparison_id}/approve")
def approve_comparison(comparison_id: int, admin: dict = Depends(get_current_admin), _feature=Depends(require_feature("analytics.competitors"))):
    tenant_id = int(admin["restaurant_id"])
    actor_id = str(admin["id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE product_comparisons SET approved_by_human = true, approved_by = %s, approved_at = NOW(), updated_at = NOW() WHERE tenant_id = %s AND id = %s RETURNING id, approved_at", (actor_id, tenant_id, comparison_id))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Comparison not found")
            record_audit(cur, tenant_id=tenant_id, actor_type="admin", actor_id=actor_id, action="competitor_comparison.approved", resource_type="product_comparison", resource_id=str(comparison_id))
    return {"id": row[0], "approvedByHuman": True, "approvedAt": row[1].isoformat()}
