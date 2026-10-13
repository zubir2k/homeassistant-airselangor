"""Async client for the Air Selangor customer API (api3.airselangor.com).

Reverse-engineered from the www.airselangor.com Next.js portal:

* Every request is a JSON ``POST`` to ``https://api3.airselangor.com/<path>``.
* Unauthenticated calls (login, token refresh) carry a "public token":
  ``Authorization: Bearer sha256("airselangorsecretkey" + Timestamp)`` where
  ``Timestamp`` is the same UTC ``YYYY-MM-DDTHH:MM:SSZ`` value sent as a header.
* Authenticated calls carry ``Authorization: Bearer <accesstoken>`` from login.
* Responses are wrapped: ``{"status": bool, "message": str,
  "error": {"code", "message"} | null, "data": {...}}``.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://api3.airselangor.com/"
PUBLIC_SECRET = "airselangorsecretkey"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 HomeAssistant-AirSelangor"
)
DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=30)

# Error code returned (with HTTP 400) for an expired or invalid access token.
INVALID_TOKEN_CODES = {"999"}

# Login error codes: 129 = wrong login ID/password (response carries the
# remaining "attempts"), 111/112 = temporarily locked out. 104 is the API's
# generic "Unexpected error" (e.g. a malformed device payload) and is transient.
INVALID_CREDENTIALS_CODES = {"129"}
LOCKED_OUT_CODES = {"111", "112"}

# watertrend "type": 1 = latest 6 bills, 2 = the 6 bills before those.
TREND_RECENT = 1
TREND_PREVIOUS = 2


class AirSelangorError(Exception):
    """Base error."""


class AirSelangorAuthError(AirSelangorError):
    """Credentials rejected (or the account is temporarily locked)."""


class AirSelangorApiError(AirSelangorError):
    """The API returned an error envelope or an unexpected response."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


class AirSelangorConnectionError(AirSelangorError):
    """Network-level failure."""


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _to_date(value: Any) -> date | None:
    """Parse ``2026-10-21T00:00:00`` style dates."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:19]).date()
    except ValueError:
        return None


def _parse_portal_datetime(value: Any) -> datetime | None:
    """Parse portal timestamps into an aware datetime.

    The API returns either ISO-8601 UTC (``2025-11-24T22:52:55.091594Z``) or a
    display string (``Tue 2025-11-25 6:52 AM (UTC+08:00)``) depending on the
    client, so both are accepted.
    """
    if not value:
        return None
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
    if parsed is not None:
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    try:
        body, _, zone = text.partition("(UTC")
        parts = body.split()
        if parts and not parts[0][0].isdigit():
            parts = parts[1:]  # drop weekday
        naive = datetime.strptime(" ".join(parts[:3]), "%Y-%m-%d %I:%M %p")
        offset = zone.rstrip(")").strip() or "+00:00"
        return datetime.fromisoformat(naive.isoformat() + offset)
    except (ValueError, IndexError):
        return None


@dataclass(slots=True)
class WaterAccount:
    """One water account linked to the portal user."""

    account_id: str
    account_number: str
    display_name: str
    address: str | None = None
    status: str | None = None
    is_smart_meter: bool = False
    is_ebill: bool = False

    @classmethod
    def from_api(cls, item: dict[str, Any]) -> WaterAccount:
        return cls(
            account_id=item["wateraccountid"],
            account_number=str(item["accountnumber"]),
            display_name=item.get("displayname") or str(item["accountnumber"]),
            address=item.get("address"),
            status=item.get("status"),
            is_smart_meter=bool(item.get("issmartmeter")),
            is_ebill=bool(item.get("is_ebil")),
        )


@dataclass(slots=True)
class Bill:
    """One monthly bill from the water-trend endpoint."""

    bill_date: date
    usage_m3: float
    amount_rm: float

    @classmethod
    def from_api(cls, item: dict[str, Any]) -> Bill | None:
        bill_date = _to_date(item.get("billdate"))
        if bill_date is None:
            return None
        return cls(
            bill_date=bill_date,
            usage_m3=_to_float(item.get("waterusage")) or 0.0,
            amount_rm=_to_float(item.get("amount")) or 0.0,
        )


@dataclass(slots=True)
class Payment:
    """One payment transaction."""

    reference: str
    amount_rm: float | None
    status: str | None
    method: str | None
    bank: str | None
    paid_at: datetime | None

    @classmethod
    def from_api(cls, item: dict[str, Any]) -> Payment:
        return cls(
            reference=item.get("referenceno") or item.get("transactionid") or "",
            amount_rm=_to_float(item.get("amount")),
            status=item.get("status"),
            method=item.get("paymenttype") or None,
            bank=item.get("bank") or None,
            paid_at=_parse_portal_datetime(item.get("transactiondate")),
        )


@dataclass(slots=True)
class AccountData:
    """Everything the integration shows for one account."""

    account: WaterAccount
    current_balance_rm: float | None = None
    outstanding_rm: float | None = None
    # Negative values mean the account is in credit.
    overdue_rm: float | None = None
    latest_bill_amount_rm: float | None = None
    overdue_status: str | None = None
    bill_number: str | None = None
    bill_date: date | None = None
    due_date: date | None = None
    last_payment_date: date | None = None
    household_size: int | None = None
    lcd_target_lpcd: float | None = None
    bills: list[Bill] = field(default_factory=list)
    payments: list[Payment] = field(default_factory=list)
    raw_details: dict[str, Any] = field(default_factory=dict)

    @property
    def latest_bill(self) -> Bill | None:
        return self.bills[-1] if self.bills else None

    @property
    def previous_bill(self) -> Bill | None:
        return self.bills[-2] if len(self.bills) > 1 else None

    @property
    def average_usage_m3(self) -> float | None:
        if not self.bills:
            return None
        return round(sum(b.usage_m3 for b in self.bills) / len(self.bills), 2)

    @property
    def usage_per_person_lpd(self) -> float | None:
        """Litres per person per day for the latest bill (portal's LCD maths)."""
        bill = self.latest_bill
        if bill is None or not self.household_size:
            return None
        days = 30
        if self.previous_bill:
            days = max((bill.bill_date - self.previous_bill.bill_date).days, 1)
        return round(bill.usage_m3 * 1000 / days / self.household_size, 1)

    @property
    def last_payment(self) -> Payment | None:
        ok = [p for p in self.payments if p.paid_at is not None]
        return max(ok, key=lambda p: p.paid_at) if ok else None


class AirSelangorClient:
    """Minimal async client. Re-logs in automatically when the token expires."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        login_id: str,
        password: str,
    ) -> None:
        self._session = session
        self._login_id = login_id
        self._password = password
        self._device_uid = str(uuid.uuid4())
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._csrf_token: str | None = None
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ http
    @staticmethod
    def _timestamp() -> str:
        return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _headers(self, authenticated: bool) -> dict[str, str]:
        ts = self._timestamp()
        headers = {
            "Timestamp": ts,
            "Language": "en",
            "Transactionid": str(uuid.uuid4()),
            "device-name": "browser",
            "os-type": "web",
            "os-version": "home-assistant",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": "https://www.airselangor.com",
            "Referer": "https://www.airselangor.com/",
            "User-Agent": USER_AGENT,
        }
        if authenticated and self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
            if self._csrf_token:
                headers["X-Csrf-Token"] = self._csrf_token
        else:
            public = hashlib.sha256(f"{PUBLIC_SECRET}{ts}".encode()).hexdigest()
            headers["Authorization"] = f"Bearer {public}"
        return headers

    async def _raw_post(
        self, path: str, body: dict[str, Any], authenticated: bool
    ) -> tuple[int, Any]:
        url = BASE_URL + path.lstrip("/")
        try:
            async with self._session.post(
                url,
                json=body,
                headers=self._headers(authenticated),
                timeout=DEFAULT_TIMEOUT,
            ) as resp:
                try:
                    payload = await resp.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError):
                    payload = None
                return resp.status, payload
        except (TimeoutError, aiohttp.ClientError) as err:
            raise AirSelangorConnectionError(f"{path}: {err}") from err

    @staticmethod
    def _unwrap(path: str, status: int, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise AirSelangorApiError(f"{path}: HTTP {status}, non-JSON response")
        if not payload.get("status"):
            err = payload.get("error") or {}
            raise AirSelangorApiError(
                f"{path}: {err.get('message') or payload.get('message')}",
                code=str(err.get("code")) if err.get("code") is not None else None,
            )
        return payload.get("data") or {}

    async def _post(self, path: str, body: dict[str, Any] | None = None) -> dict:
        body = body or {}
        if self._access_token is None:
            await self.login()
        status, payload = await self._raw_post(path, body, True)
        if self._token_rejected(status, payload):
            _LOGGER.debug("Access token rejected on %s, re-authenticating", path)
            await self._reauthenticate()
            status, payload = await self._raw_post(path, body, True)
            if self._token_rejected(status, payload):
                raise AirSelangorAuthError("Session rejected after re-login")
        return self._unwrap(path, status, payload)

    @staticmethod
    def _token_rejected(status: int, payload: Any) -> bool:
        if status == 401:
            return True
        if isinstance(payload, dict) and not payload.get("status"):
            code = (payload.get("error") or {}).get("code")
            return str(code) in INVALID_TOKEN_CODES
        return False

    # ------------------------------------------------------------------ auth
    async def login(self) -> None:
        """Log in with the portal login ID (IC/passport/email) and password."""
        async with self._lock:
            status, payload = await self._raw_post(
                "/authentication/v1/login",
                {
                    "loginid": self._login_id,
                    "password": self._password,
                    "deviceuid": self._device_uid,
                    "apptype": "1",
                    "loginType": "1",
                    # The API answers 104 unless the browser fingerprint fields
                    # the portal sends (ua-parser output) are all present.
                    "ostype": "Linux",
                    "osversion": "x86_64",
                    "devicename": "Chrome",
                    "app": "Chrome",
                    "appversion": "126",
                },
                False,
            )
            if status >= 500:
                raise AirSelangorConnectionError(f"login: HTTP {status}")
            try:
                data = self._unwrap("login", status, payload)
            except AirSelangorApiError as err:
                if err.code in LOCKED_OUT_CODES:
                    raise AirSelangorAuthError(
                        "Account temporarily locked after failed logins"
                    ) from err
                has_attempts = (
                    isinstance(payload, dict)
                    and isinstance(payload.get("data"), dict)
                    and "attempts" in payload["data"]
                )
                if err.code in INVALID_CREDENTIALS_CODES or has_attempts:
                    raise AirSelangorAuthError(str(err)) from err
                raise
            token = data.get("accesstoken")
            if not token:
                raise AirSelangorAuthError("Login returned no access token")
            self._access_token = token
            self._refresh_token = data.get("refreshtoken")
            self._csrf_token = data.get("csrftoken")

    async def _reauthenticate(self) -> None:
        """Try the refresh token first, then a full login."""
        if self._refresh_token:
            status, payload = await self._raw_post(
                "/authentication/v1/refreshtoken",
                {"refreshtoken": self._refresh_token},
                False,
            )
            if (
                status == 200
                and isinstance(payload, dict)
                and payload.get("status")
                and (payload.get("data") or {}).get("accesstoken")
            ):
                self._access_token = payload["data"]["accesstoken"]
                return
        self._access_token = None
        await self.login()

    # ------------------------------------------------------------------ data
    async def get_profile(self) -> dict[str, Any]:
        return await self._post("/userprofile/v2/view/basic")

    async def get_accounts(self) -> list[WaterAccount]:
        accounts: list[WaterAccount] = []
        offset = 0
        while True:
            data = await self._post(
                "/wateraccount/v1/dashboardlist",
                {"offset": offset, "limit": 100, "isebiztab": False},
            )
            items = data.get("items") or []
            accounts.extend(WaterAccount.from_api(i) for i in items)
            total = int(data.get("total") or 0)
            offset += 100
            if not items or offset >= total:
                return accounts

    async def get_account_details(self, account_id: str) -> dict[str, Any]:
        data = await self._post(
            "/wateraccount/v1/details", {"wateraccountid": account_id}
        )
        return data.get("accountdetails") or {}

    async def get_bills(self, account_number: str) -> list[Bill]:
        """Up to 12 monthly bills, oldest first."""
        bills: dict[date, Bill] = {}
        for trend_type in (TREND_PREVIOUS, TREND_RECENT):
            data = await self._post(
                "/billing/v1/watertrend",
                {"accountnumber": account_number, "type": trend_type},
            )
            for item in data.get("items") or []:
                bill = Bill.from_api(item)
                if bill is not None:
                    bills[bill.bill_date] = bill
        return [bills[d] for d in sorted(bills)]

    async def get_household_usage(self, account_id: str) -> dict[str, Any]:
        return await self._post(
            "/lifestyle/v1/lcd/latestbillwaterusage",
            {"wateraccountid": account_id, "channel": "web"},
        )

    async def get_payments(self, account_id: str) -> list[Payment]:
        data = await self._post(
            "/payment/v1/history",
            {
                "accountid": account_id,
                "wateraccountguid": account_id,
                "type": 0,
                "limit": 0,
            },
        )
        return [Payment.from_api(p) for p in data.get("payment_histories") or []]

    async def get_account_data(self, account: WaterAccount) -> AccountData:
        details = await self.get_account_details(account.account_id)
        bills = await self.get_bills(account.account_number)

        household: dict[str, Any] = {}
        try:
            household = await self.get_household_usage(account.account_id)
        except AirSelangorApiError as err:
            _LOGGER.debug("No household usage for %s: %s", account.account_number, err)

        payments: list[Payment] = []
        try:
            payments = await self.get_payments(account.account_id)
        except AirSelangorApiError as err:
            _LOGGER.debug("No payment history for %s: %s", account.account_number, err)

        account.display_name = details.get("displayname") or account.display_name
        account.address = details.get("address") or account.address
        account.status = details.get("status") or account.status

        household_size = household.get("billdatehouseholdnumber") or household.get(
            "householdnumber"
        )
        return AccountData(
            account=account,
            current_balance_rm=_to_float(details.get("currentBalance")),
            outstanding_rm=_to_float(details.get("outstandingamount")),
            overdue_rm=_to_float(details.get("overdueamount")),
            latest_bill_amount_rm=_to_float(details.get("amount")),
            overdue_status=details.get("overduestatus"),
            bill_number=details.get("billnumber"),
            bill_date=_to_date(details.get("billdate")),
            due_date=_to_date(details.get("duedate")),
            last_payment_date=_to_date(details.get("lastpaymentdate")),
            household_size=int(household_size) if household_size else None,
            lcd_target_lpcd=_to_float(household.get("householdconsumption")),
            bills=bills,
            payments=payments,
            raw_details=details,
        )

    async def logout(self) -> None:
        if not self._refresh_token:
            return
        try:
            await self._raw_post(
                "/authentication/v1/logout",
                {"refreshtoken": self._refresh_token},
                True,
            )
        except AirSelangorError:
            pass
        finally:
            self._access_token = None
            self._refresh_token = None
