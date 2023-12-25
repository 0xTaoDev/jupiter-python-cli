from pyfiglet import Figlet
import json

def display_logo() -> None:
    """Display Jupiter CLI logo."""
    print("\033c\n", end="")
    print("-" * 51, "\n" + Figlet(font='small').renderText('JUPITER  CLI\n') + "-" * 51 + "\n")
    

def load_wallets() -> dict:
    """Returns all wallets stored in wallets.json."""
    with open('wallets.json', 'r') as wallets_file:
        return json.load(wallets_file)