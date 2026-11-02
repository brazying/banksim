from decimal import Decimal, ROUND_HALF_UP

def to_cents(value):
    amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    cents = int(amount * 100)
    if cents <= 0:
        raise ValueError("Сумма должна быть больше нуля.")
    return cents

def money(cents):
    return f"{cents / 100:,.2f}".replace(",", " ") + " ₽"

def compound_interest(principal_cents, annual_rate_percent, years, compounds_per_year):
    if principal_cents <= 0:
        raise ValueError("Начальная сумма должна быть больше нуля.")
    if annual_rate_percent < 0 or years < 0 or compounds_per_year < 1:
        raise ValueError("Проверьте ставку, срок и периодичность капитализации.")
    principal = principal_cents / 100
    rate = annual_rate_percent / 100
    result = principal * (1 + rate / compounds_per_year) ** (compounds_per_year * years)
    return int(Decimal(str(result * 100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

def projected_value(initial_cents, annual_rate_percent, years):
    if initial_cents < 0 or years < 0:
        raise ValueError("Сумма и срок не могут быть отрицательными.")
    return int(Decimal(str((initial_cents / 100) * (1 + annual_rate_percent / 100) ** years * 100))
               .quantize(Decimal("1"), rounding=ROUND_HALF_UP))

def monte_carlo(initial_cents, annual_return_percent, volatility_percent, years, simulations=1000):
    """Run Monte Carlo paths using annual lognormal returns.

    Returns final values in cents, summary statistics, and sample paths in rubles.
    """
    import math
    import random
    from statistics import mean, median

    if initial_cents <= 0:
        raise ValueError("Начальный капитал должен быть больше нуля.")
    if not -99 <= annual_return_percent <= 100:
        raise ValueError("Годовая доходность должна быть от -99 до 100%.")
    if not 0 <= volatility_percent <= 100:
        raise ValueError("Волатильность должна быть от 0 до 100%.")
    if years < 1 or simulations < 100:
        raise ValueError("Нужно минимум 1 год и 100 сценариев.")

    expected_return = annual_return_percent / 100
    volatility = volatility_percent / 100
    drift = expected_return - (volatility ** 2) / 2
    finals = []
    sample_paths = []

    for simulation in range(simulations):
        value = initial_cents / 100
        path = [value]
        for year in range(years):
            annual_change = math.exp(drift + volatility * random.gauss(0, 1))
            value *= annual_change
            path.append(value)
        finals.append(int(round(value * 100)))
        if simulation < min(100, simulations):
            sample_paths.append(path)

    ordered = sorted(finals)
    p5 = ordered[int((len(ordered) - 1) * 0.05)]
    p95 = ordered[int((len(ordered) - 1) * 0.95)]
    losses = sum(value < initial_cents for value in finals)

    return {
        "average": int(round(mean(finals))),
        "median": int(round(median(finals))),
        "p5": p5,
        "p95": p95,
        "loss_probability": losses / simulations * 100,
        "final_values": finals,
        "sample_paths": sample_paths,
    }

