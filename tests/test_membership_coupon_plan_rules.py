import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from adapter.routers.membership import _resolve_coupon_aware_preview
from backend.models.errors import PreconditionFailure
from backend.system.membership_marketing_store import MembershipMarketingStore
from backend.system.membership_payment_service import PAYMENT_PROVIDER_MANUAL_TEST
from backend.system.membership_store import (
    MEMBERSHIP_PLAN_COUPON_UNSUPPORTED_MESSAGE,
    MEMBERSHIP_PLAN_GRADUATE_EXAM,
    MEMBERSHIP_PLAN_MONTHLY,
    MEMBERSHIP_PRICING_VERSION,
    MembershipStore,
)


FIXED_NOW = datetime(2026, 5, 17, 4, 0, tzinfo=timezone.utc)


def _stores(db_path: Path) -> tuple[MembershipStore, MembershipMarketingStore]:
    return MembershipStore(db_path), MembershipMarketingStore(db_path)


def test_monthly_plan_still_accepts_available_coupon(tmp_path):
    membership_store, marketing_store = _stores(tmp_path / "membership.sqlite3")
    coupon = marketing_store.grant_coupon(
        "user_coupon",
        amount_cent=500,
        title="测试 5 元券",
        expires_in_days=30,
    )

    preview = _resolve_coupon_aware_preview(
        user_id="user_coupon",
        plan_id=MEMBERSHIP_PLAN_MONTHLY,
        coupon_id=coupon.coupon_id,
        membership_store=membership_store,
        membership_marketing_store=marketing_store,
    )

    assert preview.plan_id == MEMBERSHIP_PLAN_MONTHLY
    assert preview.coupon_id == coupon.coupon_id
    assert preview.coupon_discount_cent == 500
    assert preview.payable_amount_cent == 1500


def test_graduate_exam_plan_rejects_coupon_at_router_preview(tmp_path):
    membership_store, marketing_store = _stores(tmp_path / "membership.sqlite3")
    coupon = marketing_store.grant_coupon(
        "user_coupon",
        amount_cent=500,
        title="测试 5 元券",
        expires_in_days=30,
    )

    with pytest.raises(PreconditionFailure, match=MEMBERSHIP_PLAN_COUPON_UNSUPPORTED_MESSAGE):
        _resolve_coupon_aware_preview(
            user_id="user_coupon",
            plan_id=MEMBERSHIP_PLAN_GRADUATE_EXAM,
            coupon_id=coupon.coupon_id,
            membership_store=membership_store,
            membership_marketing_store=marketing_store,
        )


def test_graduate_exam_plan_rejects_coupon_at_membership_store(tmp_path):
    membership_store = MembershipStore(tmp_path / "membership.sqlite3")

    with pytest.raises(PreconditionFailure, match=MEMBERSHIP_PLAN_COUPON_UNSUPPORTED_MESSAGE):
        membership_store.preview_order(
            "user_coupon",
            plan_id=MEMBERSHIP_PLAN_GRADUATE_EXAM,
            coupon_id="mcpn_test",
            coupon_discount_cent=1,
        )


def test_graduate_exam_plan_with_coupon_cannot_be_confirmed(tmp_path):
    db_path = tmp_path / "membership.sqlite3"
    membership_store = MembershipStore(db_path)
    marketing_store = MembershipMarketingStore(db_path)
    coupon = marketing_store.grant_coupon(
        "user_coupon",
        amount_cent=500,
        title="测试 5 元券",
        expires_in_days=30,
    )
    created_at = FIXED_NOW.isoformat()
    expired_at = FIXED_NOW.replace(hour=5).isoformat()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO membership_orders (
                order_id,
                user_id,
                plan_id,
                order_type,
                pricing_version,
                period_days,
                list_amount_cent,
                first_order_discount_cent,
                coupon_discount_cent,
                payable_amount_cent,
                coupon_id,
                provider,
                status,
                client_ip,
                client_version,
                created_at,
                expired_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)
            """,
            (
                "mord_graduate_with_coupon",
                "user_coupon",
                MEMBERSHIP_PLAN_GRADUATE_EXAM,
                "first_purchase",
                MEMBERSHIP_PRICING_VERSION,
                218,
                10900,
                0,
                500,
                10400,
                coupon.coupon_id,
                PAYMENT_PROVIDER_MANUAL_TEST,
                "",
                "",
                created_at,
                expired_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    with patch("backend.system.membership_store._utc_now", return_value=FIXED_NOW):
        with pytest.raises(PreconditionFailure, match=MEMBERSHIP_PLAN_COUPON_UNSUPPORTED_MESSAGE):
            membership_store.confirm_payment(
                "user_coupon",
                provider=PAYMENT_PROVIDER_MANUAL_TEST,
                order_id="mord_graduate_with_coupon",
            )


def test_graduate_exam_plan_with_coupon_discount_cannot_be_confirmed(tmp_path):
    db_path = tmp_path / "membership.sqlite3"
    membership_store = MembershipStore(db_path)
    created_at = FIXED_NOW.isoformat()
    expired_at = FIXED_NOW.replace(hour=5).isoformat()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO membership_orders (
                order_id,
                user_id,
                plan_id,
                order_type,
                pricing_version,
                period_days,
                list_amount_cent,
                first_order_discount_cent,
                coupon_discount_cent,
                payable_amount_cent,
                coupon_id,
                provider,
                status,
                client_ip,
                client_version,
                created_at,
                expired_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, 'pending', ?, ?, ?, ?)
            """,
            (
                "mord_graduate_with_coupon_discount",
                "user_coupon",
                MEMBERSHIP_PLAN_GRADUATE_EXAM,
                "first_purchase",
                MEMBERSHIP_PRICING_VERSION,
                218,
                10900,
                0,
                500,
                10400,
                PAYMENT_PROVIDER_MANUAL_TEST,
                "",
                "",
                created_at,
                expired_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    with patch("backend.system.membership_store._utc_now", return_value=FIXED_NOW):
        with pytest.raises(PreconditionFailure, match=MEMBERSHIP_PLAN_COUPON_UNSUPPORTED_MESSAGE):
            membership_store.confirm_payment(
                "user_coupon",
                provider=PAYMENT_PROVIDER_MANUAL_TEST,
                order_id="mord_graduate_with_coupon_discount",
            )
