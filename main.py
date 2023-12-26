import json
import base58
import os

from dotenv import load_dotenv

from InquirerPy import inquirer

from solders.keypair import Keypair


import functions as f


class Config_CLI():
    
    @staticmethod
    def get_config_data() -> dict:
        """Fetch config file data.
        Returns: dict"""
        with open('config.json', 'r') as config_file:
            return json.load(config_file)
        
    @staticmethod
    def edit_config_file(config_data: dict) -> dict:
        """Edit config file.
        Returns: dict"""
        with open('config.json', 'w') as config_file:
            json.dump(config_data, config_file, indent=4)
    
    @staticmethod
    def collect_fees():
        """Asks the user if they want the CLI to take a small percentage of fees during their swaps."""
        collect_fees = inquirer.select(message="Would you like CLI to collect small fees from your swaps? (0.005%)", choices=["Yes", "No"]).execute()
        confirm = inquirer.select(message="Confirm?", choices=["Yes", "No"]).execute()
        if confirm == "Yes":
            config_data = Config_CLI.get_config_data()
            config_data['COLLECT_FEES'] = True if collect_fees == "Yes" else False
            Config_CLI.edit_config_file(config_data=config_data)
        elif confirm == "No":
            Config_CLI.collect_fees()

    @staticmethod
    def rpc_url():
        """Asks the user the RPC URL endpoint to be used."""
        rpc_url = inquirer.text(message="Enter your RPC URL endpoint:").execute()
        confirm = inquirer.select(message="Confirm?", choices=["Yes", "No"]).execute()
        if confirm == "Yes":
            config_data = Config_CLI.get_config_data()
            config_data['RPC_URL'] = rpc_url
            Config_CLI.edit_config_file(config_data=config_data)
        elif confirm == "No":
            Config_CLI.rpc_url()
    

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
    def get_wallets() -> dict:
        """Returns all wallets stored in wallets.json."""
        with open('wallets.json', 'r') as wallets_file:
            return json.load(wallets_file) 
    
    @staticmethod
    def add_wallet():
        """Adds a wallet to wallets.json."""
        wallet_private_key = inquirer.secret(message="Enter Wallet Private Key:").execute()
        wallet_private_key = os.environ['PRIVATE_KEY']
        
        if wallet_private_key != "":
            try:
                keypair = Keypair.from_bytes(base58.b58decode(wallet_private_key))
                pubkey = keypair.pubkey()
            except:
                print("! Invalid private key.")
                Wallets_CLI.add_wallet()
            
            confirm = inquirer.select(message=f"Wallet Address: {pubkey.__str__()}\nConfirm?", choices=["Yes", "No"]).execute()
            # confirm = "Yes"
            if confirm == "Yes":
                wallet_name = inquirer.text(message="Enter wallet name:").execute()
                # wallet_name = "DEGEN 1"
                
                with open('wallets.json', 'r') as wallets_file:
                    wallets_data = json.load(wallets_file)
                
                wallet_data = {
                        'wallet_name': wallet_name,
                        'pubkey': pubkey.__str__(),
                        'keypair': wallet_private_key,
                }
                wallets_data[len(wallets_data) + 1] = wallet_data
                
                with open('wallets.json', 'w') as wallets_file:
                    json.dump(wallets_data, wallets_file, indent=4)
                    
            elif confirm == "No":
                Wallets_CLI.add_wallet()
                
    
            


class Main_CLI():
    wallet = None
    
    def __init__(self):
        if len(f.load_wallets()) > -1:
            Main_CLI.first_login()
            Wallets_CLI.add_wallet()
        Main_CLI.main_menu()
        
    @staticmethod
    def first_login():
        """Setting up CLI configuration when it's the first login."""
        
        f.display_logo()
        print("Welcome to the Jupiter Python CLI v.0.0.1! Made by @_TaoDev_")
        print("This is your first login, let's setup the CLI configuration.")
        
        # Config_CLI.collect_fees()
        # Config_CLI.rpc_url()
        
    @staticmethod
    def main_menu():
        pass
        

if __name__ == "__main__":
    load_dotenv()
    Main_CLI()