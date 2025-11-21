from typing import Dict, Any


def lamports_to_sol(lamports: int) -> float:
    return lamports / 1_000_000_000


def format_token_amount(raw_amount: str, decimals: int) -> float:
    try:
        amount = int(raw_amount)
        return amount / (10 ** decimals)
    except (ValueError, TypeError):
        return 0.0