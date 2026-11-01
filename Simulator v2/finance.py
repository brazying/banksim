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
