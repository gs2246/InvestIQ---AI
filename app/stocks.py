"""Single source of truth for the five stocks the app covers.

Keys are Yahoo Finance / NSE symbols; values are display names.
"""

EXCHANGE = "NSE"

TICKERS: dict[str, str] = {
    "MARUTI.NS": "Maruti Suzuki",
    "RELIANCE.NS": "Reliance",
    "INFY.NS": "Infosys",
    "HDFCBANK.NS": "HDFC Bank",
    "BAJAJ-AUTO.NS": "Bajaj Auto",
}
