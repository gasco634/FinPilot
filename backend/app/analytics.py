from collections import defaultdict
from datetime import date, timedelta
from statistics import mean
import pandas as pd


def _amount(row):
    if isinstance(row, dict):
        return int(row.get("amount_xof", row.get("total_xof", 0)))
    return int(getattr(row, "amount_xof", getattr(row, "total_xof", 0)))


def _get(row, key, default=None):
    return row.get(key, default) if isinstance(row, dict) else getattr(row, key, default)


def calculate_kpis(transactions, invoices=(), payments=(), quotes=(), categories=(), start=None, end=None, previous_start=None, previous_end=None, cash_balance=0):
    """Stable KPI definitions: transaction-based cash, invoice-based billings and receivables."""
    def in_range(value, left, right):
        return value is not None and (left is None or value >= left) and (right is None or value <= right)

    current = [t for t in transactions if in_range(_get(t, "transaction_date"), start, end)]
    previous = [t for t in transactions if in_range(_get(t, "transaction_date"), previous_start, previous_end)] if previous_start else []
    settled = [t for t in current if _get(t, "status") == "received"]
    income = sum(_amount(t) for t in settled if _get(t, "kind") == "income")
    expenses = sum(_amount(t) for t in settled if _get(t, "kind") == "expense")
    profit = income - expenses
    previous_income = sum(_amount(t) for t in previous if _get(t, "status") == "received" and _get(t, "kind") == "income")
    previous_expenses = sum(_amount(t) for t in previous if _get(t, "status") == "received" and _get(t, "kind") == "expense")
    previous_profit = previous_income - previous_expenses

    relevant_invoices = [i for i in invoices if _get(i, "status") not in ("cancelled", "draft")]
    billed = sum(_amount(i) for i in relevant_invoices if in_range(_get(i, "issue_date"), start, end))
    period_quotes = [q for q in quotes if _get(q, "status") != "draft"
                     and in_range(_get(q, "issue_date"), start, end)]
    quote_rows = [_get(q, "status") for q in period_quotes]
    accepted_quotes = sum(status == "accepted" for status in quote_rows)
    conversion = round(100 * accepted_quotes / len(quote_rows), 1) if quote_rows else 0
    acceptance_days = [(_get(q, "accepted_at") - _get(q, "issue_date")).days for q in period_quotes
                       if _get(q, "status") == "accepted" and _get(q, "accepted_at")
                       and _get(q, "accepted_at") >= _get(q, "issue_date")]
    average_acceptance_days = round(mean(acceptance_days), 1) if acceptance_days else None
    invoice_paid = defaultdict(int)
    invoice_dates = {str(_get(i, "id")): _get(i, "issue_date") for i in relevant_invoices}
    for p in payments:
        invoice_paid[str(_get(p, "invoice_id"))] += _amount(p)
    receivables = sum(max(0, _amount(i) - invoice_paid[str(_get(i, "id"))]) for i in relevant_invoices)
    overdue = sum(max(0, _amount(i) - invoice_paid[str(_get(i, "id"))]) for i in relevant_invoices if _get(i, "due_date") and _get(i, "due_date") < date.today())
    period_payments = [p for p in payments if in_range(_get(p, "paid_at"), start, end)]
    paid_in_period = sum(_amount(p) for p in period_payments)
    collection_rate = round(100 * paid_in_period / billed, 1) if billed else 0
    dso_pairs = []
    for p in period_payments:
        issue = invoice_dates.get(str(_get(p, "invoice_id")))
        paid_at = _get(p, "paid_at")
        if issue and paid_at and paid_at >= issue:
            dso_pairs.append((max(0, (paid_at - issue).days), _amount(p)))
    dso = round(sum(days * amount for days, amount in dso_pairs) / sum(amount for _, amount in dso_pairs), 1) if dso_pairs else 0

    revenue_by_client = defaultdict(int)
    revenue_by_activity = defaultdict(int)
    expense_by_activity = defaultdict(int)
    for t in settled:
        if _get(t, "kind") == "income":
            revenue_by_client[_get(t, "client_id") or "Sans client"] += _amount(t)
            revenue_by_activity[_get(t, "activity_id") or "Non affecté"] += _amount(t)
        elif _get(t, "kind") == "expense":
            expense_by_activity[_get(t, "activity_id") or "Non affecté"] += _amount(t)
    top_client = max(revenue_by_client.values(), default=0)
    concentration = round(100 * top_client / income, 1) if income else 0
    hhi = round(sum((100 * amount / income) ** 2 for amount in revenue_by_client.values()), 1) if income else 0
    activity_ids = set(revenue_by_activity) | set(expense_by_activity)
    activity_rows = [{"activity_id": activity, "revenue_xof": revenue_by_activity[activity],
                      "expenses_xof": expense_by_activity[activity],
                      "profit_xof": revenue_by_activity[activity] - expense_by_activity[activity]}
                     for activity in activity_ids]
    activity_rows.sort(key=lambda item: item["revenue_xof"], reverse=True)

    previous_months = []
    if end:
        series_end = min(end, date.today()) if start and start <= date.today() else end
        frame = pd.DataFrame([{"month": _get(t, "transaction_date").strftime("%Y-%m"), "kind": _get(t, "kind"), "amount_xof": _amount(t)} for t in transactions if _get(t, "status") == "received" and _get(t, "transaction_date") <= series_end])
        grouped = frame.groupby(["month", "kind"], as_index=False)["amount_xof"].sum() if not frame.empty else pd.DataFrame(columns=["month", "kind", "amount_xof"])
        for offset in range(5, -1, -1):
            anchor = series_end.replace(day=1)
            month = (anchor.month - offset - 1) % 12 + 1
            year = anchor.year + (anchor.month - offset - 1) // 12
            left = date(year, month, 1)
            key = left.strftime("%Y-%m")
            row = grouped[grouped["month"] == key]
            values = dict(zip(row["kind"], row["amount_xof"]))
            previous_months.append({"month": key, "income_xof": int(values.get("income", 0)), "expenses_xof": int(values.get("expense", 0))})

    growth = round(100 * (income - previous_income) / previous_income, 1) if previous_income else None
    year_ago_start = year_ago_end = None
    if start and end:
        try:
            year_ago_start = start.replace(year=start.year - 1)
            year_ago_end = end.replace(year=end.year - 1)
        except ValueError:
            year_ago_start = start.replace(year=start.year - 1, day=min(start.day, 28))
            year_ago_end = end.replace(year=end.year - 1, day=min(end.day, 28))
    year_ago_income = sum(_amount(t) for t in transactions if _get(t, "status") == "received" and _get(t, "kind") == "income" and in_range(_get(t, "transaction_date"), year_ago_start, year_ago_end)) if year_ago_start else 0
    growth_yoy = round(100 * (income - year_ago_income) / year_ago_income, 1) if year_ago_income else None
    avg_basket = round(income / max(1, sum(1 for t in settled if _get(t, "kind") == "income")))
    burn_rate = round(sum(row["expenses_xof"] for row in previous_months[-3:]) / 3)
    margin = round(100 * profit / income, 1) if income else 0
    savings = round(100 * profit / income, 1) if income else 0
    total_fixed = total_variable = direct_costs = 0
    category_types = {_get(c, "id"): _get(c, "cost_type") for c in categories}
    for t in settled:
        if _get(t, "kind") == "expense":
            if category_types.get(_get(t, "category_id")) == "fixed":
                total_fixed += _amount(t)
            else:
                total_variable += _amount(t)
            if category_types.get(_get(t, "category_id")) == "direct": direct_costs += _amount(t)
    contribution = (income - total_variable) / income if income else 0
    break_even = round(total_fixed / contribution) if contribution > 0 else 0
    return {
        "revenue_xof": income, "expenses_xof": expenses, "net_profit_xof": profit,
        "gross_profit_xof": income - direct_costs, "gross_margin_pct": round(100 * (income-direct_costs) / income, 1) if income else 0,
        "net_margin_pct": margin, "cash_balance_xof": cash_balance,
        "receivables_xof": receivables, "overdue_xof": overdue, "savings_rate_pct": savings,
        "billed_revenue_xof": billed, "collection_rate_pct": collection_rate, "dso_days": dso,
        "quote_conversion_pct": conversion, "quote_acceptance_days": average_acceptance_days,
        "average_basket_xof": avg_basket,
        "client_concentration_pct": concentration, "client_hhi": hhi,
        "growth_mom_pct": growth, "growth_yoy_pct": growth_yoy,
        "burn_rate_monthly_xof": burn_rate, "runway_months": round(cash_balance / burn_rate, 1) if burn_rate else None,
        "break_even_xof": break_even, "top_clients": sorted([{"client_id": k, "revenue_xof": v} for k, v in revenue_by_client.items()], key=lambda x: x["revenue_xof"], reverse=True)[:5],
        "activities": activity_rows, "monthly": previous_months,
        "changes": {"revenue_pct": round(100 * (income - previous_income) / previous_income, 1) if previous_income else None,
                    "expenses_pct": round(100 * (expenses - previous_expenses) / previous_expenses, 1) if previous_expenses else None,
                    "profit_pct": round(100 * (profit - previous_profit) / abs(previous_profit), 1) if previous_profit else None},
    }


def forecast_cash(monthly_history, cash_balance, months=3, scenario="realistic"):
    """Three-month moving average with a bounded same-month seasonal adjustment."""
    factor = {"optimistic": 1.15, "realistic": 1.0, "pessimistic": 0.8}.get(scenario)
    if factor is None:
        raise ValueError("Scénario inconnu")
    completed_history = [row for row in monthly_history if not row.get("partial")]
    if not completed_history:
        completed_history = monthly_history
    if not completed_history:
        avg_in, avg_out = 0, 0
    else:
        recent = completed_history[-3:]
        avg_in = mean(row.get("income_xof", 0) for row in recent)
        avg_out = mean(row.get("expenses_xof", 0) for row in recent)
    seasonal_history = completed_history[-12:]
    seasonal_means = {
        key: mean(row.get(key, 0) for row in seasonal_history)
        for key in ("income_xof", "expenses_xof")
    }
    month_index = None
    if monthly_history:
        try:
            last_month = date.fromisoformat(f"{monthly_history[-1]['month']}-01")
            month_index = last_month.year * 12 + last_month.month - 1
        except (KeyError, TypeError, ValueError):
            month_index = None

    def seasonal_factor(key, future_index):
        if month_index is None or len(seasonal_history) < 12:
            return 1.0
        year, month_zero = divmod(future_index, 12)
        prior_year_month = f"{year - 1:04d}-{month_zero + 1:02d}"
        prior_year_value = next((row.get(key, 0) for row in seasonal_history
                                 if row.get("month") == prior_year_month), None)
        average = seasonal_means[key]
        if prior_year_value is None or average <= 0:
            return 1.0
        seasonal_index = max(0.5, min(1.5, prior_year_value / average))
        return 0.5 + 0.5 * seasonal_index

    balance = cash_balance
    output = []
    for idx in range(1, months + 1):
        future_index = month_index + idx if month_index is not None else None
        inflow_season = seasonal_factor("income_xof", future_index) if future_index is not None else 1.0
        outflow_season = seasonal_factor("expenses_xof", future_index) if future_index is not None else 1.0
        inflow = round(avg_in * factor * inflow_season)
        outflow = round(avg_out * (2 - factor) * outflow_season)
        balance += inflow - outflow
        output.append({"month_offset": idx, "income_xof": inflow, "expenses_xof": outflow, "cash_balance_xof": balance})
    return output


def _month_start(value: date, offset: int = 0) -> date:
    month_index = value.year * 12 + value.month - 1 - offset
    year, month_zero = divmod(month_index, 12)
    return date(year, month_zero + 1, 1)


def _monthly_equivalent(amount: int, frequency: str) -> int:
    factor = {"weekly": 52 / 12, "monthly": 1, "quarterly": 1 / 3, "yearly": 1 / 12}.get(frequency, 1)
    return round(amount * factor)


def evaluate_alerts(transactions, invoices, payments, kpis, rules=(), target_monthly=0, today=None,
                    recurring_rules=(), activity_names=None):
    """Return actionable, explainable alerts; monetary estimates are explicitly heuristic."""
    today = today or date.today()
    activity_names = activity_names or {}
    alerts = []
    active_rules = [r for r in rules if _get(r, "is_active", True)]
    configured_types = {_get(r, "rule_type") for r in active_rules}
    if not rules:
        configured_types = {
            "late_invoice", "client_concentration", "category_spike", "target_lag", "cash_forecast",
            "recurring_review", "recurring_increase", "activity_margin_decline", "activity_opportunity",
            "savings_opportunity",
        }
    params_by_type = {_get(r, "rule_type"): (_get(r, "parameters", {}) or {}) for r in active_rules}

    if "late_invoice" in configured_types:
        for invoice in invoices:
            due_date = _get(invoice, "due_date")
            if _get(invoice, "status") in ("paid", "cancelled", "draft") or not due_date or due_date >= today:
                continue
            paid = sum(_amount(p) for p in payments if str(_get(p, "invoice_id")) == str(_get(invoice, "id")))
            balance = max(0, _amount(invoice) - paid)
            if balance:
                alerts.append({"severity": "high", "rule_type": "late_invoice", "dedupe_key": f"late:{_get(invoice, 'id')}:{today:%Y-%m}",
                               "title": f"Facture {_get(invoice, 'number')} en retard",
                               "explanation": f"{balance:,} FCFA restent dus depuis le {due_date}.",
                               "recommendation": "Relancer le client et confirmer la date de règlement.",
                               "details": {"invoice_id": _get(invoice, "id"), "balance_xof": balance}})

    limit = float(params_by_type.get("client_concentration", {}).get("threshold_pct", 40))
    concentration = float(kpis.get("client_concentration_pct", 0))
    if "client_concentration" in configured_types and concentration > limit:
        alerts.append({"severity": "medium", "rule_type": "client_concentration", "dedupe_key": f"client-concentration:{today:%Y-%m}",
                       "title": "Dépendance à un client",
                       "explanation": f"Le premier client représente {concentration:g} % des encaissements.",
                       "recommendation": "Diversifier le portefeuille et renforcer la prospection.",
                       "details": {"share_pct": concentration, "threshold_pct": limit}})

    actual_revenue = float(kpis.get("revenue_xof", 0))
    if "target_lag" in configured_types and target_monthly and actual_revenue < target_monthly * 0.5 and today.day > 20:
        alerts.append({"severity": "medium", "rule_type": "target_lag", "dedupe_key": f"target:{today:%Y-%m}",
                       "title": "Objectif mensuel en retard",
                       "explanation": f"{actual_revenue:,.0f} FCFA encaissés sur un objectif de {target_monthly:,.0f} FCFA.",
                       "recommendation": "Accélérer les relances et concentrer les efforts sur les offres les plus rentables.",
                       "details": {"target_xof": target_monthly, "actual_xof": actual_revenue}})

    category_spikes = []
    for rule in active_rules:
        rule_type = _get(rule, "rule_type")
        parameters = _get(rule, "parameters", {}) or {}
        if rule_type == "category_spike":
            threshold = float(parameters.get("threshold_pct", 25))
            by_category = defaultdict(lambda: defaultdict(int))
            for transaction in transactions:
                transaction_date = _get(transaction, "transaction_date")
                if (_get(transaction, "kind") == "expense" and _get(transaction, "status") == "received"
                        and transaction_date is not None):
                    by_category[_get(transaction, "category_id")][transaction_date.strftime("%Y-%m")] += _amount(transaction)
            for category, values in by_category.items():
                months = sorted(values)
                current_month = months[-1]
                current = values[current_month]
                current_date = date.fromisoformat(f"{current_month}-01")
                previous_months = [_month_start(current_date, offset).strftime("%Y-%m") for offset in (1, 2, 3)]
                baseline = mean(values.get(month, 0) for month in previous_months)
                if baseline and current > baseline * (1 + threshold / 100):
                    savings = max(0, round(current - baseline))
                    category_spikes.append(savings)
                    alerts.append({"severity": "medium", "rule_type": "category_spike", "dedupe_key": f"spike:{category}:{current_month}",
                                   "title": "Dépenses en hausse",
                                   "explanation": f"Cette catégorie atteint {current:,} FCFA, soit {round(100 * (current / baseline - 1))} % au-dessus de sa moyenne des trois derniers mois ({round(baseline):,} FCFA).",
                                   "recommendation": "Vérifier les achats et ajuster le budget si la hausse est durable.",
                                   "details": {"category_id": category, "current_xof": current, "baseline_xof": round(baseline),
                                               "potential_savings_monthly_xof": savings, "threshold_pct": threshold}})

    if "cash_forecast" in configured_types:
        cash = float(kpis.get("cash_balance_xof", 0))
        burn = float(kpis.get("burn_rate_monthly_xof", 0))
        threshold_months = float(params_by_type.get("cash_forecast", {}).get("threshold_months", 2))
        projected = cash - burn * threshold_months
        if burn and projected < 0:
            alerts.append({"severity": "high", "rule_type": "cash_forecast", "dedupe_key": f"cash-runway:{today:%Y-%m}",
                           "title": "Risque de tension de trésorerie",
                           "explanation": f"Au rythme actuel, la trésorerie pourrait atteindre {round(projected):,} FCFA sous {threshold_months:g} mois.",
                           "recommendation": "Accélérer les encaissements, reporter les sorties non essentielles et actualiser le prévisionnel.",
                           "details": {"cash_balance_xof": cash, "burn_rate_xof": burn, "horizon_months": threshold_months, "projected_xof": round(projected)}})

    if "recurring_review" in configured_types or "recurring_increase" in configured_types:
        for recurring in recurring_rules:
            if not _get(recurring, "is_active", True) or _get(recurring, "kind") != "expense":
                continue
            recurring_id = _get(recurring, "id")
            frequency = _get(recurring, "frequency", "monthly")
            amount = _amount(recurring)
            monthly_amount = _monthly_equivalent(amount, frequency)
            if "recurring_review" in configured_types:
                minimum = int(params_by_type.get("recurring_review", {}).get("min_monthly_xof", 25_000))
                if monthly_amount >= minimum:
                    alerts.append({"severity": "low", "rule_type": "recurring_review", "dedupe_key": f"recurring-review:{recurring_id}:{today:%Y-%m}",
                                   "title": f"Charge récurrente à confirmer : {_get(recurring, 'description')}",
                                   "explanation": f"Cette dépense représente environ {monthly_amount:,} FCFA par mois ({monthly_amount * 12:,} FCFA par an). FinPilot ne mesure pas son usage.",
                                   "recommendation": "Vérifier qu’elle reste utile et comparer les offres avant le prochain renouvellement.",
                                   "details": {"recurring_rule_id": recurring_id, "monthly_amount_xof": monthly_amount,
                                               "annual_amount_xof": monthly_amount * 12, "minimum_monthly_xof": minimum}})
            if "recurring_increase" in configured_types and recurring_id:
                previous_runs = [t for t in transactions
                                 if str(_get(t, "reference", "")).startswith(f"recurring:{recurring_id}:")
                                 and _get(t, "transaction_date") is not None]
                if previous_runs:
                    previous_amount = _amount(max(previous_runs, key=lambda row: _get(row, "transaction_date")))
                    increase_pct = float(params_by_type.get("recurring_increase", {}).get("threshold_pct", 20))
                    if previous_amount > 0 and amount > previous_amount * (1 + increase_pct / 100):
                        previous_monthly = _monthly_equivalent(previous_amount, frequency)
                        alerts.append({"severity": "medium", "rule_type": "recurring_increase", "dedupe_key": f"recurring-increase:{recurring_id}:{today:%Y-%m}",
                                       "title": f"Hausse d’une charge récurrente : {_get(recurring, 'description')}",
                                       "explanation": f"Le montant est passé de {previous_monthly:,} à {monthly_amount:,} FCFA par mois ({round(100 * (amount / previous_amount - 1))} % de hausse).",
                                       "recommendation": "Vérifier le nouveau tarif et demander une offre moins chère si le service reste nécessaire.",
                                       "details": {"recurring_rule_id": recurring_id, "previous_monthly_xof": previous_monthly,
                                                   "current_monthly_xof": monthly_amount, "increase_pct": round(100 * (amount / previous_amount - 1), 1)}})

    if "activity_margin_decline" in configured_types:
        previous_start = _month_start(today, 1)
        current_start = _month_start(today)
        by_activity_month = defaultdict(lambda: defaultdict(lambda: {"income": 0, "expense": 0}))
        for transaction in transactions:
            transaction_date = _get(transaction, "transaction_date")
            if _get(transaction, "status") != "received" or transaction_date is None:
                continue
            if not (previous_start <= transaction_date <= today):
                continue
            activity_id = _get(transaction, "activity_id") or "unassigned"
            month_key = "current" if transaction_date >= current_start else "previous"
            kind_key = "income" if _get(transaction, "kind") == "income" else "expense"
            by_activity_month[activity_id][month_key][kind_key] += _amount(transaction)
        drop_points = float(params_by_type.get("activity_margin_decline", {}).get("drop_pct", 15))
        minimum_revenue = int(params_by_type.get("activity_margin_decline", {}).get("min_previous_revenue_xof", 100_000))
        for activity_id, periods in by_activity_month.items():
            previous = periods["previous"]
            current = periods["current"]
            if previous["income"] < minimum_revenue:
                continue
            previous_margin = 100 * (previous["income"] - previous["expense"]) / previous["income"]
            current_margin = 100 * (current["income"] - current["expense"]) / current["income"] if current["income"] else 0
            decline = previous_margin - current_margin
            if decline >= drop_points:
                name = activity_names.get(activity_id, "Activité non affectée" if activity_id == "unassigned" else "Activité")
                alerts.append({"severity": "medium", "rule_type": "activity_margin_decline", "dedupe_key": f"activity-margin:{activity_id}:{today:%Y-%m}",
                               "title": f"Marge en baisse : {name}",
                               "explanation": f"La marge de l’activité est passée de {previous_margin:.1f} % le mois dernier à {current_margin:.1f} % ce mois-ci.",
                               "recommendation": "Revoir le temps passé, les coûts affectés et les prix des prestations de cette activité.",
                               "details": {"activity_id": activity_id, "previous_margin_pct": round(previous_margin, 1),
                                           "current_margin_pct": round(current_margin, 1), "drop_points": round(decline, 1),
                                           "threshold_points": drop_points, "current_revenue_xof": current["income"],
                                           "current_expenses_xof": current["expense"]}})

    if "activity_opportunity" in configured_types:
        window_start = _month_start(today, 2)
        by_activity = defaultdict(lambda: {"income": 0, "expense": 0})
        for transaction in transactions:
            transaction_date = _get(transaction, "transaction_date")
            activity_id = _get(transaction, "activity_id")
            if activity_id and window_start <= transaction_date <= today and _get(transaction, "status") == "received":
                by_activity[activity_id]["income" if _get(transaction, "kind") == "income" else "expense"] += _amount(transaction)
        minimum_revenue = int(params_by_type.get("activity_opportunity", {}).get("min_revenue_xof", 100_000))
        opportunities = []
        for activity_id, values in by_activity.items():
            revenue = values["income"]
            profit = revenue - values["expense"]
            if revenue >= minimum_revenue and profit > 0:
                opportunities.append((profit / revenue, profit, activity_id, revenue, values["expense"]))
        if opportunities:
            margin, profit, activity_id, revenue, expense = max(opportunities)
            name = activity_names.get(activity_id, "Activité")
            alerts.append({"severity": "low", "rule_type": "activity_opportunity", "dedupe_key": f"activity-opportunity:{today:%Y-%m}",
                           "title": f"Piste de développement : {name}",
                           "explanation": f"Sur les trois derniers mois, cette activité a généré {profit:,} FCFA de résultat pour {revenue:,} FCFA encaissés ({round(margin * 100, 1)} % de marge).",
                           "recommendation": "Tester une hausse de capacité ou de prospection sur cette activité, puis comparer les résultats le mois prochain.",
                           "details": {"activity_id": activity_id, "revenue_xof": revenue, "expenses_xof": expense,
                                       "profit_xof": profit, "margin_pct": round(margin * 100, 1)}})

    if "savings_opportunity" in configured_types:
        potential_savings = sum(category_spikes)
        minimum = int(params_by_type.get("savings_opportunity", {}).get("min_savings_xof", 10_000))
        if potential_savings >= minimum:
            alerts.append({"severity": "low", "rule_type": "savings_opportunity", "dedupe_key": f"savings-opportunity:{today:%Y-%m}",
                           "title": "Économies potentielles repérées",
                           "explanation": f"Jusqu’à {potential_savings:,} FCFA d’économies ce mois-ci si les catégories en hausse reviennent à leur moyenne récente.",
                           "recommendation": "Inspecter les dépenses concernées et valider les économies possibles avant de modifier les achats.",
                           "details": {"potential_savings_monthly_xof": potential_savings, "minimum_savings_xof": minimum,
                                       "estimate_method": "Dépenses du dernier mois au-dessus de la moyenne des trois mois précédents."}})

    return alerts
