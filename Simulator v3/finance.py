from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import math


def _decimal_value(value, field_name: str) -> Decimal:
    """Преобразовать вход в конечное Decimal с понятной ошибкой."""
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"Некорректное значение: {field_name}.") from None
    if not result.is_finite():
        raise ValueError(f"Значение «{field_name}» должно быть конечным числом.")
    return result


def to_cents(value: int | float | str) -> int:
    amount = _decimal_value(value, "сумма")
    try:
        precision = max(50, len(amount.as_tuple().digits) + max(amount.adjusted(), 0) + 5)
        with localcontext() as context:
            context.prec = precision
            amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            cents = int(amount * Decimal(100))
    except (InvalidOperation, OverflowError):
        raise ValueError("Сумма слишком велика для обработки.") from None
    if cents <= 0:
        raise ValueError("Сумма должна быть больше нуля.")
    return cents


def money(cents: int) -> str:
    """Форматировать копейки без преобразования в float и потери точности."""
    value = int(cents)
    sign = "-" if value < 0 else ""
    rubles, kopecks = divmod(abs(value), 100)
    formatted_rubles = f"{rubles:,}".replace(",", " ")
    return f"{sign}{formatted_rubles}.{kopecks:02d} ₽"


def _rounded_decimal_cents(value: Decimal) -> int:
    try:
        with localcontext() as context:
            # Запас точности позволяет квантовать очень большие суммы,
            # не упираясь в стандартный 28-значный контекст Decimal.
            context.prec = max(
                60,
                len(value.as_tuple().digits) + max(value.adjusted(), 0) + 10,
            )
            return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, OverflowError):
        raise ValueError("Результат слишком велик для расчёта.") from None


def compound_interest(
    principal_cents: int,
    annual_rate_percent: float,
    years: int,
    compounds_per_year: int,
) -> int:
    principal = _decimal_value(principal_cents, "начальная сумма")
    rate_percent = _decimal_value(annual_rate_percent, "годовая ставка")
    term = _decimal_value(years, "срок")
    compounds = _decimal_value(compounds_per_year, "периодичность капитализации")

    if principal <= 0:
        raise ValueError("Начальная сумма должна быть больше нуля.")
    if rate_percent < 0 or term < 0 or compounds < 1:
        raise ValueError("Проверьте ставку, срок и периодичность капитализации.")

    with localcontext() as context:
        context.prec = 80
        rate = rate_percent / Decimal(100)
        periods = compounds * term
        base = Decimal(1) + rate / compounds
        try:
            result_cents = principal * (base ** periods)
        except (InvalidOperation, OverflowError):
            raise ValueError("Результат слишком велик для расчёта.") from None
    return _rounded_decimal_cents(result_cents)


def projected_value(
    initial_cents: int,
    annual_rate_percent: float,
    years: int,
) -> int:
    initial = _decimal_value(initial_cents, "начальная сумма")
    rate_percent = _decimal_value(annual_rate_percent, "годовая ставка")
    term = _decimal_value(years, "срок")

    if initial < 0 or term < 0:
        raise ValueError("Сумма и срок не могут быть отрицательными.")
    if rate_percent < -100:
        raise ValueError("Годовая ставка не может быть ниже -100%.")

    with localcontext() as context:
        context.prec = 80
        base = Decimal(1) + rate_percent / Decimal(100)
        if term == 0:
            result_cents = initial
        elif base == 0:
            result_cents = Decimal(0)
        else:
            try:
                result_cents = initial * (base ** term)
            except (InvalidOperation, OverflowError):
                raise ValueError("Результат слишком велик для расчёта.") from None
    return _rounded_decimal_cents(result_cents)


def monte_carlo(
    initial_cents: int,
    annual_return_percent: float,
    volatility_percent: float,
    years: int,
    simulations: int = 1000,
) -> dict[str, object]:
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
            annual_change = math.exp(
                drift + volatility * random.gauss(0, 1)
            )
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



def monte_carlo_price_step(
    price_cents: int,
    daily_volatility: float,
    annual_return_percent: float = 8.0,
) -> int:
    """Смоделировать один симулируемый час движения цены.

    daily_volatility — прежняя дневная волатильность акции; она переводится
    в часовую с учётом 252 торговых дней и 365 календарных дней в году.
    """
    import math
    import random

    if price_cents <= 0:
        raise ValueError("Цена акции должна быть больше нуля.")
    if not 0 <= daily_volatility <= 1:
        raise ValueError("Дневная волатильность должна быть от 0 до 1.")
    if not -99 <= annual_return_percent <= 100:
        raise ValueError("Ожидаемая годовая доходность должна быть от -99 до 100%.")

    hours_per_year = 365 * 24
    annual_volatility = daily_volatility * math.sqrt(252)
    hourly_volatility = annual_volatility / math.sqrt(hours_per_year)
    hourly_drift = (annual_return_percent / 100 - 0.5 * annual_volatility ** 2) / hours_per_year
    random_shock = random.gauss(0, 1)
    log_return = hourly_drift + hourly_volatility * random_shock
    return max(1, int(round(price_cents * math.exp(log_return))))


def monte_carlo_capital(
    cash_cents: int,
    portfolio_cents: int,
    annual_return_percent: float,
    volatility_percent: float,
    years: int,
    simulations: int = 1000,
    monthly_contribution_cents: int = 0,
) -> dict[str, object]:
    """Моделирует общий капитал: денежный остаток отдельно, инвестиции по GBM."""
    import math
    import random
    from statistics import mean, median

    if cash_cents < 0 or portfolio_cents < 0 or cash_cents + portfolio_cents <= 0:
        raise ValueError("На счёте или в портфеле должен быть капитал.")
    if not -99 <= annual_return_percent <= 100:
        raise ValueError("Годовая доходность должна быть от -99 до 100%.")
    if not 0 <= volatility_percent <= 100:
        raise ValueError("Волатильность должна быть от 0 до 100%.")
    if years < 1 or simulations < 100 or monthly_contribution_cents < 0:
        raise ValueError("Проверьте срок, число сценариев и ежемесячное пополнение.")

    mu = annual_return_percent / 100
    sigma = volatility_percent / 100
    monthly_sigma = sigma / math.sqrt(12)
    monthly_drift = (mu - 0.5 * sigma * sigma) / 12
    starting_total = cash_cents + portfolio_cents
    year_values = [[] for _ in range(years + 1)]
    sample_paths = []

    for simulation in range(simulations):
        invested = portfolio_cents / 100
        cash = cash_cents / 100
        path = [starting_total / 100]
        for month in range(1, years * 12 + 1):
            shock = random.gauss(0, 1)
            invested *= math.exp(monthly_drift + monthly_sigma * shock)
            invested += monthly_contribution_cents / 100
            if month % 12 == 0:
                total = cash + invested
                year_values[month // 12].append(total)
                path.append(total)
        if simulation < min(100, simulations):
            sample_paths.append(path)

    median_by_year = []
    p5_by_year = []
    p95_by_year = []
    for index, values in enumerate(year_values):
        if index == 0:
            values = [starting_total / 100] * simulations
        ordered = sorted(values)
        median_by_year.append(float(median(ordered)))
        p5_by_year.append(float(ordered[int((len(ordered) - 1) * 0.05)]))
        p95_by_year.append(float(ordered[int((len(ordered) - 1) * 0.95)]))

    finals = year_values[-1]
    return {
        "average": int(round(mean(finals) * 100)),
        "median": int(round(median(finals) * 100)),
        "p5": int(round(p5_by_year[-1] * 100)),
        "p95": int(round(p95_by_year[-1] * 100)),
        "loss_probability": sum(v < starting_total / 100 for v in finals) / simulations * 100,
        "years": list(range(years + 1)),
        "median_path": median_by_year,
        "p5_path": p5_by_year,
        "p95_path": p95_by_year,
        "sample_paths": sample_paths,
    }
