from datetime import date, datetime
import math
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RegisterIn(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str):
        value = value.strip().lower()
        if "@" not in value:
            raise ValueError("Adresse e-mail invalide")
        return value

    @field_validator("password")
    @classmethod
    def bcrypt_length_limit(cls, value: str):
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Le mot de passe ne doit pas dépasser 72 octets UTF-8")
        return value


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ActivityIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str = Field(default="#1E4DD8", pattern=r"^#[0-9A-Fa-f]{6}$")


class ClientIn(BaseModel):
    name: str = Field(default="", max_length=160)
    first_name: str | None = Field(default=None, max_length=80)
    last_name: str | None = Field(default=None, max_length=80)
    email: str | None = None
    phone: str | None = None
    payment_terms_days: int = Field(default=30, ge=0, le=365)
    reliability_score: int | None = Field(default=None, ge=1, le=5)
    notes: str = ""

    @model_validator(mode="after")
    def build_client_name(self):
        first_name = (self.first_name or "").strip()
        last_name = (self.last_name or "").strip()
        if first_name or last_name:
            self.first_name = first_name or None
            self.last_name = last_name or None
            self.name = " ".join(part for part in (first_name, last_name) if part)
        else:
            self.name = self.name.strip()
            if not self.name:
                raise ValueError("Saisissez le nom du client ou son prénom et son nom.")
        return self


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: str = Field(pattern="^(income|expense)$")
    cost_type: str | None = Field(default=None, pattern="^(fixed|variable|direct)$")


class TransactionIn(BaseModel):
    kind: str = Field(pattern="^(income|expense)$")
    income_type: str | None = Field(default=None, pattern="^(prestation|formation|vente|autre)$")
    amount_xof: int = Field(gt=0, le=9_000_000_000_000)
    transaction_date: date
    due_date: date | None = None
    status: str = Field(default="received", pattern="^(received|pending|overdue)$")
    payment_method: str | None = Field(default=None, pattern="^(orange_money|moov_money|coris|bank_transfer|cash|other)$")
    activity_id: str | None = None
    client_id: str | None = None
    category_id: str | None = None
    description: str = Field(default="", max_length=240)
    reference: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def income_type_only_for_income(self):
        if self.kind == "expense" and self.income_type is not None:
            raise ValueError("Le type de revenu ne s’applique qu’aux revenus.")
        return self


class QuoteItemIn(BaseModel):
    designation: str = Field(min_length=1, max_length=240)
    quantity: float = Field(default=1, gt=0, le=100000)
    unit_price_xof: int = Field(ge=0, le=9_000_000_000_000)
    discount_xof: int = Field(default=0, ge=0)
    tax_rate: float = Field(default=0, ge=0, le=100)

    @model_validator(mode="after")
    def discount_does_not_exceed_line(self):
        if self.discount_xof > round(self.quantity * self.unit_price_xof):
            raise ValueError("La remise ne peut pas dépasser le montant de la ligne")
        return self


class QuoteIn(BaseModel):
    client_id: str
    activity_id: str | None = None
    issue_date: date
    valid_until: date
    notes: str = ""
    items: list[QuoteItemIn] = Field(min_length=1, max_length=100)


class PaymentIn(BaseModel):
    amount_xof: int = Field(gt=0, le=9_000_000_000_000)
    paid_at: date
    payment_method: str = Field(pattern="^(orange_money|moov_money|coris|bank_transfer|cash|other)$")


class BudgetIn(BaseModel):
    category_id: str
    activity_id: str | None = None
    period_start: date
    period_end: date
    amount_xof: int = Field(gt=0)


class AlertRuleIn(BaseModel):
    rule_type: str = Field(pattern="^(client_concentration|category_spike|late_invoice|cash_forecast|target_lag|recurring_review|recurring_increase|activity_margin_decline|activity_opportunity|savings_opportunity)$")
    parameters: dict = Field(default_factory=dict)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_thresholds(self):
        keys = {
            "client_concentration": {"threshold_pct": (0, 100)},
            "category_spike": {"threshold_pct": (0, 1000)},
            "cash_forecast": {"threshold_months": (1, 60)},
            "recurring_review": {"min_monthly_xof": (0, 9_000_000_000_000)},
            "recurring_increase": {"threshold_pct": (0, 1000)},
            "activity_margin_decline": {"drop_pct": (0, 100), "min_previous_revenue_xof": (0, 9_000_000_000_000)},
            "activity_opportunity": {"min_revenue_xof": (0, 9_000_000_000_000)},
            "savings_opportunity": {"min_savings_xof": (0, 9_000_000_000_000)},
        }.get(self.rule_type, {})
        for key, (minimum, maximum) in keys.items():
            if key not in self.parameters:
                continue
            value = self.parameters[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
                raise ValueError(f"Seuil invalide pour {key}")
        return self


class SettingsIn(BaseModel):
    currency: str = "XOF"
    fx_rate: float = Field(default=1, gt=0, le=1_000_000)
    locale: str = "fr-FR"
    theme: str = Field(default="light", pattern="^(light|dark)$")
    monthly_target_xof: int = Field(default=0, ge=0)
    annual_target_xof: int = Field(default=0, ge=0)
    business_name: str = "Jérémie GASBEOGO"
    legal_mentions: str = ""


class AlertStatusIn(BaseModel):
    status: str = Field(pattern="^(active|acknowledged|resolved)$")


class WorkSessionIn(BaseModel):
    activity_id: str | None = None
    client_id: str | None = None
    service_type: str = Field(default="", max_length=120)
    started_at: datetime
    hours: float = Field(gt=0, le=1000)
    revenue_xof: int = Field(default=0, ge=0, le=9_000_000_000_000)


class RecurringRuleIn(BaseModel):
    activity_id: str | None = None
    category_id: str | None = None
    kind: str = Field(pattern="^(income|expense)$")
    description: str = Field(min_length=1, max_length=240)
    amount_xof: int = Field(gt=0, le=9_000_000_000_000)
    frequency: str = Field(pattern="^(weekly|monthly|quarterly|yearly)$")
    next_run: date
    is_active: bool = True

