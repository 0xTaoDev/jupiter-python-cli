

import functions as f


class Wallet():
    def __init__(self, private_key: str) -> None:
        pass
    

class Jupiter_CLI():
    def __init__(self) -> None:
        pass
    
    
class Wallets_CLI():
    
    def __init__(self) -> None:
        pass
    
    @staticmethod
    def select_wallet():
        wallets = f.load_wallets()


class Main_CLI():
    wallet = None
    
    def __init__(self):
        if len(f.load_wallets()) == 0:
            self.first_login()
        Wallets_CLI.select_wallet()
            
    def first_login(self):
        f.display_logo()
        print("Welcome to the Jupiter Python CLI v.0.0.1! (Made by @_TaoDev_)")
        print("This is your first login, let's setup the CLI configuration.")
        


if __name__ == "__main__":
    Main_CLI()