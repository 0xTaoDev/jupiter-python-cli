from pyfiglet import Figlet
import json
import httpx

def display_logo() -> None:
    """Display Jupiter CLI logo."""
    print("\033c\n", end="")
    print("-" * 51, "\n" + Figlet(font='small').renderText('JUPITER  CLI\n') + "-" * 51 + "\n")
    
def load_wallets() -> dict:
    """Returns all wallets stored in wallets.json."""
    with open('wallets.json', 'r') as wallets_file:
        return json.load(wallets_file)
    
def get_crypto_price(crypto: str) -> float:
    """Returns crypto price."""
    API_BINANCE = f"https://www.binance.com/api/v3/ticker/price?symbol={crypto}USDT"
    crypto_price =float(httpx.get(API_BINANCE).json()['price'])
    return crypto_price

def get_timestamp_formatted(unix_timestamp: int) -> str:
    """Returns timestamp formatted based on a unix timestamp."""
    if unix_timestamp < 60:
        return f"{unix_timestamp} seconds"
    elif unix_timestamp < 3600:
        minutes = unix_timestamp // 60
        seconds = unix_timestamp % 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} and {seconds} second{'s' if seconds > 1 else ''}"
    elif unix_timestamp < 86400:
        hours = unix_timestamp // 3600
        minutes = (unix_timestamp % 3600) // 60
        return f"{hours} hour{'s' if hours > 1 else ''}, {minutes} minute{'s' if minutes > 1 else ''}"
    elif unix_timestamp < 604800:
        days = unix_timestamp // 86400
        hours = (unix_timestamp % 86400) // 3600
        return f"{days} day{'s' if days > 1 else ''}, {hours} hour{'s' if hours > 1 else ''}"
    elif unix_timestamp < 2629746:  # Approximately a month
        weeks = unix_timestamp // 604800
        days = (unix_timestamp % 604800) // 86400
        return f"{weeks} week{'s' if weeks > 1 else ''}, {days} day{'s' if days > 1 else ''}"
    else:
        months = unix_timestamp // 2629746  # Approximately a month
        days = (unix_timestamp % 2629746) // 86400
        return f"{months} month{'s' if months > 1 else ''}, {days} day{'s' if days > 1 else ''}"