from datetime import date
import pytest
from app.analytics import calculate_kpis, evaluate_alerts, forecast_cash


def test_cash_kpis_keep_unpaid_items_out_of_encaissements():
    txs = [
        {"id": "t1", "kind": "income", "status": "received", "amount_xof": 600000, "transaction_date": date(2026, 3, 10), "client_id": "c1", "activity_id": "a1", "category_id": "income"},
        {"id": "t2", "kind": "expense", "status": "received", "amount_xof": 200000, "transaction_date": date(2026, 3, 11), "client_id": None, "activity_id": "a1", "category_id": "fixed"},
        {"id": "t3", "kind": "income", "status": "pending", "amount_xof": 900000, "transaction_date": date(2026, 3, 12), "client_id": "c2", "activity_id": "a2", "category_id": "income"},
    ]
    invoices = [{"id": "i1", "status": "issued", "issue_date": date(2026, 3, 5), "due_date": date(2026, 4, 5), "total_xof": 1000000}]
    payments = [{"invoice_id": "i1", "amount_xof": 250000, "paid_at": date(2026, 3, 20)}]
    kpi = calculate_kpis(txs, invoices, payments, start=date(2026,3,1), end=date(2026,3,31), cash_balance=400000)
    assert kpi["revenue_xof"] == 600000
    assert kpi["expenses_xof"] == 200000
    assert kpi["net_profit_xof"] == 400000
    assert kpi["billed_revenue_xof"] == 1000000
    assert kpi["receivables_xof"] == 750000
    assert kpi["cash_balance_xof"] == 400000


def test_forecast_scenarios_move_cash_in_expected_direction():
    history = [{"income_xof": 1000000, "expenses_xof": 600000}] * 3
    optimistic = forecast_cash(history, 500000, scenario="optimistic")
    realistic = forecast_cash(history, 500000, scenario="realistic")
    pessimistic = forecast_cash(history, 500000, scenario="pessimistic")
    assert optimistic[-1]["cash_balance_xof"] > realistic[-1]["cash_balance_xof"] > pessimistic[-1]["cash_balance_xof"]
    with pytest.raises(ValueError): forecast_cash(history, 0, scenario="unknown")


def test_forecast_uses_bounded_same_month_seasonality_after_one_year():
    history = [{"month": date(2025, month, 1).strftime("%Y-%m"),
                "income_xof": 200000 if month == 1 else 100000,
                "expenses_xof": 100000 if month == 1 else 40000}
               for month in range(1, 13)]
    forecast = forecast_cash(history, 0, months=3, scenario="realistic")
    assert forecast[0]["income_xof"] == 125000
    assert forecast[0]["expenses_xof"] == 50000


def test_forecast_ignores_incomplete_current_month_for_moving_average():
    history = [
        {"month":"2026-07", "income_xof":100000, "expenses_xof":40000},
        {"month":"2026-08", "income_xof":120000, "expenses_xof":50000},
        {"month":"2026-09", "income_xof":110000, "expenses_xof":45000},
        {"month":"2026-10", "income_xof":10000, "expenses_xof":5000, "partial":True},
    ]
    forecast = forecast_cash(history, 250000, months=1, scenario="realistic")
    assert forecast[0]["income_xof"] == 110000
    assert forecast[0]["expenses_xof"] == 45000


def test_alert_rules_flag_overdue_invoice_and_high_client_concentration():
    invoices = [{"id": "inv-1", "number": "FAC-2026-001", "status": "issued", "due_date": date(2026, 1, 1), "total_xof": 500000}]
    kpis = {"client_concentration_pct": 58.2, "revenue_xof": 900000}
    alerts = evaluate_alerts([], invoices, [], kpis, [
        {"rule_type": "client_concentration", "is_active": True, "parameters": {"threshold_pct": 40}},
        {"rule_type": "late_invoice", "is_active": True, "parameters": {}},
    ], today=date(2026, 2, 1))
    assert {a["rule_type"] for a in alerts} == {"late_invoice", "client_concentration"}
    assert alerts[0]["details"].get("balance_xof") == 500000


def test_documented_kpi_formulas_use_period_and_prior_comparators():
    txs = [
        {"kind":"income","status":"received","amount_xof":800000,"transaction_date":date(2026,3,8),"client_id":"c1","activity_id":"a1","category_id":"sales"},
        {"kind":"income","status":"received","amount_xof":200000,"transaction_date":date(2026,3,18),"client_id":"c2","activity_id":"a2","category_id":"sales"},
        {"kind":"expense","status":"received","amount_xof":200000,"transaction_date":date(2026,3,15),"client_id":None,"activity_id":"a1","category_id":"direct"},
        {"kind":"expense","status":"received","amount_xof":100000,"transaction_date":date(2026,3,19),"client_id":None,"activity_id":"a1","category_id":"fixed"},
        {"kind":"income","status":"received","amount_xof":500000,"transaction_date":date(2026,2,12),"client_id":"c1","activity_id":"a1","category_id":"sales"},
        {"kind":"expense","status":"received","amount_xof":80000,"transaction_date":date(2026,1,12),"client_id":None,"activity_id":"a1","category_id":"fixed"},
        {"kind":"expense","status":"received","amount_xof":100000,"transaction_date":date(2026,2,12),"client_id":None,"activity_id":"a1","category_id":"fixed"},
        {"kind":"income","status":"received","amount_xof":250000,"transaction_date":date(2025,3,8),"client_id":"c1","activity_id":"a1","category_id":"sales"},
    ]
    invoices=[{"id":"i1","status":"issued","issue_date":date(2026,3,2),"due_date":date(2026,4,2),"total_xof":500000}]
    payments=[{"invoice_id":"i1","amount_xof":200000,"paid_at":date(2026,3,12)}]
    quotes=[{"status":"accepted","issue_date":date(2026,3,1),"accepted_at":date(2026,3,3)},
            {"status":"sent","issue_date":date(2026,3,15)},
            {"status":"draft","issue_date":date(2026,3,20)}]
    categories=[{"id":"fixed","cost_type":"fixed"},{"id":"direct","cost_type":"direct"}]
    k=calculate_kpis(txs,invoices,payments,quotes,categories,date(2026,3,1),date(2026,3,31),date(2026,2,1),date(2026,2,28),2_000_000)
    assert k["gross_profit_xof"] == 800000
    assert k["gross_margin_pct"] == 80
    assert k["net_profit_xof"] == 700000
    assert k["net_margin_pct"] == 70
    assert k["savings_rate_pct"] == 70
    assert k["quote_conversion_pct"] == 50
    assert k["quote_acceptance_days"] == 2
    assert k["dso_days"] == 10
    assert k["collection_rate_pct"] == 40
    assert k["client_concentration_pct"] == 80
    assert k["client_hhi"] == 6800
    assert k["growth_mom_pct"] == 100
    assert k["growth_yoy_pct"] == 300
    assert k["burn_rate_monthly_xof"] == 160000
    assert k["runway_months"] == 12.5
    assert k["break_even_xof"] == 125000
    assert k["average_basket_xof"] == 500000


def test_category_spike_alert_requires_active_rule_and_exceeds_threshold():
    txs=[]
    for month, amount in [(1,100000),(2,110000),(3,90000),(4,150000)]:
        txs.append({"kind":"expense","status":"received","amount_xof":amount,"transaction_date":date(2026,month,12),"category_id":"software"})
    rules=[{"rule_type":"category_spike","is_active":True,"parameters":{"threshold_pct":25}}]
    result=evaluate_alerts(txs,[],[],{},rules,today=date(2026,4,20))
    assert len(result)==1 and result[0]["rule_type"]=="category_spike"
    assert result[0]["details"]["potential_savings_monthly_xof"] == 50000


def test_recurring_charge_review_and_increase_are_explained_in_monthly_terms():
    recurring = [{"id":"rr1", "kind":"expense", "description":"Outil vidéo", "amount_xof":18000,
                  "frequency":"monthly", "is_active":True}]
    transactions = [{"kind":"expense", "status":"pending", "amount_xof":12000,
                    "transaction_date":date(2026,9,1), "reference":"recurring:rr1:2026-09-01"}]
    rules = [
        {"rule_type":"recurring_review", "is_active":True, "parameters":{"min_monthly_xof":10000}},
        {"rule_type":"recurring_increase", "is_active":True, "parameters":{"threshold_pct":20}},
    ]
    alerts = evaluate_alerts(transactions, [], [], {}, rules, today=date(2026,10,22), recurring_rules=recurring)
    by_type = {alert["rule_type"]: alert for alert in alerts}
    assert set(by_type) == {"recurring_review", "recurring_increase"}
    assert by_type["recurring_review"]["details"]["annual_amount_xof"] == 216000
    assert by_type["recurring_increase"]["details"]["increase_pct"] == 50


def test_activity_margin_decline_and_profitable_activity_opportunity():
    transactions = [
        {"kind":"income", "status":"received", "amount_xof":500000, "transaction_date":date(2026,9,10), "activity_id":"a1"},
        {"kind":"expense", "status":"received", "amount_xof":100000, "transaction_date":date(2026,9,12), "activity_id":"a1"},
        {"kind":"income", "status":"received", "amount_xof":500000, "transaction_date":date(2026,10,10), "activity_id":"a1"},
        {"kind":"expense", "status":"received", "amount_xof":400000, "transaction_date":date(2026,10,12), "activity_id":"a1"},
    ]
    rules = [
        {"rule_type":"activity_margin_decline", "is_active":True, "parameters":{"drop_pct":15, "min_previous_revenue_xof":100000}},
        {"rule_type":"activity_opportunity", "is_active":True, "parameters":{"min_revenue_xof":100000}},
    ]
    alerts = evaluate_alerts(transactions, [], [], {}, rules, today=date(2026,10,22), activity_names={"a1":"Coaching IA"})
    by_type = {alert["rule_type"]: alert for alert in alerts}
    assert set(by_type) == {"activity_margin_decline", "activity_opportunity"}
    assert by_type["activity_margin_decline"]["details"]["drop_points"] == 60
    assert by_type["activity_opportunity"]["details"]["profit_xof"] == 500000


def test_savings_opportunity_sums_category_spikes():
    txs=[]
    for month, amount in [(7,100000),(8,110000),(9,90000),(10,150000)]:
        txs.append({"kind":"expense","status":"received","amount_xof":amount,
                    "transaction_date":date(2026,month,12),"category_id":"software"})
    rules=[
        {"rule_type":"category_spike","is_active":True,"parameters":{"threshold_pct":25}},
        {"rule_type":"savings_opportunity","is_active":True,"parameters":{"min_savings_xof":10000}},
    ]
    result=evaluate_alerts(txs,[],[],{},rules,today=date(2026,10,22))
    opportunity=next(alert for alert in result if alert["rule_type"]=="savings_opportunity")
    assert opportunity["details"]["potential_savings_monthly_xof"] == 50000
