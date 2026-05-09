from functools import lru_cache
from pathlib import Path

from fastapi import Request

from adapter.auth import require_request_auth_user
from backend.models.errors import PreconditionFailure
from backend.system.api import SystemAPI
from backend.system.auth_rate_limit_store import AuthRateLimitStore
from backend.system.auth_store import AuthStore
from backend.system.inmemory_system import InMemorySystem
from backend.system.membership_marketing_store import MembershipMarketingStore
from backend.system.membership_commission_store import MembershipCommissionStore
from backend.system.membership_payment_service import MembershipPaymentService
from backend.system.membership_store import MembershipStore
from backend.system.sql_backend import create_persist_store


@lru_cache(maxsize=1)
def get_api() -> SystemAPI:
    project_root = Path(__file__).resolve().parent.parent
    persist_store = create_persist_store(legacy_root=project_root)
    sys = InMemorySystem(persist_store=persist_store)
    return SystemAPI(sys)


@lru_cache(maxsize=1)
def get_auth_store() -> AuthStore:
    return AuthStore()


@lru_cache(maxsize=1)
def get_auth_rate_limit_store() -> AuthRateLimitStore:
    return AuthRateLimitStore()


@lru_cache(maxsize=1)
def get_membership_store() -> MembershipStore:
    return MembershipStore()


@lru_cache(maxsize=1)
def get_membership_marketing_store() -> MembershipMarketingStore:
    return MembershipMarketingStore()


@lru_cache(maxsize=1)
def get_membership_commission_store() -> MembershipCommissionStore:
    return MembershipCommissionStore()


@lru_cache(maxsize=1)
def get_membership_payment_service() -> MembershipPaymentService:
    return MembershipPaymentService()


MEMBER_ONLY_FEATURE_MESSAGE = "This feature requires active membership."


def require_active_membership(request: Request, membership_store: MembershipStore) -> None:
    user = require_request_auth_user(request)
    summary = membership_store.get_membership_summary(user.user_id)
    if not summary.is_active:
        raise PreconditionFailure(MEMBER_ONLY_FEATURE_MESSAGE)
