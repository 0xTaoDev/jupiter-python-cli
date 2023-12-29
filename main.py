import json
import base58
import base64
import os
import time
import re
import httpx
import asyncio

from datetime import datetime, timedelta

from dotenv import load_dotenv

from InquirerPy import inquirer

from tabulate import tabulate
import pandas as pd

from yaspin import yaspin

from solders import message
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from solders.signature import Signature
from solders.system_program import transfer, TransferParams


from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Processed
from solana.rpc.types import TxOpts
from solana.transaction import Transaction

from spl.token.instructions import get_associated_token_address


from jupiter_python_sdk.jupiter import Jupiter, Jupiter_DCA


import functions as f
import constants as c


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
        rpc_url = await inquirer.text(message="Enter your RPC URL endpoint or press ENTER:").execute_async()
        # rpc_url = os.getenv('RPC_URL')
        # confirm = "Yes"
        
        if rpc_url != "":
            confirm = await inquirer.select(message="Confirm?", choices=["Yes", "No"]).execute_async()
            if confirm == "Yes":
                if rpc_url.endswith("/"):
                    rpc_url = rpc_url[:-1]
                    
                test_client = AsyncClient(endpoint=rpc_url)
                
                if not await test_client.is_connected():
                    print(f"{c.RED}! Connection to RPC failed. Please enter a valid RPC.{c.RESET}")
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
        return
            
    @staticmethod
    async def main_menu():
        """Main menu for CLI settings."""
        f.display_logo()
        print("[CLI SETTINGS]\n")
        config_data = await Config_CLI.get_config_data()
        
        # print(f"CLI collect fees (0.005%): {'Yes' if config_data['COLLECT_FEES'] else 'No'}") # TBD
        
        client = AsyncClient(endpoint=config_data['RPC_URL'])
        start_time = time.time()
        await client.is_connected()
        end_time = time.time()
        print(f"RPC URL Endpoint: {config_data['RPC_URL']} {c.GREEN}({round(end_time - start_time, 2)} ms){c.RESET}")
        
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
    def __init__(self, rpc_url: str, private_key: str):
        self.wallet = Keypair.from_bytes(base58.b58decode(private_key))
        self.client = AsyncClient(endpoint=rpc_url)
        
    async def get_token_balance(self, token_mint_account: str) -> dict:
        
        if token_mint_account == self.wallet.pubkey().__str__():
            get_token_balance = await self.client.get_balance(pubkey=self.wallet.pubkey())
            token_balance = {
                'decimals': 9,
                'balance': {
                    'int': get_token_balance.value,
                    'float': float(get_token_balance.value / 10 ** 9)
                }
            }
        else:
            get_token_balance = await self.client.get_token_account_balance(pubkey=token_mint_account)
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
    
    async def sign_send_transaction(self, transaction_data: str, signatures_list: list=None):
        signatures = []

        raw_transaction = VersionedTransaction.from_bytes(base64.b64decode(transaction_data))
        signature = self.wallet.sign_message(message.to_bytes_versioned(raw_transaction.message))
        signatures.append(signature)
        if signatures_list:
            for signature in signatures_list:
                signatures.append(signature)
        signed_txn = VersionedTransaction.populate(raw_transaction.message, signatures)
        opts = TxOpts(skip_preflight=True, preflight_commitment=Processed)
        
        # print(signatures, transaction_data)
        # input()
        
        result = await self.client.send_raw_transaction(txn=bytes(signed_txn), opts=opts)
        transaction_hash = json.loads(result.to_json())['result']
        print(f"{c.GREEN}Transaction sent: https://explorer.solana.com/tx/{transaction_hash}{c.RESET}")
        input("\nPress ENTER to continue ")
        # await self.get_status_transaction(transaction_hash=transaction_hash) # TBD
        return
        
    async def get_status_transaction(self, transaction_hash: str):
        print("Checking transaction status...")
        get_transaction_details = await self.client.confirm_transaction(tx_sig=Signature.from_string(transaction_hash), sleep_seconds=1)
        transaction_status = get_transaction_details.value[0].err
        
        if transaction_status is None:
            print("Transaction SUCCESS!")
        else:
            print(f"{c.RED}Transaction FAILED!{c.RESET}")
            
        input("\nPress ENTER to continue")
        return
            
    
class Jupiter_CLI(Wallet):
    
    def __init__(self, rpc_url: str, private_key: str) -> None:
        super().__init__(rpc_url=rpc_url, private_key=private_key)
    
    async def main_menu(self):
        """Main menu for Jupiter CLI."""
        f.display_logo()
        print("[JUPITER CLI] [MAIN MENU]")
        await Wallets_CLI.display_selected_wallet()
        self.jupiter = Jupiter(async_client=self.client, keypair=self.wallet)
        
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
        
        elif jupiter_cli_prompt_main_menu == "Limit Order":
            await self.limit_order_menu()
            return
        
        elif jupiter_cli_prompt_main_menu == "DCA":
            await self.dca_menu()
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
    
    async def select_tokens(self, type_swap: str):
        """Prompts user to select tokens & amount to sell.
        
        type_swap (str): swap, limit_order, dca
        """
        tokens_list = await Jupiter.get_tokens_list(list_type="all")
        tokens_list_dca = await Jupiter_DCA.get_available_dca_tokens()
            
        choices = []
        for token in tokens_list:
            choices.append(f"{token['symbol']} ({token['address']})")
        
        # TOKEN TO SELL
        while True:
            select_sell_token = await inquirer.fuzzy(message="Enter token symbol or address you want to sell:", match_exact=True, choices=choices).execute_async()
            
            if select_sell_token is None:
                print(f"{c.RED}! Select a token to sell.")
            
            elif select_sell_token is not None:
                confirm = await inquirer.select(message="Confirm token to sell?", choices=["Yes", "No"]).execute_async()
                if confirm == "Yes":
                    if select_sell_token == "SOL (So11111111111111111111111111111111111111112)":
                        sell_token_symbol = select_sell_token
                        sell_token_address = "So11111111111111111111111111111111111111112"
                        sell_token_account = self.wallet.pubkey().__str__()
                    else:
                        sell_token_symbol = re.search(r'^(.*?)\s*\(', select_sell_token).group(1)
                        sell_token_address = re.search(r'\((.*?)\)', select_sell_token).group(1)
                        sell_token_account = await self.get_token_mint_account(token_mint=sell_token_address)
                        
                    sell_token_account_info = await self.get_token_balance(token_mint_account=sell_token_account)
                    if sell_token_account_info['balance']['float'] == 0:
                        print(f"{c.RED}! You don't have any tokens to sell.{c.RESET}")
                    elif type_swap == "dca" and sell_token_address not in tokens_list_dca:
                        print(f"{c.RED}Selected token to sell is not available for DCA")
                    else:
                        choices.remove(select_sell_token)
                        break
        
        # TOKEN TO BUY
        while True:
            select_buy_token = await inquirer.fuzzy(message="Enter symbol name or address you want to buy:", match_exact=True, choices=choices).execute_async()
                        
            if select_sell_token is None:
                print(f"{c.RED}! Select a token to buy.")
            
            elif select_sell_token is not None:
                
                confirm = await inquirer.select(message="Confirm token to buy?", choices=["Yes", "No"]).execute_async()
                if confirm == "Yes":
                    if select_buy_token == "SOL":
                        buy_token_symbol = select_buy_token
                        buy_token_address = "So11111111111111111111111111111111111111112"
                        buy_token_address = self.wallet.pubkey().__str__()
                    else:
                        buy_token_symbol = re.search(r'^(.*?)\s*\(', select_buy_token).group(1)
                        buy_token_address = re.search(r'\((.*?)\)', select_buy_token).group(1)
                        buy_token_account = await self.get_token_mint_account(token_mint=buy_token_address)
                    
                    buy_token_account_info = await self.get_token_balance(token_mint_account=buy_token_account)
                    if type_swap == "dca" and sell_token_address not in tokens_list_dca:
                        print(f"{c.RED}Selected token to buy is not available for DCA")
                    else:
                        choices.remove(select_buy_token)
                        break
        
        # AMOUNT TO SELL
        while True:
            print(f"You own {sell_token_account_info['balance']['float']} ${sell_token_symbol}")
            prompt_amount_to_sell = await inquirer.number(message="Enter amount to sell:", float_allowed=True, max_allowed=sell_token_account_info['balance']['float']).execute_async()
            amount_to_sell = float(prompt_amount_to_sell)
            if float(amount_to_sell) == 0:
                print("! Amount to sell cannot be 0.")
            else:
                confirm_amount_to_sell = await inquirer.select(message="Confirm amount to sell?", choices=["Yes", "No"]).execute_async()
                if confirm_amount_to_sell == "Yes":
                    break
        
        return sell_token_symbol, sell_token_address, buy_token_symbol, buy_token_address, amount_to_sell, sell_token_account_info, buy_token_account_info
    
    async def swap_menu(self):  
        """Jupiter CLI - SWAP MENU."""
        f.display_logo()
        print("[JUPITER CLI] [SWAP MENU]")
        print()
        
        sell_token_symbol, sell_token_address, buy_token_symbol, buy_token_address, amount_to_sell, sell_token_account_info, buy_token_account_info = await self.select_tokens(type_swap="swap")
        
        # SLIPPAGE BPS
        while True:
            prompt_slippage_bps = await inquirer.number(message="Enter slippage percentage (%):", float_allowed=True, min_allowed=0.01, max_allowed=100.00).execute_async()
            slippage_bps = float(prompt_slippage_bps)
            
            confirm_slippage = await inquirer.select(message="Confirm slippage percentage?", choices=["Yes", "No"]).execute_async()
            if confirm_slippage == "Yes":
                break
        
        # DIRECT ROUTE
        # direct_route = await inquirer.select(message="Single hop routes only (usually for shitcoins)?", choices=["Yes", "No"]).execute_async()
        # if direct_route == "Yes":
        #     direct_route = True
        # elif direct_route == "No":
        #     direct_route = False

        print()
        print(f"[SELL {amount_to_sell} ${sell_token_symbol} -> ${buy_token_symbol} | SLIPPAGE: {slippage_bps}%]")
        confirm_swap = await inquirer.select(message="Execute swap?", choices=["Yes", "No"]).execute_async()
        if confirm_swap == "Yes":
            try:
                swap_data = await self.jupiter.swap(
                    input_mint=sell_token_address,
                    output_mint=buy_token_address,
                    amount=int(amount_to_sell*10**sell_token_account_info['decimals']),
                    slippage_bps=int(slippage_bps*100),
                    # only_direct_routes=direct_route
                )
                await self.sign_send_transaction(swap_data)
            except:
                print(f"{c.RED}Swap execution failed.{c.RESET}")
                input("Press ENTER to continue ")
            return
        
        elif confirm_swap == "No":
            return
    
    async def limit_order_menu(self):
        """Jupiter CLI - LIMIT ORDER MENU."""
        loading_spinner = yaspin()
        loading_spinner.start()
        f.display_logo()
        print("[JUPITER CLI] [LIMIT ORDER MENU]")
        print()
        
        choices = [
            "Open Limit Order",
            "Display Canceled Orders History",
            "Display Filled Orders History",
            "Back to main menu",
        ]

        open_orders = await Jupiter_CLI.get_open_orders(wallet_address=self.wallet.pubkey().__str__())
        if len(open_orders) > 0:
            choices.insert(1, "Cancel Limit Order(s)")
            await Jupiter_CLI.display_open_orders(wallet_address=self.wallet.pubkey().__str__())
        
        loading_spinner.stop()
        limit_order_prompt_main_menu = await inquirer.select(message="Select menu:", choices=choices).execute_async()
        
        if limit_order_prompt_main_menu == "Open Limit Order":
            sell_token_symbol, sell_token_address, buy_token_symbol, buy_token_address, amount_to_sell, sell_token_account_info, buy_token_account_info = await self.select_tokens(type_swap="limit_order")
            
            # AMOUNT TO BUY
            while True:
                amount_to_buy = await inquirer.number(message="Enter amount to buy:", float_allowed=True).execute_async()
                confirm = await inquirer.select(message="Confirm amount to buy?", choices=["Yes", "No"]).execute_async()
                if confirm == "Yes":
                    amount_to_buy = float(amount_to_buy)
                    break

            prompt_expired_at = await inquirer.select(message="Add expiration to the limit order?", choices=["Yes", "No"]).execute_async()
            if prompt_expired_at == "Yes":
                unit_time_expired_at = await inquirer.select(message="Select unit time:", choices=[
                    "Minute(s)",
                    "Hour(s)",
                    "Day(s)",
                    "Week(s)",
                ]).execute_async()
                
                prompt_time_expired_at = await inquirer.number(message=f"Enter the number of {unit_time_expired_at.lower()} before your limit order expires:", float_allowed=False, min_allowed=1).execute_async()
                prompt_time_expired_at = int(prompt_time_expired_at)
                
                if unit_time_expired_at == "Minute(s)":
                    expired_at = prompt_time_expired_at * 60 + int(time.time())
                elif unit_time_expired_at == "Hour(s)":
                    expired_at = prompt_time_expired_at * 3600 + int(time.time())
                elif unit_time_expired_at == "Day(s)":
                    expired_at = prompt_time_expired_at * 86400 + int(time.time())
                elif unit_time_expired_at == "Week(s)":
                    expired_at = prompt_time_expired_at * 604800 + int(time.time())
            
            elif prompt_expired_at == "No":
                expired_at = None
            
            print("")
            expired_at_phrase = "Never Expires" if expired_at is None else f"Expires in {prompt_time_expired_at} {unit_time_expired_at.lower()}"
            
            print(f"[{amount_to_sell} ${sell_token_symbol} -> {amount_to_buy} ${buy_token_symbol} - {expired_at_phrase}]")
            confirm_open_order = await inquirer.select(message="Open order?", choices=["Yes", "No"]).execute_async()
            if confirm_open_order == "Yes":
                
                open_order_data = await self.jupiter.open_order(
                    input_mint=sell_token_address,
                    output_mint=buy_token_address,
                    in_amount=int(amount_to_sell * 10 ** sell_token_account_info['decimals']),
                    out_amount=int(amount_to_buy * 10 ** buy_token_account_info['decimals']),
                    expired_at=expired_at,
                )
                
                print()
                await self.sign_send_transaction(
                    transaction_data=open_order_data['transaction_data'],
                    signatures_list=[open_order_data['signature2']]
                )

            await self.limit_order_menu()
            return
        
        elif limit_order_prompt_main_menu == "Cancel Limit Order(s)":
            f.display_logo()
            
            loading_spinner = yaspin()
            loading_spinner.start()
            open_orders = await Jupiter_CLI.display_open_orders(wallet_address=self.wallet.pubkey().__str__())
            choices = []
        
            for order_id, order_data in open_orders.items():
                choices.append(f"ID {order_id} - {order_data['input_mint']['amount']} ${order_data['input_mint']['symbol']} -> {order_data['output_mint']['amount']} ${order_data['output_mint']['symbol']} (Account address: {order_data['open_order_pubkey']})")
            loading_spinner.stop()
            
            while True:
                prompt_select_cancel_orders = await inquirer.checkbox(message="Select orders to cancel (Max 10) or press ENTER:", choices=choices).execute_async()
                
                if len(prompt_select_cancel_orders) > 10:
                    print(f"{c.RED}! You can only cancel 10 orders at the time.")
                elif len(prompt_select_cancel_orders) == 0:
                    break
                
                confirm_cancel_orders = await inquirer.select(message="Cancel selected orders?", choices=["Yes", "No"]).execute_async()
                
                if confirm_cancel_orders == "Yes":
                    orders_to_cancel = []
                    
                    for order_to_cancel in prompt_select_cancel_orders:
                        order_account_address = re.search(r"Account address: (\w+)", order_to_cancel).group(1)
                        orders_to_cancel.append(order_account_address)
                        
                    cancel_orders_data = await self.jupiter.cancel_orders(orders=orders_to_cancel)
                    await self.sign_send_transaction(cancel_orders_data)
                    break
                    
                elif confirm_cancel_orders == "No":
                    break

            await self.limit_order_menu()
            return
        
        elif limit_order_prompt_main_menu == "Display Canceled Orders History":
            loading_spinner = yaspin()
            loading_spinner.start()
            tokens_list = await  Jupiter.get_tokens_list(list_type="all")
            cancel_orders_history = await Jupiter.query_orders_history(wallet_address=self.wallet.pubkey().__str__())
            data = {
                "ID": [],
                "CREATED AT": [],
                "TOKEN SOLD": [],
                "AMOUNT SOLD": [],
                "TOKEN BOUGHT": [],
                "AMOUNT BOUGHT": [],
                "STATE": [],
            }
            
            order_id = 1
            for order in cancel_orders_history:
                data['ID'].append(order_id)
                date = datetime.strptime(order['createdAt'], "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%m-%d-%Y %H:%M:%S")
                data['CREATED AT'].append(date)

                token_sold_address = order['inputMint']
                token_bought_address = order['outputMint']
                
                token_sold_decimals = int(next((token.get("decimals", "") for token in tokens_list if token_sold_address == token.get("address", "")), None))
                token_sold_symbol = next((token.get("symbol", "") for token in tokens_list if token_sold_address == token.get("address", "")), None)
                data['TOKEN SOLD'].append(token_sold_symbol)
                amount_sold = float(order['inAmount']) / 10 ** token_sold_decimals
                data['AMOUNT SOLD'].append(amount_sold)
                
                token_bought_decimals = int(next((token.get("decimals", "") for token in tokens_list if token_bought_address == token.get("address", "")), None))
                token_bought_symbol = next((token.get("symbol", "") for token in tokens_list if token_bought_address == token.get("address", "")), None)
                data['TOKEN BOUGHT'].append(token_bought_symbol)
                amount_bought = float(order['outAmount'])  / 10 ** token_bought_decimals
                data['AMOUNT BOUGHT'].append(amount_bought)
                
                state = order['state']
                data['STATE'] = state
                
                order_id += 1
                
            dataframe = tabulate(pd.DataFrame(data), headers="keys", tablefmt="fancy_grid", showindex="never", numalign="center")
            loading_spinner.stop()
            print(dataframe)
            print()
            
            input("Press ENTER to continue ")
            await self.limit_order_menu()
            return
        
        elif limit_order_prompt_main_menu == "Display Filled Orders History":
            loading_spinner = yaspin()
            loading_spinner.start()
            tokens_list = await  Jupiter.get_tokens_list(list_type="all")
            filled_orders_history = await Jupiter.query_trades_history(wallet_address=self.wallet.pubkey().__str__())
            data = {
                "ID": [],
                "CREATED AT": [],
                "TOKEN SOLD": [],
                "AMOUNT SOLD": [],
                "TOKEN BOUGHT": [],
                "AMOUNT BOUGHT": [],
                "STATE": [],
            }
            
            order_id = 1
            for order in filled_orders_history:
                data['ID'].append(order_id)
                date = datetime.strptime(order['createdAt'], "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%m-%d-%Y %H:%M:%S")
                data['CREATED AT'].append(date)

                token_sold_address = order['order']['inputMint']
                token_bought_address = order['order']['outputMint']
                
                token_sold_decimals = int(next((token.get("decimals", "") for token in tokens_list if token_sold_address == token.get("address", "")), None))
                token_sold_symbol = next((token.get("symbol", "") for token in tokens_list if token_sold_address == token.get("address", "")), None)
                data['TOKEN SOLD'].append(token_sold_symbol)
                amount_sold = float(order['inAmount']) / 10 ** token_sold_decimals
                data['AMOUNT SOLD'].append(amount_sold)
                
                token_bought_decimals = int(next((token.get("decimals", "") for token in tokens_list if token_bought_address == token.get("address", "")), None))
                token_bought_symbol = next((token.get("symbol", "") for token in tokens_list if token_bought_address == token.get("address", "")), None)
                data['TOKEN BOUGHT'].append(token_bought_symbol)
                amount_bought = float(order['outAmount'])  / 10 ** token_sold_decimals
                data['AMOUNT BOUGHT'].append(amount_bought)
                
                data['STATE'] = "FILLED"
                
                order_id += 1
                
            dataframe = tabulate(pd.DataFrame(data), headers="keys", tablefmt="fancy_grid", showindex="never", numalign="center")
            
            loading_spinner.stop()
            print(dataframe)
            print()
            
            input("Press ENTER to continue ")
            await self.limit_order_menu()
            return
        
        elif limit_order_prompt_main_menu == "Back to main menu":
            await self.main_menu()
            return
    
    async def dca_menu(self):
        """Jupiter CLI - DCA MENU."""
        f.display_logo()
        print("[JUPITER CLI] [DCA MENU]")
        print()
        
        choices = [
            "Open DCA Account",
            "Manage DCA Accounts",
            "Back to main menu"
        ]
        dca_menu_prompt_choice = await inquirer.select(message="Select menu:", choices=choices).execute_async()
        
        if dca_menu_prompt_choice == "Open DCA Account":
            
            sell_token_symbol, sell_token_address, buy_token_symbol, buy_token_address, amount_to_sell, sell_token_account_info, buy_token_account_info = await self.select_tokens(type_swap="dca")
            
            # IN AMOUNT PER CYCLE
            while True:
                in_amount_per_cycle = await inquirer.number(message="Enter amount per cycle to buy:", float_allowed=True, max_allowed=amount_to_sell).execute_async()
                in_amount_per_cycle = float(in_amount_per_cycle)
                confirm_in_amount_per_cycle = await inquirer.select(message="Confirm amount per cycle to buy?", choices=["Yes", "No"]).execute_async()
                if confirm_in_amount_per_cycle == "Yes":
                    break

            # CYCLE FREQUENCY
            while True:
                unit_time_cycle_frequency = await inquirer.select(message="Select unit time for cycle frequency:", choices=[
                    "Minute(s)",
                    "Hour(s)",
                    "Day(s)",
                    "Week(s)",
                ]).execute_async()
                
                prompt_cycle_frequency = await inquirer.number(message=f"Enter the number of {unit_time_cycle_frequency.lower()} for every cycle:", float_allowed=False, min_allowed=1).execute_async()
                prompt_cycle_frequency = int(prompt_cycle_frequency)
                
                if unit_time_cycle_frequency == "Minute(s)":
                    cycle_frequency = prompt_cycle_frequency * 60
                elif unit_time_cycle_frequency == "Hour(s)":
                    cycle_frequency = prompt_cycle_frequency * 3600
                elif unit_time_cycle_frequency == "Day(s)":
                    cycle_frequency = prompt_cycle_frequency * 86400
                elif unit_time_cycle_frequency == "Week(s)":
                    cycle_frequency = prompt_cycle_frequency * 604800
                    
                confirm_in_amount_per_cycle = await inquirer.select(message=f"Confirm number of {unit_time_cycle_frequency.lower()} for every cycle:", choices=["Yes", "No"]).execute_async()
                if confirm_in_amount_per_cycle == "Yes":
                    break
                
            # START AT
            unit_time_start_at = await inquirer.select(message="Select unit time to start DCA Account:", choices=[
                "Now",
                "Minute(s)",
                "Hour(s)",
                "Day(s)",
                "Week(s)",
            ]).execute_async()
            
            if unit_time_start_at == "Now":
                start_at = 0
            else:
                prompt_start_at = await inquirer.number(message=f"In how many {unit_time_start_at.lower()} does the DCA Account start:", float_allowed=False, min_allowed=1).execute_async()
                prompt_start_at = int(prompt_start_at)
                
                if unit_time_start_at == "Minute(s)":
                    start_at = prompt_start_at * 60 + int(time.time())
                elif unit_time_start_at == "Hour(s)":
                    start_at = prompt_start_at * 3600 + int(time.time())
                elif unit_time_start_at == "Day(s)":
                    start_at = prompt_start_at * 86400 + int(time.time())
                elif unit_time_start_at == "Week(s)":
                    start_at = prompt_start_at * 604800 + int(time.time())
            
            confirm_dca = await inquirer.select(message="Open DCA Account?", choices=["Yes", "No"]).execute_async()
            if confirm_dca == "Yes":  
                try:
                    transaction_info = await self.jupiter.dca.create_dca(
                        input_mint=Pubkey.from_string(sell_token_address),
                        output_mint=Pubkey.from_string(buy_token_address),
                        total_in_amount=int(amount_to_sell*10**sell_token_account_info['decimals']),
                        in_amount_per_cycle=int(in_amount_per_cycle*10**sell_token_account_info['decimals']),
                        cycle_frequency=cycle_frequency,
                        start_at=start_at
                    )
                    print(f"{c.GREEN}Transaction sent: https://explorer.solana.com/tx/{transaction_info['transaction_hash']}{c.RESET}")
            
                except:
                    print(f"{c.RED}Creating DCA Account failed.{c.RESET}")
                
                input("\nPress ENTER to continue.")

            await self.dca_menu()
            return
        
        elif dca_menu_prompt_choice == "Manage DCA Accounts":
            dca_accounts_data = await self.display_dca_accounts(wallet_address=self.wallet.pubkey().__str__())
            
            choices = []
            dca_account_id = 1
            for dca_account_data in dca_accounts_data:
                choices.append(f"ID {dca_account_id} (DCA Account Address: {dca_account_data['dcaKey']})")
                dca_account_id += 1
           
            dca_close_account_prompt_choice = await inquirer.checkbox(message="Select DCA Account to close with SPACEBAR or press ENTER:", choices=choices).execute_async()
            
            if len(dca_close_account_prompt_choice) == 0:
                await self.dca_menu()
                return
            
            else:
                for dca_account_to_close in dca_close_account_prompt_choice:
                    dca_account_id = re.search(r'ID (\d+)', dca_account_to_close).group(1)
                    dca_account_address = re.search(r'DCA Account Address: (\w+)', dca_account_to_close).group(1)
                    try:
                        await self.jupiter.dca.close_dca(dca_pubkey=Pubkey.from_string(dca_account_address))
                        print(f"{c.GREEN}Deleted DCA Account #{dca_account_id}{c.RESET}")
                    except:
                        print(f"{c.RED}Failed to delete DCA Account #{dca_account_id}{c.RESET}")
                    
                    await asyncio.sleep(1)

                input("Press ENTER to continue ")
                await self.dca_menu()
                return
                        
        elif dca_menu_prompt_choice == "Back to main menu":
            await self.main_menu()
            return
         
    @staticmethod
    async def get_open_orders(wallet_address: str) -> dict:
        """Returns all open orders in a correct format."""
        
        loading_spinner = yaspin()
        loading_spinner.start()
        tokens_list = await  Jupiter.get_tokens_list(list_type="all")
        open_orders_list = await Jupiter.query_open_orders(wallet_address=wallet_address)
        
        open_orders = {}
        
        order_id = 1
        for open_order in open_orders_list:
            open_order_pubkey = open_order['publicKey']
            
            expired_at = open_order['account']['expiredAt']
            if expired_at:
                expired_at = datetime.fromtimestamp(int(expired_at)).strftime('%m-%d-%Y %H:%M:%S')
            else:
                expired_at = "Never"
            
            input_mint_address = open_order['account']['inputMint']
            input_mint_amount = int(open_order['account']['inAmount'])
            input_mint_symbol = next((token.get("symbol", "") for token in tokens_list if input_mint_address == token.get("address", "")), None)
            input_mint_decimals = int(next((token.get("decimals", "") for token in tokens_list if input_mint_address == token.get("address", "")), None))
            
            output_mint_address = open_order['account']['outputMint']
            output_mint_amount = int(open_order['account']['outAmount'])
            output_mint_symbol = next((token.get("symbol", "") for token in tokens_list if output_mint_address == token.get("address", "")), None)
            output_mint_decimals = int(next((token.get("decimals", "") for token in tokens_list if output_mint_address == token.get("address", "")), None))
            
            open_orders[order_id] = {
                'open_order_pubkey': open_order_pubkey, 
                'expired_at': expired_at,
                'input_mint': {
                    'symbol': input_mint_symbol,
                    'amount': input_mint_amount / 10 ** input_mint_decimals
                },
                'output_mint': {
                    'symbol': output_mint_symbol,
                    'amount': output_mint_amount / 10 ** output_mint_decimals
                }
            }
            order_id += 1
        
        loading_spinner.stop()
        return open_orders

    @staticmethod
    async def display_open_orders(wallet_address: str) -> dict:
        """Displays current open orders and return open orders dict."""
        loading_spinner = yaspin()
        loading_spinner.start()
        open_orders = await Jupiter_CLI.get_open_orders(wallet_address=wallet_address)
        
        data = {
            'ID': [],
            'EXPIRED AT': [],
            'SELL TOKEN': [],
            'BUY TOKEN': [],
            'ACCOUNT ADDRESS': []
        }
        
        for open_order_id, open_order_data in open_orders.items():
            data['ID'].append(open_order_id)
            data['EXPIRED AT'].append(open_order_data['expired_at'])
            data['SELL TOKEN'].append(f"{open_order_data['input_mint']['amount']} ${open_order_data['input_mint']['symbol']}")
            data['BUY TOKEN'].append(f"{open_order_data['output_mint']['amount']} ${open_order_data['output_mint']['symbol']}")
            data['ACCOUNT ADDRESS'].append(open_order_data['open_order_pubkey'])
            
        dataframe = tabulate(pd.DataFrame(data), headers="keys", tablefmt="fancy_grid", showindex="never", numalign="center")
        loading_spinner.stop()
        
        print(dataframe)
        print()
        return open_orders

    async def display_dca_accounts(self, wallet_address: str):
        loading_spinner = yaspin()
        loading_spinner.start()
        tokens_list = await  Jupiter.get_tokens_list(list_type="all")
        get_dca_accounts = await self.jupiter.dca.fetch_user_dca_accounts(wallet_address=wallet_address, status=0)
        loading_spinner.stop()
        
        dca_accounts = get_dca_accounts['data']['dcaAccounts']
        
        data = {
            'ID': [],
            'CREATED AT': [],
            'END AT': [],
            'SELLING': [],
            'SELLING PER CYCLE': [],
            "BUYING": [],
            'CYCLE FREQUENCY': [],
            'NEXT ORDER AT': [],
            'ORDERS LEFT': []
        }

        dca_account_id = 1

        for dca_account_data in dca_accounts:
            data['ID'].append(dca_account_id)
            
            created_at = datetime.strptime(dca_account_data['createdAt'], "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%m-%d-%y %H:%M")
            data['CREATED AT'].append(created_at)
            
            end_at = int(dca_account_data['unfilledAmount']) / int(dca_account_data['inAmountPerCycle']) * int(dca_account_data['cycleFrequency'])
            data['END AT'].append(datetime.fromtimestamp(end_at).strftime("%m-%d-%y %H:%M"))
            
            input_mint_address = dca_account_data['inputMint']
            input_mint_amount = int(dca_account_data['inDeposited'])
            input_mint_symbol = next((token.get("symbol", "") for token in tokens_list if input_mint_address == token.get("address", "")), None)
            input_mint_decimals = int(next((token.get("decimals", "") for token in tokens_list if input_mint_address == token.get("address", "")), None))
            data['SELLING'].append(f"{input_mint_amount/10**input_mint_decimals} ${input_mint_symbol}")
            data['SELLING PER CYCLE'].append(f"{int(dca_account_data['inAmountPerCycle'])/10**input_mint_decimals} ${input_mint_symbol}")
            
            output_mint_address = dca_account_data['outputMint']
            output_mint_amount = int(dca_account_data['unfilledAmount'])
            output_mint_symbol = next((token.get("symbol", "") for token in tokens_list if output_mint_address == token.get("address", "")), None)
            output_mint_decimals = int(next((token.get("decimals", "") for token in tokens_list if output_mint_address == token.get("address", "")), None))
            data['BUYING'].append(f"{output_mint_amount/10**output_mint_decimals} ${output_mint_symbol}")
            
            data['CYCLE FREQUENCY'].append(f.get_timestamp_formatted(int(dca_account_data['cycleFrequency'])))
            
            # NEXT ORDER AT
            creation_unix_timestamp = int(datetime.fromisoformat(dca_account_data['createdAt'].replace('Z', '+00:00')).timestamp())
            date_now_unix_timestamp = int(time.time())
            time_elapsed = date_now_unix_timestamp - creation_unix_timestamp
            cycle_frequency = int(dca_account_data['cycleFrequency'])
            total_orders = int(int(dca_account_data['inDeposited']) / int(dca_account_data['inAmountPerCycle']))
            total_orders_filled = int(len(dca_account_data['fills']))
            total_orders_unfilled = total_orders - total_orders_filled

            next_order_time_unix_timestamp = creation_unix_timestamp + (cycle_frequency * (total_orders_filled + 1))
            next_order_time_date = datetime.fromtimestamp(next_order_time_unix_timestamp).strftime("%m-%d-%y %H:%M")
            data['NEXT ORDER AT'].append(next_order_time_date)
            
            data['ORDERS LEFT'].append(total_orders_unfilled)
            
            dca_account_id += 1
            

        dataframe = tabulate(pd.DataFrame(data), headers="keys", tablefmt="fancy_grid", showindex="never", numalign="center")
        loading_spinner.stop()
        
        print(dataframe)
        print()
        return dca_accounts

class Wallets_CLI():
    
    @staticmethod
    async def get_wallets() -> dict:
        """Returns all wallets stored in wallets.json."""
        with open('wallets.json', 'r') as wallets_file:
            return json.load(wallets_file) 
    
    @staticmethod
    async def prompt_select_wallet() -> str:
        """Prompts user to select a wallet."""
        await Wallets_CLI.display_wallets()
        wallets = await Wallets_CLI.get_wallets()
        
        choices = []
        for wallet_id, wallet_data in wallets.items():
            choices.append(f"ID {wallet_id} - {wallet_data['wallet_name']} - {wallet_data['pubkey']}")
        
        while True:
            prompt_select_wallet = await inquirer.select(message="Select wallet:", choices=choices).execute_async()
            confirm = await inquirer.select(message="Confirm wallet selected?", choices=["Yes", "No"]).execute_async()
            if confirm == "Yes":        
                wallet_id = re.search(r'ID (\d+) -', prompt_select_wallet).group(1)
                
                config_data = await Config_CLI.get_config_data()
                config_data['LAST_WALLET_SELECTED'] = wallet_id
                await Config_CLI.edit_config_file(config_data=config_data)
            
                return wallets[wallet_id]['private_key']

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
                print(f"{c.RED}! Invalid private key.{c.RESET}")
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
        loading_spinner = yaspin()
        loading_spinner.start()
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
        loading_spinner.stop()
        print(dataframe)
        print()
        return

    @staticmethod
    async def display_selected_wallet():
        print()
        print("WALLET SELECTED")
        loading_spinner = yaspin()
        loading_spinner.start()
        
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
        loading_spinner.stop()
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
            "CLI settings",
            "About",
            "Exit CLI"
        ]).execute_async()
        
        if cli_prompt_main_menu == "Jupiter Exchange":
            config_data = await Config_CLI.get_config_data()
            wallets = await Wallets_CLI.get_wallets()
            last_wallet_selected = wallets[str(config_data['LAST_WALLET_SELECTED'])]['private_key']
            await Jupiter_CLI(rpc_url=config_data['RPC_URL'], private_key=last_wallet_selected).main_menu()
            return
        elif cli_prompt_main_menu == "Manage Wallets":
            await Wallets_CLI.main_menu()
            return
        elif cli_prompt_main_menu == "CLI settings":
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
            confirm_make_donation = await inquirer.select(message="Would you make a donation?", choices=[
                "Yes",
                "No",
            ]).execute_async()

            if confirm_make_donation == "Yes":
                config_data = await Config_CLI.get_config_data()
                client = AsyncClient(endpoint=config_data['RPC_URL'])
                
                wallet_private_key = await Wallets_CLI.prompt_select_wallet()
                wallet = Wallet(rpc_url=config_data['RPC_URL'], private_key=wallet_private_key)
               
                get_wallet_sol_balance =  await client.get_balance(pubkey=wallet.wallet.pubkey())
                sol_price = f.get_crypto_price("SOL")
                sol_balance = round(get_wallet_sol_balance.value / 10 ** 9, 4)
                sol_balance_usd = round(sol_balance * sol_price, 2) - 0.05

                amount_usd_to_donate = await inquirer.number(message="Enter amount $ to donate:", float_allowed=True, max_allowed=sol_balance_usd).execute_async()

                prompt_donation_choice = await inquirer.select(message="Confirm donation?", choices=["Yes", "No"]).execute_async()
                if prompt_donation_choice == "Yes":
                    transfer_IX = transfer(TransferParams(
                        from_pubkey=wallet.wallet.pubkey(),
                        to_pubkey=Pubkey.from_string("AyWu89SjZBW1MzkxiREmgtyMKxSkS1zVy8Uo23RyLphX"),
                        lamports=int(float(amount_usd_to_donate) / sol_price * 10 ** 9)
                    ))
                    transaction = Transaction().add(transfer_IX)
                    transaction.sign(wallet.wallet)
                    try:
                        await client.send_transaction(transaction, wallet.wallet, opts=TxOpts(skip_preflight=True, preflight_commitment=Processed))
                        print(f"{c.GREEN}Thanks a lot for your donation{c.RESET}")
                    except:
                        print(f"{c.RED}Failed to send the donation.{c.RESET}")
                    
                    input("Press ENTER to continue ")
                
            await Main_CLI.main_menu()
            return
        
        elif cli_prompt_main_menu == "Exit CLI":
            print("\nBye!")
            time.sleep(1)
            exit()
        

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(Main_CLI.start_CLI())
