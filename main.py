import json
import base58
import base64
import os
import time
import re
import httpx
import asyncio

from dotenv import load_dotenv

from InquirerPy import inquirer

from tabulate import tabulate
import pandas as pd

from solders import message
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from solders.signature import Signature

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Processed
from solana.rpc.types import TxOpts

from spl.token.instructions import get_associated_token_address


from jupiter_python_sdk.jupiter import Jupiter


import functions as f

class Config_CLI():
    
    @staticmethod
    async def get_config_data() -> dict:
        """Fetch config file data.
        Returns: dict"""
        with open('config.json', 'r') as config_file:
            return json.load(config_file)
        
    @staticmethod
    async def edit_config_file(config_data: dict):
        """Edit config file."""
        with open('config.json', 'w') as config_file:
            json.dump(config_data, config_file, indent=4)
        return True
    
    @staticmethod
    async def prompt_collect_fees():
        """Asks the user if they want the CLI to take a small percentage of fees during their swaps."""
        collect_fees = inquirer.select(message="Would you like CLI to collect small fees from your swaps? (0.005%)", choices=["Yes", "No"]).execute_async()
        confirm = inquirer.select(message="Confirm?", choices=["Yes", "No"]).execute_async()
        if confirm == "Yes":
            config_data = Config_CLI.get_config_data()
            config_data['COLLECT_FEES'] = True if collect_fees == "Yes" else False
            Config_CLI.edit_config_file(config_data=config_data)
            return
        elif confirm == "No":
            Config_CLI.prompt_collect_fees()
            return

    @staticmethod
    async def prompt_rpc_url():
        """Asks the user the RPC URL endpoint to be used."""
        rpc_url = await inquirer.text(message="Enter your RPC URL endpoint:").execute_async()
        confirm = await inquirer.select(message="Confirm?", choices=["Yes", "No"]).execute_async()
        # rpc_url = os.getenv('RPC_URL')
        # confirm = "Yes"
        if confirm == "Yes":
            if rpc_url.endswith("/"):
                rpc_url = rpc_url[:-1]
                
            test_client = AsyncClient(endpoint=rpc_url)
            
            if not await test_client.is_connected():
                print("! Connection to RPC failed. Please enter a valid RPC.")
                await Config_CLI.prompt_rpc_url()
                return
            else:
                config_data = await Config_CLI.get_config_data()
                config_data['RPC_URL'] = rpc_url
                await Config_CLI.edit_config_file(config_data=config_data)
                return
        
        elif confirm == "No":
            await Config_CLI.prompt_rpc_url()
            return
            
    @staticmethod
    async def main_menu():
        """Main menu for CLI configuration."""
        f.display_logo()
        print("[CLI CONFIGURATION]\n")
        config_data = await Config_CLI.get_config_data()
        
        # print(f"CLI collect fees (0.005%): {'Yes' if config_data['COLLECT_FEES'] else 'No'}") # TBD
        
        client = AsyncClient(endpoint=config_data['RPC_URL'])
        start_time = time.time()
        await client.is_connected()
        end_time = time.time()
        print(f"RPC URL Endpoint: {config_data['RPC_URL']} ({round(end_time - start_time, 2)} ms)")
        
        print()
        
        config_cli_prompt_main_menu = await inquirer.select(message="Select CLI parameter to change:", choices=[
            # "CLI collect fees", # TBD
            "RPC URL Endpoint",
            "Back to main menu"
        ]).execute_async()
        
        if config_cli_prompt_main_menu == "CLI collect fees":
            await Config_CLI.prompt_collect_fees()
            await Config_CLI.main_menu()
        elif config_cli_prompt_main_menu == "RPC URL Endpoint":
            await Config_CLI.prompt_rpc_url()
            await Config_CLI.main_menu()
        elif config_cli_prompt_main_menu == "Back to main menu":
            await Main_CLI.main_menu()


class Wallet():
    def __init__(self, private_key: str):
        self.wallet = Keypair.from_bytes(base58.b58decode(private_key))
        
    async def get_token_balance(self, token_mint_account: str) -> dict:
        config_data = await Config_CLI.get_config_data()
        client = AsyncClient(endpoint=config_data['RPC_URL'])
        
        if token_mint_account == self.wallet.pubkey().__str__():
            get_token_balance = await client.get_balance(pubkey=self.wallet.pubkey())
            token_balance = {
                'decimals': 9,
                'balance': {
                    'int': get_token_balance.value,
                    'float': float(get_token_balance.value / 10 ** 9)
                }
            }
        else:
            get_token_balance = await client.get_token_account_balance(pubkey=token_mint_account)
            try:
                token_balance = {
                    'decimals': int(get_token_balance.value.decimals),
                    'balance': {
                        'int': get_token_balance.value.amount,
                        'float': float(get_token_balance.value.amount) / 10 ** int(get_token_balance.value.decimals)
                    }
                }
            except AttributeError:
                token_balance = {'balance': {'int': 0, 'float':0}}
        
        return token_balance
    
    async def get_token_mint_account(self, token_mint: str) -> Pubkey:
        token_mint_account = get_associated_token_address(owner=self.wallet.pubkey(), mint=Pubkey.from_string(token_mint))
        return token_mint_account
    
    async def sign_send_transaction(self, transaction_data: str, signatures: list=None):
        config_data = await Config_CLI.get_config_data()
        client = AsyncClient(endpoint=config_data['RPC_URL'])
        
        raw_transaction = VersionedTransaction.from_bytes(base64.b64decode(transaction_data))
        signature = self.wallet.sign_message(message.to_bytes_versioned(raw_transaction.message))
        signed_txn = VersionedTransaction.populate(raw_transaction.message, [signature])
        opts = TxOpts(skip_preflight=False, preflight_commitment=Processed)
        result = await client.send_raw_transaction(txn=bytes(signed_txn), opts=opts)
        transaction_id = json.loads(result.to_json())['result']
        print(f"Transaction sent: https://explorer.solana.com/tx/{transaction_id}")
        
    async def get_status_transaction(self, transaction_hash: str):
        config_data = await Config_CLI.get_config_data()
        client = AsyncClient(endpoint=config_data['RPC_URL'])
        
        while True:
            transaction_status = await client.get_transaction(tx_sig=Signature.from_string(transaction_hash), max_supported_transaction_version=0)
            input(transaction_status)
    
class Jupiter_CLI(Wallet):
    
    def __init__(self, private_key: str) -> None:
        super().__init__(private_key=private_key)
    
    async def main_menu(self):
        """Main menu for Jupiter CLI."""
        f.display_logo()
        print("[JUPITER CLI] [MAIN MENU]")
        await Wallets_CLI.display_selected_wallet()
        
        config_data = await Config_CLI.get_config_data()
        client = AsyncClient(endpoint=config_data['RPC_URL'])
        self.jupiter = Jupiter(async_client=client, keypair=self.wallet)
        
        #---------------------------------------------------------------------------
        #                            SWAP FUNCTION ALMOST FINISHED: ADD CHECK AMOUNT TOKEN TO SELL OWNED + CHECK TRANSATION STATUS
        #---------------------------------------------------------------------------
        # await self.get_status_transaction("4WP3da4QK5tg5Ff7RLjA51yYEZSMLLTcip4tQWvEeyEZrU7XUz2T4bU67NqgxSw9T4ZoHXQpCwx2nkw31YSnU4F2")

        jupiter_cli_prompt_main_menu = await inquirer.select(message="Select menu:", choices=[
            "Swap",
            "Limit Order",
            "DCA",
            "Snipe Token",
            "Lookup",
            "Stats",
            "Change wallet",
            "Back to main menu",
        ]).execute_async()
        
        if jupiter_cli_prompt_main_menu == "Swap":
            await self.swap_menu()
            await self.main_menu()
            return
        elif jupiter_cli_prompt_main_menu == "Change wallet":
            select_wallet = await Wallets_CLI.prompt_select_wallet()
            if select_wallet:
                self.wallet = Keypair.from_bytes(base58.b58decode(select_wallet))
            await self.main_menu()
            return
        elif jupiter_cli_prompt_main_menu == "Back to main menu":
            await Main_CLI.main_menu()
            return
        
    async def swap_menu(self):
        """Jupiter CLI - SWAP MENU."""
        f.display_logo()
        print("[JUPITER CLI] [SWAP MENU]")
        print()
        
        tokens_list = await Jupiter.get_tokens_list(list_type="all")
        choices = ["SOL"]
        for token in tokens_list:
            choices.append(f"{token['name']} ({token['address']})")
        
        # TOKEN TO SELL
        while True:
            select_sell_token = await inquirer.fuzzy(message="Enter token name or address you want to sell:", match_exact=True, choices=choices).execute_async()
            confirm = await inquirer.select(message="Confirm token to sell?", choices=["Yes", "No"]).execute_async()
            if confirm == "Yes":
                if select_sell_token == "SOL":
                    sell_token_symbol = select_sell_token
                    sell_token_address = select_sell_token
                else:
                    sell_token_symbol = re.search(r'^(.*?)\s*\(', select_sell_token).group(1)
                    sell_token_address = re.search(r'\((.*?)\)', select_sell_token).group(1)
                choices.remove(select_sell_token)
                break
        
        # TOKEN TO BUY
        while True:
            select_buy_token = await inquirer.fuzzy(message="Enter token name or address you want to buy:", match_exact=True, choices=choices).execute_async()
            confirm = await inquirer.select(message="Confirm token to buy?", choices=["Yes", "No"]).execute_async()
            if confirm == "Yes":
                if select_buy_token == "SOL":
                    buy_token_symbol = select_buy_token
                    buy_token_address = select_buy_token
                else:
                    buy_token_symbol = re.search(r'^(.*?)\s*\(', select_buy_token).group(1)
                    buy_token_address = re.search(r'\((.*?)\)', select_buy_token).group(1)
                choices.remove(select_buy_token)
                break
        
        if select_sell_token == "SOL":
            sell_token_account = self.wallet.pubkey().__str__()
        else:
            sell_token_account = await self.get_token_mint_account(token_mint=sell_token_address)
            
        sell_token_account_info = await self.get_token_balance(token_mint_account=sell_token_account)
        if sell_token_account_info['balance']['float'] == 0:
            input("! You don't have any tokens to sell.")
            return

        # AMOUNT TO SELL
        while True:
            prompt_amount_to_sell = await inquirer.number(message="Enter amount to sell:", float_allowed=True, max_allowed=sell_token_account_info['balance']['float']).execute_async()
            amount_to_sell = float(prompt_amount_to_sell)
            if float(amount_to_sell) == 0:
                print("! Amount to sell cannot be 0.")
            else:
                confirm_amount_to_sell = await inquirer.select(message="Confirm amount to sell?", choices=["Yes", "No"]).execute_async()
                if confirm_amount_to_sell == "Yes":
                    break
        
        # SLIPPAGE BPS
        while True:
            prompt_slippage_bps = await inquirer.number(message="Enter slippage percentage:", float_allowed=True, min_allowed=0.01, max_allowed=100.00).execute_async()
            slippage_bps = float(prompt_slippage_bps)
            
            confirm_slippage = await inquirer.select(message="Confirm slippage percentage?", choices=["Yes", "No"]).execute_async()
            if confirm_slippage == "Yes":
                break
            
        print()
        print(f"SELL {amount_to_sell} ${sell_token_symbol} -> ${buy_token_symbol} | SLIPPAGE: {slippage_bps}%")
        confirm_swap = await inquirer.select(message="Execute swap?", choices=["Yes", "No"]).execute_async()
        if confirm_swap == "Yes":
            swap_data = await self.jupiter.swap(
                input_mint=sell_token_address,
                output_mint=buy_token_address,
                amount=int(amount_to_sell *10**sell_token_account_info['decimals']),
                slippage_bps=int(slippage_bps*100)
            )
            await self.sign_send_transaction(swap_data)
            input("------------")
            return
        else:
            return
        
        

class Wallets_CLI():
    
    @staticmethod
    async def get_wallets() -> dict:
        """Returns all wallets stored in wallets.json."""
        with open('wallets.json', 'r') as wallets_file:
            return json.load(wallets_file) 
    
    @staticmethod
    async def prompt_select_wallet():
        """Prompts user to select a wallet."""
        await Wallets_CLI.display_wallets()
        wallets = await Wallets_CLI.get_wallets()
        
        choices = []
        for wallet_id, wallet_data in wallets.items():
            choices.append(f"ID {wallet_id} - {wallet_data['wallet_name']} - {wallet_data['pubkey']}")
            
        prompt_select_wallet = await inquirer.select(message="Select wallet:", choices=choices).execute_async()
        
        confirm = await inquirer.select(message="Confirm wallet selected?", choices=["Yes", "No"]).execute_async()
        if confirm == "Yes":        
            wallet_id = re.search(r'ID (\d+) -', prompt_select_wallet).group(1)
            
            config_data = await Config_CLI.get_config_data()
            config_data['LAST_WALLET_SELECTED'] = wallet_id
            await Config_CLI.edit_config_file(config_data=config_data)
            
            return wallets[wallet_id]['private_key']
            
        elif confirm == "No":
            await Wallets_CLI.prompt_select_wallet()
            return

    @staticmethod
    async def prompt_add_wallet():
        """Adds a wallet to wallets.json."""
        wallet_private_key = await inquirer.secret(message="Enter Wallet Private Key:").execute_async()
        # wallet_private_key = os.getenv('PRIVATE_KEY')
        
        if wallet_private_key != "":
            try:
                keypair = Keypair.from_bytes(base58.b58decode(wallet_private_key))
                pubkey = keypair.pubkey()
            except:
                print("! Invalid private key.")
                await Wallets_CLI.prompt_add_wallet()
                return
            
            confirm = await inquirer.select(message=f"Wallet Address: {pubkey.__str__()}\nConfirm?", choices=["Yes", "No"]).execute_async()
            # confirm = "Yes"
            if confirm == "Yes":
                wallet_name = await inquirer.text(message="Enter wallet name:").execute_async()
                # wallet_name = "DEGEN 1"
                
                with open('wallets.json', 'r') as wallets_file:
                    wallets_data = json.load(wallets_file)
                
                wallet_data = {
                        'wallet_name': wallet_name,
                        'pubkey': pubkey.__str__(),
                        'private_key': wallet_private_key,
                }
                wallets_data[len(wallets_data) + 1] = wallet_data
                
                with open('wallets.json', 'w') as wallets_file:
                    json.dump(wallets_data, wallets_file, indent=4)
                    
            elif confirm == "No":
                await Wallets_CLI.prompt_add_wallet()
                return
    
    @staticmethod
    async def prompt_edit_wallet_name():
        """Prompts user to edit a wallet name."""
        wallets = await Wallets_CLI.get_wallets()
        choices = []
        
        for wallet_id, wallet_data in wallets.items():
            choices.append(f"ID {wallet_id} - {wallet_data['wallet_name']} - {wallet_data['pubkey']}")
            
        prompt_select_wallet_to_edit_name = await inquirer.select(message="Select wallet:", choices=choices).execute_async()
        
        confirm = await inquirer.select(message="Confirm wallet selected?", choices=["Yes", "No"]).execute_async()
        if confirm == "Yes":
            new_wallet_name = await inquirer.text(message="Enter Wallet new name:").execute_async()
            
            confirm = await inquirer.select(message="Confirm wallet new name?", choices=["Yes", "No"]).execute_async()
            if confirm == "Yes":
                wallet_id = re.search(r'ID (\d+) -', prompt_select_wallet_to_edit_name).group(1)
                wallets[wallet_id]['wallet_name'] = new_wallet_name
                with open('wallets.json', 'w') as wallets_file:
                    json.dump(wallets, wallets_file, indent=4)
                return 
            elif confirm == "No":
                await Wallets_CLI.prompt_edit_wallet_name()
                return
            
        elif confirm == "No":
            await Wallets_CLI.prompt_edit_wallet_name()
            return
    
    @staticmethod
    async def prompt_delete_wallet():
        """Prompts user to delete wallet(s)"""
        wallets = await Wallets_CLI.get_wallets()
        choices = []
        
        for wallet_id, wallet_data in wallets.items():
            choices.append(f"ID {wallet_id} - {wallet_data['wallet_name']} - {wallet_data['pubkey']}")
    
        prompt_wallets_to_delete = await inquirer.checkbox(message="Select wallet(s) to delete with SPACEBAR or press ENTER:", choices=choices).execute_async()
        
        if len(prompt_wallets_to_delete) == 0:
            await Wallets_CLI.main_menu()
            return
        else:
            confirm = await inquirer.select(message="Confirm delete wallet(s) selected?", choices=["Yes", "No"]).execute_async()
            if confirm == "Yes":
                for wallet_to_delete in prompt_wallets_to_delete:
                    wallet_id = re.search(r'ID (\d+) -', wallet_to_delete).group(1)
                    del wallets[wallet_id]

                with open('wallets.json', 'w') as wallets_file:
                    json.dump(wallets, wallets_file, indent=4)
                return
            
            elif confirm == "No":
                await Wallets_CLI.main_menu()
                return
            
    @staticmethod
    async def display_wallets():
        print()
        data = {
            'ID': [],
            'NAME': [],
            'SOL BALANCE': [],
            'ADDRESS': [],
        }
        wallets = await Wallets_CLI.get_wallets()
        get_rpc_url = await Config_CLI.get_config_data()
        client = AsyncClient(endpoint=get_rpc_url['RPC_URL'])
        sol_price = f.get_crypto_price(crypto='SOL')
        
        for wallet_id, wallet_data in wallets.items():
            data['ID'].append(wallet_id)
            data['NAME'].append(wallet_data['wallet_name'])
            data['ADDRESS'].append(wallet_data['pubkey'])
            get_wallet_sol_balance = await client.get_balance(pubkey=Pubkey.from_string(wallet_data['pubkey']))
            sol_balance = round(get_wallet_sol_balance.value / 10 ** 9, 4)
            sol_balance_usd = round(sol_balance * sol_price, 2)
            data['SOL BALANCE'].append(f"{sol_balance} (${sol_balance_usd})")
            
        dataframe = tabulate(pd.DataFrame(data), headers="keys", tablefmt="fancy_grid", showindex="never", numalign="center")
        print(dataframe)
        print()
        return

    @staticmethod
    async def display_selected_wallet():
        print()
        print("WALLET SELECTED")
        config_data = await Config_CLI.get_config_data()
        wallets = await Wallets_CLI.get_wallets()
        client = AsyncClient(endpoint=config_data['RPC_URL'])
        
        get_sol_balance = await client.get_balance(pubkey=Pubkey.from_string(wallets[config_data['LAST_WALLET_SELECTED']]['pubkey']))
        sol_balance = round(get_sol_balance.value / 10 ** 9, 4)
        sol_price = f.get_crypto_price(crypto='SOL')
        sol_balance_usd = round(sol_balance * sol_price, 2)
        data = {
            'NAME': [wallets[config_data['LAST_WALLET_SELECTED']]['wallet_name']],
            'SOL BALANCE': [f"{sol_balance} (${sol_balance_usd})"],
            'ADDRESS': [wallets[config_data['LAST_WALLET_SELECTED']]['pubkey']],
        }
        
        dataframe = tabulate(pd.DataFrame(data), headers="keys", tablefmt="fancy_grid", showindex="never", numalign="center")
        print(dataframe)
        print()
        return

    @staticmethod 
    async def main_menu():
        """Main menu for Wallets CLI."""
        f.display_logo()
        print("[MANAGE WALLETS]")
        await Wallets_CLI.display_wallets()

        wallets_cli_prompt_main_menu = await inquirer.select(message="Select choice:", choices=[
            "Add wallet",
            "Edit wallet name",
            "Delete wallet(s)",
            "Back to main menu"
        ]).execute_async()
        
        if wallets_cli_prompt_main_menu == "Add wallet":
            await Wallets_CLI.prompt_add_wallet()
            await Wallets_CLI.main_menu()
            return
        elif wallets_cli_prompt_main_menu == "Edit wallet name":
            await Wallets_CLI.prompt_edit_wallet_name()
            await Wallets_CLI.main_menu()
            return
        elif wallets_cli_prompt_main_menu == "Delete wallet(s)":
            await Wallets_CLI.prompt_delete_wallet()
            await Wallets_CLI.main_menu()
            return
        elif wallets_cli_prompt_main_menu ==  "Back to main menu":
            await Main_CLI.main_menu()
            return
        
            
class Main_CLI():
    
    async def start_CLI():
        config_data = await Config_CLI.get_config_data()
        
        if config_data['FIRST_LOGIN'] is True:
            await Main_CLI.first_login()
            await Wallets_CLI.prompt_add_wallet()
            
            config_data['FIRST_LOGIN'] = False
            config_data['LAST_WALLET_SELECTED'] = 1
            await Config_CLI.edit_config_file(config_data=config_data)
        
        await Main_CLI.main_menu()
        
    @staticmethod
    async def first_login():
        """Setting up CLI configuration if it's the first login."""
        
        f.display_logo()
        print("Welcome to the Jupiter Python CLI v.0.0.1! Made by @_TaoDev_")
        print("This is your first login, let's setup the CLI configuration.")
        
        # async Config_CLI.prompt_collect_fees() # TBD
        await Config_CLI.prompt_rpc_url()
        
        return
        
    @staticmethod
    async def main_menu():
        """Main menu for CLI."""
        f.display_logo()
        print("Welcome to the Jupiter Python CLI v.0.0.1! Made by @_TaoDev_\n")
        cli_prompt_main_menu = await inquirer.select(message="Select menu:", choices=[
            "Jupiter Exchange",
            "Manage Wallets",
            "CLI Configuration",
            "About",
            "Exit CLI"
        ]).execute_async()
        
        if cli_prompt_main_menu == "Jupiter Exchange":
            config_data = await Config_CLI.get_config_data()
            wallets = await Wallets_CLI.get_wallets()
            last_wallet_selected = wallets[str(config_data['LAST_WALLET_SELECTED'])]['private_key']
            await Jupiter_CLI(private_key=last_wallet_selected).main_menu()
            return
        elif cli_prompt_main_menu == "Manage Wallets":
            await Wallets_CLI.main_menu()
            return
        elif cli_prompt_main_menu == "CLI Configuration":
            await Config_CLI.main_menu()
            return
        elif cli_prompt_main_menu == "About":
            print()
            print("DESCRIPTION")
            description = (
                "This tool is a commande-line interface to use Jupiter Exchange faster made by @_TaoDev_." + 
                "\nIt allows you to manage your wallets quickly, executes swaps, managing limit orders and DCA accounts, fetch wallet data (open orders, trades history...), tokens stats, and more!"
            )
            input(description)
            print()
            print("DISCLAIMER")
            disclaimer = (
                "Please note that the creator of this tool is not responsible for any loss of funds, damages, or other libailities resulting from the use of this software or any associated services." + 
                "\nThis tool is provided for educational purposes only and should not be used as financial advice, it is still in expiremental phase so use it at your own risk."
            )
            input(disclaimer)
            print()
            print("CONTRIBUTIONS")
            contributions = (
                "If you are interesting in contributing, fork the repository and submit a pull request in order to merge your improvements into the main repository." + 
                "\nContact me for any inquiry, I will reach you as soon as possible." +
                "\nDiscord: _taodev_ | Twitter: @_TaoDev_ | Github: 0xTaoDev"
            )
            input(contributions)
            print()
            print("DONATIONS")
            print("This project doesn't include platform fees.\nIf you find value in it and would like to support its development, your donations are greatly appreciated.")
            cli_prompt_main_menu = await inquirer.select(message="Would you make a donation?", choices=[
                "Yes",
                "No",
            ]).execute_async()
           
            await Main_CLI.main_menu()
            return
        elif cli_prompt_main_menu == "Exit CLI":
            print("\nBye!")
            time.sleep(1)
            exit()
        

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(Main_CLI.start_CLI())
