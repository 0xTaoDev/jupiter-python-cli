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