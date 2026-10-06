
from app.core.scoring import score_company
from app.core.simulation import run_simulation

fake = {
    "symbol": "BBCA",
    "company_name": "PT Bank Central Asia Tbk.",
    "sector": "Financials",
    "sub_sector": "Banks",
    "last_close_price": 9500.0,
    "daily_close_change": 0.004,
    "market_cap": 1_150_000_000_000_000,
    "pe_ttm": 22.5,
    "pb_mrq": 4.8,
    "52_w_high_price": 10800.0,
    "52_w_low_price": 8200.0,
    "der_mrq": 0.3,
    "dar_mrq": 0.15,
    "roe_ttm": 0.21,
    "roa_ttm": 0.035,
}

stressed = {
    "symbol": "XXXX",
    "company_name": "PT Example Stressed Tbk.",
    "sector": "Energy",
    "sub_sector": "Coal",
    "last_close_price": 184.0,
    "daily_close_change": -0.03,
    "market_cap": 400_000_000_000,
    "pe_ttm": 2.1,
    "pb_mrq": 0.4,
    "52_w_high_price": 620.0,
    "52_w_low_price": 170.0,
    "der_mrq": 2.3,
    "dar_mrq": 0.7,
    "roe_ttm": 0.02,
    "roa_ttm": 0.005,
}


def show(raw):
    r = score_company(raw)
    print(f"\n=== {r.symbol}  {r.company_name} ===")
    print(f"  composite={r.composite:>6}  regime={r.regime:<13} confidence={r.confidence}")
    print(f"  sub-scores: {r.sub_scores.normalized()}")
    sim = run_simulation(
        current_price=r.last_close_price,
        sub_scores_norm=r.sub_scores.normalized(),
        runs=500,
        days=30,
        seed=42,
    )
    print(f"  agent mix:  {sim['agent_mix']}")
    print(f"  bands:      {sim['bands']}")
    print(f"  E[return]={sim['expected_return_pct']}%   P(up)={sim['prob_price_up']}")


if __name__ == "__main__":
    show(fake)
    show(stressed)
    print("\nOK — scoring and simulation ran without the API.")
