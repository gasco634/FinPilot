"""Prépare les choix de départ d'un nouvel espace, sans données fictives."""
from sqlalchemy.orm import Session

from .models import Activity, AlertRule, Category, Setting


WORKSPACE_VERSION = 2

# Ces entrées aident à organiser les saisies, mais aucun client ou montant
# n'est créé automatiquement.
DEFAULT_ACTIVITIES = (
    ("Formation en intelligence artificielle", "#1E4DD8"),
    ("Coaching", "#E5322D"),
    ("Montage vidéo", "#315EC8"),
    ("Infographie", "#D8423E"),
    ("Vente d’ordinateur", "#5676CF"),
    ("Autres business", "#7C8DB8"),
)

DEFAULT_INCOME_CATEGORIES = (
    ("Prestation", None),
    ("Formation", None),
    ("Vente", None),
    ("Autre revenu", None),
)

DEFAULT_EXPENSE_CATEGORIES = (
    ("Loyer", "fixed"),
    ("Courant", "variable"),
    ("Wifi", "fixed"),
    ("Eau", "variable"),
    ("Dépense maison", "variable"),
    ("Nourriture", "variable"),
    ("Épargne personnelle", None),
    ("Épargne loyer", None),
    ("Épargne moto", None),
    ("Investissement", "variable"),
    ("Famille", "variable"),
    ("Copine", "variable"),
    ("Essence", "variable"),
)

DEFAULT_ALERT_RULES = (
    ("client_concentration", {"threshold_pct": 40}),
    ("category_spike", {"threshold_pct": 30}),
    ("late_invoice", {}),
    ("cash_forecast", {"threshold_months": 2}),
    ("target_lag", {}),
    ("recurring_review", {"min_monthly_xof": 25_000}),
    ("recurring_increase", {"threshold_pct": 20}),
    ("activity_margin_decline", {"drop_pct": 15, "min_previous_revenue_xof": 100_000}),
    ("activity_opportunity", {"min_revenue_xof": 100_000}),
    ("savings_opportunity", {"min_savings_xof": 10_000}),
)


def initialize_workspace(db: Session, user_id: str) -> None:
    """Ajoute les catégories et réglages initiaux d'un nouvel utilisateur."""
    db.add_all(
        Activity(user_id=user_id, name=name, color=color)
        for name, color in DEFAULT_ACTIVITIES
    )
    db.add_all(
        Category(user_id=user_id, name=name, kind="income", cost_type=cost_type)
        for name, cost_type in DEFAULT_INCOME_CATEGORIES
    )
    db.add_all(
        Category(user_id=user_id, name=name, kind="expense", cost_type=cost_type)
        for name, cost_type in DEFAULT_EXPENSE_CATEGORIES
    )
    db.add_all(
        AlertRule(user_id=user_id, rule_type=rule_type, parameters=parameters, is_active=True)
        for rule_type, parameters in DEFAULT_ALERT_RULES
    )
    db.add_all(
        [
            Setting(
                user_id=user_id,
                key="preferences",
                value={
                    "currency": "XOF",
                    "fx_rate": 1,
                    "locale": "fr-FR",
                    "theme": "light",
                    "monthly_target_xof": 0,
                    "annual_target_xof": 0,
                    "business_name": "Jérémie GASBEOGO",
                    "legal_mentions": "",
                },
            ),
            Setting(
                user_id=user_id,
                key="workspace_seed_version",
                value={"version": WORKSPACE_VERSION},
            ),
        ]
    )
