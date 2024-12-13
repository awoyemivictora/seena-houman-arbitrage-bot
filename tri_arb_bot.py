# import ccxt.async_support as ccxt
# import os
# from dotenv import load_dotenv
# import asyncio
# from telegram import Bot
# import pandas as pd
# import math
# # from telegram import Update
# from telegram import Bot, Update
# from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, Updater
# import time 
# from datetime import datetime
# import os.path
# import traceback
# from decimal import Decimal
# import logging
# from decimal import ROUND_DOWN,ROUND_UP
# import asyncio
# from decimal import Decimal, InvalidOperation
# import numpy as np


# logging.basicConfig(filename='arbitrage.log', level=logging.INFO, format='%(asctime)s %(message)s')
# start_time = time.time()

# # Load API keys from config.env file
# load_dotenv('config.env')

# binance_api_key = os.environ.get('binance_api_key')
# binance_api_secret = os.environ.get('binance_api_secret')

# okx_api_key = os.environ.get('okx_api_key')
# okx_api_secret = os.environ.get('okx_api_secret')

# huobi_api_key = os.environ.get('huobi_api_key')
# huobi_api_secret = os.environ.get('huobi_api_secret')

# xt_api_key = os.environ.get('xt_api_key')
# xt_api_secret = os.environ.get('xt_api_secret')

# kucoin_api_key = os.environ.get('kucoin_api_key')
# kucoin_api_secret = os.environ.get('kucoin_api_secret')
# kucoin_password = os.environ.get('kucoin_password')

# # Load bot token and chat ID
# bot_token = os.environ.get('bot_token')
# chat_id = os.environ.get('chat_id')

# print(f"Loaded bot_token: {bot_token}")
# print(f"Loaded chat_id: {chat_id}")


# # Set the minimum time between messages of the Telegram Bot for each trading pair (in seconds)
# min_message_interval = 60   # 1 minute

# # Create a dictionary to keep track of the last time a message was sent for each trading pair
# last_message_times = {}

# #Load exchanges

# huobi = ccxt.huobi({
#     'apiKey': huobi_api_key,
#     'secret': huobi_api_secret,
#     'enableRateLimit': True
# })

# xt = ccxt.huobi({
#     'apiKey': xt_api_key,
#     'secret': xt_api_secret,
#     'enableRateLimit': True
# })

# kucoin = ccxt.kucoin({
#     'apiKey': kucoin_api_key,
#     'secret': kucoin_api_secret,
#     'password': kucoin_password,
#     'enableRateLimit': True
# })

# binance = ccxt.binance({
#     'apiKey': binance_api_key,
#     'secret': binance_api_secret,
#     'enableRateLimit': True
# })

# okx = ccxt.okx({
#     'apiKey': okx_api_key,
#     'secret': okx_api_secret,
#     'enableRateLimit': True
# })

# # Global variables
# running = True

# application = Application.builder().token(bot_token).build()

# # Defining function for the telegram Bot, the first is sending message, the second is to stop the script with by sending a message to the bot
# async def send_message(bot_token, chat_id, text):
#     await application.bot.send_message(chat_id=chat_id, text=text)

# async def stop_command(update: Update, context: CallbackContext):
#     global running
#     running = False
#     await update.message.reply_text('Stopping script')


# # Function for executing trades
# async def execute_trade(exchange, first_symbol, second_symbol, third_symbol, tickers, initial_amount, fee, first_tick_size, second_tick_size, third_tick_size):

#     # Use adjusted trades (including fee)
#     first_price = Decimal(tickers[first_symbol]['ask'])
#     first_trade = (initial_amount / first_price) * (1 - Decimal(fee))
#     first_trade = first_trade.quantize(Decimal(str(first_tick_size)), rounding=ROUND_DOWN)

#     # Place first order
#     print(f'\nPlacing first order: {first_trade} {first_symbol}')
#     order = await exchange.create_order(first_symbol, 'market', 'buy', float(first_trade))
#     order_id = order['id']

#     # Wait for first order to be filled
#     while True:
#         order = await exchange.fetch_order(order_id, first_symbol)
#         if order['status'] == 'closed':
#             break
#         await asyncio.sleep(1)

#     # Retrieve actual amount of first trading pair bought
#     first_trade = Decimal(order['filled'])

#     # Use the entire amount of first trade for the second order
#     second_trade = first_trade

#     # Place second order
#     print(f'Placing second order: {second_trade} {second_symbol}')
#     order = await exchange.create_order(second_symbol, 'market', 'sell', float(second_trade))
#     order_id = order['id']

#     # Wait for second order to be filled
#     while True:
#         order = await exchange.fetch_order(order_id, second_symbol)
#         if order['status'] == 'closed':
#             break
#         await asyncio.sleep(1)

#     # Retrieve actual cost of second trading pair
#     second_trade = Decimal(order['cost'])

#     # Use the entire cost of second trade for the third order
#     third_trade = second_trade * (1 - Decimal(fee))

#     # Place third order
#     print(f'Placing third order: {third_trade} {third_symbol}')
#     order = await exchange.create_order(third_symbol, 'market', 'sell', float(third_trade))
#     order_id = order['id']

#     while True:
#         order = await exchange.fetch_order(order_id, third_symbol)
#         if order['status'] == 'closed':
#             break
#         await asyncio.sleep(1)
    
#     # Fetch final balance
#     balance = await exchange.fetch_balance()
#     final_amount = balance['free']['USDT']

#     # Calculate profit/loss
#     profit = final_amount - initial_amount

#     print(f'Trade completed: Initial amount: {initial_amount}, Final amount: {final_amount}, Profit: {profit}')

#     # return profit and final amount if needed for further calculations or logging
#     return profit,  final_amount


# # Function for calculating the price impact of the order based on the orderbook asks, bids, and volumes
# async def calculate_price_impact(exchange, symbols, order_sizes, sides):
#     logging.info(f'Calculating price impact ')
    
#     # Fetch order books concurrently
#     order_books = await asyncio.gather(*[exchange.fetch_order_book(symbol) for symbol in symbols])
#     logging.info(f'Order books fetched on {exchange}')
#     price_impacts = []

#     for i in range(len(symbols)):
#         symbol = symbols[i]
#         side = sides[i]
#         order_size = float(order_sizes[i])
#         order_book = order_books[i]
        
#         # If we're buying, we need to look at the asks. If we're selling, we need to look at the bids.
#         orders = np.array(order_book['asks']) if side == 'buy' else np.array(order_book['bids'])

#         # Slice orders into prices and volumes
#         prices, volumes = orders[:,0], orders[:,1]

#         logging.info(f'Processing order book for {symbol} with side {side} and order size {order_size}')
#         logging.info(f'Order book prices: {prices}')
#         logging.info(f'Order book volumes: {volumes}')

#         total_value = 0
#         total_volume = 0

#         for j in range(len(prices)):
#             if order_size > 0:
#                 volume_for_this_order = min(volumes[j], order_size)
#                 value_for_this_order = volume_for_this_order * prices[j]

#                 logging.info(f'At price level {prices[j]}: volume_for_this_order={volume_for_this_order}, value_for_this_order={value_for_this_order}')

#                 total_value += value_for_this_order
#                 total_volume += volume_for_this_order
#                 order_size -= volume_for_this_order

#         if order_size <= 0:
#             # Calculate price impact
#             price_impact = total_value / total_volume if total_volume != 0 else None
#             logging.info(f'Price impact for {symbol}: {price_impact}')
#             price_impacts.append(price_impact)
#         else:
#             # If order size was not completely filled, price impact can't be calculated
#             price_impacts.append(None)
    
#     return price_impacts

# #Function for finding triangular arbitrage opportunities for each exchange
# async def find_triangular_arbitrage_opportunities(exchange, markets, tickers, exchange_name, fee, initial_amount ):    
    
#     logging.info('Finding arbitrage opportunities.')
#     # Read existing trades from CSV file
#     csv_file = 'tri_arb_opportunities.csv'
    
#     if os.path.exists(csv_file) and os.path.getsize(csv_file) > 0:
#         df = pd.read_csv(csv_file)
#         tri_arb_opportunities = df.to_dict('records')
#     else:
#         tri_arb_opportunities = []
    
#     # Add a new variable to keep track of the last time a trade was added to the CSV file for each trading pair
#     last_trade_time = {}
    
#     #load markets data
#     markets = await exchange.load_markets(True)
#     symbols = list(markets.keys())
#     tickers = await exchange.fetch_tickers()
    
#     # Create a dictionary with all the USDT symbols
#     usdt_symbols = {symbol for symbol in markets.keys() if symbol.endswith('/USDT')}
#     symbols_by_base = {}
    
#     for symbol in markets.keys():
#         base, quote = symbol.split('/')
#         if base not in symbols_by_base:
#             symbols_by_base[base] = set()
#         symbols_by_base[base].add(symbol)
    
#     # Split the first symbol in base and quote
#     for usdt_symbol in usdt_symbols:
#         first_symbol = usdt_symbol
#         base, quote = usdt_symbol.split('/')
#         second_base = base
#         second_symbols = symbols_by_base.get(second_base, set())
        
#         # Loop to find all the possible second symbols
#         for second_symbol in second_symbols:
#             unavailable_pairs = {'YGG/BNB', 'RAD/BNB', 'VOXEL/BNB', 'GLMR/BNB', 'UNI/EUR'}
#             if second_symbol == first_symbol or second_symbol in unavailable_pairs:
#                 continue
#             base, quote = second_symbol.split('/')
#             if base == second_base:
#                 third_base = quote
#             else:
#                 third_base = base
#             # Third symbol 
#             third_symbol = f'{third_base}/USDT'
            
#             # Check if trading pairs are valid on the exchange
#             if third_symbol in markets and first_symbol in markets and second_symbol in markets:
                
#                 # Retrieve tick size for all trading pairs
#                 market = exchange.markets
                
#                 first_market = market[first_symbol]
#                 first_tick_size = first_market['precision']['price']
                
#                 second_market = market[second_symbol]
#                 second_tick_size = second_market['precision']['price']
                
#                 third_market = market[third_symbol]
#                 third_tick_size = third_market['precision']['price']
                
#                 if any(symbol not in tickers for symbol in [first_symbol, second_symbol, third_symbol]):
#                     continue
                
#                 if all(tickers[symbol].get('ask') is not None for symbol in [first_symbol]) and all(tickers[symbol].get('bid') is not None for symbol in [second_symbol, third_symbol]):
#                     first_price = Decimal(tickers[first_symbol]['ask'])
#                     second_price = Decimal(tickers[second_symbol]['bid'])
#                     third_price = Decimal(tickers[third_symbol]['bid'])
#                 else:
#                     continue 
                    
#                 # Quantize the prices
#                 first_price = first_price.quantize(Decimal(str(first_tick_size)), rounding=ROUND_DOWN)
#                 second_price = second_price.quantize(Decimal(str(second_tick_size)), rounding=ROUND_DOWN)
#                 third_price = third_price.quantize(Decimal(str(third_tick_size)), rounding=ROUND_DOWN)

#                 if not first_price or not second_price or not third_price:
#                     continue

#                 # Check for zero prices to avoid division by zero
#                 if first_price == 0 or second_price == 0 or third_price == 0:
#                     continue

#                 #Trades calculation
#                 first_trade = initial_amount / first_price
#                 first_trade = first_trade.quantize(Decimal(str(first_tick_size)), rounding=ROUND_DOWN)
                
#                 second_trade = first_trade * second_price
#                 second_trade = second_trade.quantize(Decimal(str(second_tick_size)), rounding=ROUND_DOWN)

#                 third_trade = second_trade * third_price
#                 third_trade = third_trade.quantize(Decimal(str(third_tick_size)), rounding=ROUND_DOWN)

#                 # Check for negative trades
#                 if first_trade < 0 or second_trade < 0 or third_trade < 0:
#                     continue
                
#                 # Calculate profits        
#                 profit = third_trade - initial_amount
#                 profit_percentage = (profit / initial_amount) * 100
                
#                 opportunities = []

                
#                 if profit_percentage > 0.3:
#                     logging.info(f'Arbitrage opportunity found. Checking liquidity on {exchange_name}...')
#                     print(f'\rArbitrage opportunities found, checking liquidity', end='\r')
                    
#                     opportunities.append({
#                         'first_symbol': first_symbol,
#                         'second_symbol': second_symbol,
#                         'third_symbol': third_symbol,
#                         'first_trade': first_trade,
#                         'second_trade': second_trade,
#                         'third_trade': third_trade,
#                         'profit': profit,
#                         'profit_percentage': profit_percentage
#                     })

#                     # Sort opportunities by profit percentage in descending order
#                     opportunities.sort(key=lambda x: -x['profit_percentage'])

#                     # Take the top 1 or 2 opportunities
#                     top_opportunities = opportunities[:1]  # Change this to the number of opportunities you want to process

#                     # Calculate price impacts for top opportunities
#                     for opportunity in top_opportunities:
#                          # Log prices before checking opportunity
#                         logging.info(f'Before opportunity check on {exchange_name}: first_symbol= {first_symbol}, first_price = {first_price}, second_symbol = {second_symbol} second_price = {second_price}, third_symbol = {third_symbol}, third_price = {third_price}, profit percentage: {profit_percentage}')

#                         price_impacts = await calculate_price_impact(
#                             exchange,
#                             [opportunity['first_symbol'], opportunity['second_symbol'], opportunity['third_symbol']],
#                             [initial_amount, opportunity['first_trade'], opportunity['second_trade']],
#                             ['buy', 'sell', 'sell']
#                         )

#                         # Unpack the results
#                         first_price_impact, second_price_impact, third_price_impact = price_impacts

#                         # Quantize the price impacts
#                         first_price_impact = Decimal(first_price_impact).quantize(Decimal(str(first_tick_size)), rounding=ROUND_UP)
#                         second_price_impact = Decimal(second_price_impact).quantize(Decimal(str(second_tick_size)), rounding=ROUND_DOWN)
#                         third_price_impact = Decimal(third_price_impact).quantize(Decimal(str(third_tick_size)), rounding=ROUND_DOWN)

#                         # Calculate trades considering price impact and including fees
#                         first_trade_before_fees = initial_amount / first_price_impact 
#                         first_trade_amount = first_trade_before_fees * ( 1- Decimal(fee))
#                         first_trade_amount = first_trade_amount.quantize(Decimal(str(first_tick_size)), rounding=ROUND_DOWN)

#                         second_trade_before_fees = first_trade_amount * second_price_impact
#                         second_trade_amount = second_trade_before_fees * (1 - Decimal(fee))  
#                         second_trade_amount = second_trade_amount.quantize(Decimal(str(second_tick_size)), rounding=ROUND_DOWN)

#                         third_trade_before_fees = second_trade_amount * third_price_impact
#                         third_trade_amount = third_trade_before_fees * (1 - Decimal(fee))  
#                         third_trade_amount = third_trade_amount.quantize(Decimal(str(third_tick_size)), rounding=ROUND_DOWN)

#                         # Check real profit after price impact calculation and fees
#                         real_profit = third_trade_amount - initial_amount
#                         real_profit_percentage = (real_profit / initial_amount) * 100

#                         logging.info(f'After liquidity check on {exchange_name}: first_symbol= {first_symbol}, first_price = {first_price_impact}, second_symbol = {second_symbol} second_price = {second_price_impact}, third_symbol = {third_symbol}, third_price = {third_price_impact}, profit percentage: {real_profit_percentage}')
#                         if real_profit_percentage > 0.1:
                            
#                             logging.info(f'Arbitrage opportunity confirmed on {exchange_name}.')

#                             # call execute trades
#                             profit, final_amount = await execute_trade(
#                                 exchange,
#                                 first_symbol,
#                                 second_symbol,
#                                 third_symbol,
#                                 tickers,
#                                 initial_amount ,
#                                 fee,
#                                 first_tick_size,
#                                 second_tick_size,
#                                 third_tick_size
#                             )
                                
#                             print(f'Profitable trade found on {exchange_name}: {first_symbol} -> {second_symbol} -> {third_symbol}. Profit percentage: {real_profit_percentage:.2f}%', 'Profit change after checks: ', real_profit-profit, ' USDT')

#                             trade_key = f'{exchange_name}-{first_symbol}-{second_symbol}-{third_symbol}'
#                             current_time = time.time()
#                             last_message_time = last_message_times.get(trade_key, 0)
#                             time_since_last_message = current_time - last_message_time

#                             if time_since_last_message > min_message_interval:
#                                 message_text = f'Profitable trade found on {exchange_name}: {first_symbol} -> {second_symbol} -> {third_symbol}. Profit: {profit:.2f}. Profit percentage: {profit_percentage:.2f}%'
#                                 await send_message(bot_token, chat_id, message_text)
#                                 last_message_times[trade_key] = current_time

#                             # Check if a trade for the same trading pair has been added to the CSV file within the last minute
#                             last_trade_time_for_pair= last_trade_time.get(trade_key, 0)
#                             time_since_last_trade= current_time - last_trade_time_for_pair

#                             # If a trade for the same trading pair has not been added to the CSV file within the last  5 minute,
#                             # append trade_data to trades list and update last_trade_time[trade_key] with current time
#                             if time_since_last_trade> 300:
#                                 trade_data= {
#                                     'exchange': exchange_name,
#                                     'order size (USDT)': initial_amount,
#                                     'first_symbol': first_symbol,
#                                     'second_symbol': second_symbol,
#                                     'third_symbol': third_symbol,
#                                     'first_price': first_price_impact,
#                                     'second_price': second_price_impact,
#                                     'third_price': third_price_impact,
#                                     'profit_percentage': real_profit_percentage,
#                                     'time':  datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
#                                 }
#                                 tri_arb_opportunities.append(trade_data)
#                                 last_trade_time[trade_key]= current_time
#                         else:
#                             logging.info(f'Arbitrage opportunity not confirmed on {exchange_name}.')
#                             # Print arbitrage opportunity message
#                             print(f'\rArbitrage opportunities found, checking liquidity | Opportunities not confirmed', end='\r')     

#     # Write updated trades to CSV and Excell file
#     df= pd.DataFrame(tri_arb_opportunities)
#     df.to_csv(csv_file, index=False)
    

# async def main():
#     bot_token = "your_bot_token"  # Replace with your actual bot token
#     chat_id = "your_chat_id"  # Replace with your actual chat ID

#     # Get user input on USDT initial amount
#     while True:
#         initial_amount_input = input("How many USDT do you want to trade? | Only numbers are accepted (in the form 1, 10, 20.1) \nUSDT amount:  ")
#         try:
#             # Try to convert the input to a Decimal
#             initial_amount = Decimal(initial_amount_input)
#             break  # If the conversion succeeds, break out of the loop
#         except InvalidOperation:
#             print("Please enter a valid number.")

#     # Set up the application and dispatcher
#     application = Application.builder().token(bot_token).build()

#     # Add a command handler for the /stop command
#     application.add_handler(CommandHandler("stop", stop_command))
    
#     # Start polling
#     asyncio.create_task(application.initialize())
#     asyncio.create_task(application.start())
#     asyncio.create_task(application.updater.start_polling())
    
#     await send_message(bot_token, chat_id, "Finding arbitrage opportunities...")
#     global running
#     running = True

#     print('\nFinding arbitrage opportunities...')

#     iteration_count = 1  # Initialize iteration counter
#     start_time = time.time()

#     while running:
#         try:
#             # Load markets and tickers for all exchanges concurrently
#             binance_markets, binance_tickers, kucoin_markets, kucoin_tickers, okx_markets, okx_tickers, huobi_markets, huobi_tickers = await asyncio.gather(
#                 binance.load_markets(True),
#                 binance.fetch_tickers(),
#                 kucoin.load_markets(True),
#                 kucoin.fetch_tickers(),
#                 okx.load_markets(True),
#                 okx.fetch_tickers(),
#                 huobi.load_markets(True),
#                 huobi.fetch_tickers()
#             )

#             # Set fees for all exchanges
#             binance_fee = 0.001
#             kucoin_fee = 0.001
#             okx_fee = 0.001
#             huobi_fee = 0.002           

#             # Search for arbitrage opportunities on all exchanges concurrently
#             await asyncio.gather(
#                 find_triangular_arbitrage_opportunities(binance, binance_markets, binance_tickers, 'Binance', binance_fee, initial_amount),
#                 find_triangular_arbitrage_opportunities(kucoin, kucoin_markets, kucoin_tickers, 'Kucoin', kucoin_fee, initial_amount),
#                 find_triangular_arbitrage_opportunities(okx, okx_markets, okx_tickers, 'Okx', okx_fee, initial_amount),
#                 find_triangular_arbitrage_opportunities(huobi, huobi_markets, huobi_tickers, 'Huobi', huobi_fee, initial_amount)
#             )
            
#             end_time = time.time()
#             elapsed_time = end_time - start_time
#             # Print elapsed time and number of iterations
#             print(f'\n\rElapsed time: {elapsed_time:.2f} seconds | Number of iterations: {iteration_count}', end='\r')

#             iteration_count += 1  # Increment iteration counter
            
#             await asyncio.sleep(10)  # Sleep for 10 seconds before starting next iteration
        
#         except Exception as e:
#             print(f'An error occurred: {e}')
#             traceback.print_exc()
    
#     # Stop the application when the script is stopped
#     await application.stop()

#     # Release resources used by the exchange instances
#     await binance.close()
#     await kucoin.close()
#     await okx.close()
#     await huobi.close()

# if __name__ == "__main__":
#     asyncio.run(main())















#==================== REMOVING TELEGRAM INTEGRATITONS ================
import ccxt
import asyncio
import logging
import time
import traceback
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_UP
from datetime import datetime
import pandas as pd

# Set up logging to output to the terminal
logging.basicConfig(level=logging.INFO)

# Replace this with the path to your CSV file for storing trade data
csv_file = 'arbitrage_trades.csv'

# Initialize the exchange clients using ccxt
# binance = ccxt.binance({
#     'enableRateLimit': True,
#     'apiKey': 'your-api-key',  # Replace with your Binance API key
#     'secret': 'your-api-secret'  # Replace with your Binance API secret
# })

# kucoin = ccxt.kucoin({
#     'enableRateLimit': True,
#     'apiKey': 'your-api-key',  # Replace with your KuCoin API key
#     'secret': 'your-api-secret',  # Replace with your KuCoin API secret
#     'password': 'your-api-password'  # Replace with your KuCoin API password if needed
# })

# okx = ccxt.okx({
#     'enableRateLimit': True,
#     'apiKey': 'your-api-key',  # Replace with your OKX API key
#     'secret': 'your-api-secret',  # Replace with your OKX API secret
#     'passphrase': 'your-api-passphrase'  # Replace with your OKX API passphrase if needed
# })

# huobi = ccxt.huobi({
#     'enableRateLimit': True,
#     'apiKey': 'your-api-key',  # Replace with your Huobi API key
#     'secret': 'your-api-secret'  # Replace with your Huobi API secret
# })


xt = ccxt.xt({
    'apiKey': 'your-xt-api-key',
    'secret': 'your-xt-api-secret',
    'enableRateLimit': True
})

kucoin = ccxt.kucoin({
    'apiKey': 'your-kucoin-api-key',
    'secret': 'your-kucoin-api-secret',
    'password': 'your-kucoin-api-passphrase',
    'enableRateLimit': True
})


tri_arb_opportunities = []  # List to store found opportunities
last_message_times = {}  # To track last message time for the same trade
last_trade_time = {}  # To track last trade time for the same trade

# Minimum interval between trade messages (in seconds)
min_message_interval = 60

# Function to calculate price impacts (simplified placeholder, replace with your actual function)
async def calculate_price_impact(exchange, symbols, amounts, actions):
    # Placeholder logic to simulate price impact calculation
    return [0.99, 0.99, 0.99]  # Dummy price impacts

# Function to execute the trade (simplified placeholder, replace with your actual trade execution logic)
async def execute_trade(exchange, first_symbol, second_symbol, third_symbol, tickers, initial_amount, fee, first_tick_size, second_tick_size, third_tick_size):
    # Placeholder trade execution logic
    return initial_amount * 1.05, initial_amount * 1.05  # Dummy execution returning profit

# Function to find arbitrage opportunities
async def find_triangular_arbitrage_opportunities(exchange, markets, tickers, exchange_name, fee, initial_amount):
    global tri_arb_opportunities

    # Placeholder logic to simulate finding arbitrage opportunities
    # Replace this with actual arbitrage detection logic
    first_symbol = "BTC/USDT"
    second_symbol = "ETH/USDT"
    third_symbol = "XRP/USDT"

    first_price = Decimal('10000')  # Placeholder price for BTC
    second_price = Decimal('2000')  # Placeholder price for ETH
    third_price = Decimal('1.2')  # Placeholder price for XRP
    first_tick_size = 0.01
    second_tick_size = 0.01
    third_tick_size = 0.01

    # Trades calculation
    first_trade = initial_amount / first_price
    first_trade = first_trade.quantize(Decimal(str(first_tick_size)), rounding=ROUND_DOWN)
    
    second_trade = first_trade * second_price
    second_trade = second_trade.quantize(Decimal(str(second_tick_size)), rounding=ROUND_DOWN)

    third_trade = second_trade * third_price
    third_trade = third_trade.quantize(Decimal(str(third_tick_size)), rounding=ROUND_DOWN)

    # Check for negative trades
    if first_trade < 0 or second_trade < 0 or third_trade < 0:
        return  # Skip this opportunity if any trade is negative
    
    # Calculate profits
    profit = third_trade - initial_amount
    profit_percentage = (profit / initial_amount) * 100

    opportunities = []

    if profit_percentage > 0.3:
        logging.info(f'Arbitrage opportunity found on {exchange_name}, checking liquidity...')

        opportunities.append({
            'first_symbol': first_symbol,
            'second_symbol': second_symbol,
            'third_symbol': third_symbol,
            'first_trade': first_trade,
            'second_trade': second_trade,
            'third_trade': third_trade,
            'profit': profit,
            'profit_percentage': profit_percentage
        })

        # Sort opportunities by profit percentage in descending order
        opportunities.sort(key=lambda x: -x['profit_percentage'])

        # Take the top opportunity
        top_opportunities = opportunities[:1]

        for opportunity in top_opportunities:
            # Log the prices before checking opportunity
            logging.info(f'Before opportunity check on {exchange_name}: first_symbol= {first_symbol}, first_price = {first_price}, second_symbol = {second_symbol} second_price = {second_price}, third_symbol = {third_symbol}, third_price = {third_price}, profit percentage: {profit_percentage}')

            price_impacts = await calculate_price_impact(
                exchange,
                [opportunity['first_symbol'], opportunity['second_symbol'], opportunity['third_symbol']],
                [initial_amount, opportunity['first_trade'], opportunity['second_trade']],
                ['buy', 'sell', 'sell']
            )

            # Unpack the results
            first_price_impact, second_price_impact, third_price_impact = price_impacts

            # Quantize the price impacts
            first_price_impact = Decimal(first_price_impact).quantize(Decimal(str(first_tick_size)), rounding=ROUND_UP)
            second_price_impact = Decimal(second_price_impact).quantize(Decimal(str(second_tick_size)), rounding=ROUND_DOWN)
            third_price_impact = Decimal(third_price_impact).quantize(Decimal(str(third_tick_size)), rounding=ROUND_DOWN)

            # Calculate trades considering price impact and including fees
            first_trade_before_fees = initial_amount / first_price_impact
            first_trade_amount = first_trade_before_fees * (1 - Decimal(fee))
            first_trade_amount = first_trade_amount.quantize(Decimal(str(first_tick_size)), rounding=ROUND_DOWN)

            second_trade_before_fees = first_trade_amount * second_price_impact
            second_trade_amount = second_trade_before_fees * (1 - Decimal(fee))
            second_trade_amount = second_trade_amount.quantize(Decimal(str(second_tick_size)), rounding=ROUND_DOWN)

            third_trade_before_fees = second_trade_amount * third_price_impact
            third_trade_amount = third_trade_before_fees * (1 - Decimal(fee))
            third_trade_amount = third_trade_amount.quantize(Decimal(str(third_tick_size)), rounding=ROUND_DOWN)

            # Check real profit after price impact calculation and fees
            real_profit = third_trade_amount - initial_amount
            real_profit_percentage = (real_profit / initial_amount) * 100

            logging.info(f'After liquidity check on {exchange_name}: first_symbol= {first_symbol}, first_price = {first_price_impact}, second_symbol = {second_symbol} second_price = {second_price_impact}, third_symbol = {third_symbol}, third_price = {third_price_impact}, profit percentage: {real_profit_percentage}')
            if real_profit_percentage > 0.1:
                logging.info(f'Arbitrage opportunity confirmed on {exchange_name}.')

                # Print the found opportunity in the terminal
                print(f'Profitable trade found on {exchange_name}: {first_symbol} -> {second_symbol} -> {third_symbol}. Profit percentage: {real_profit_percentage:.2f}%')

                # Save the trade data
                trade_key = f'{exchange_name}-{first_symbol}-{second_symbol}-{third_symbol}'
                current_time = time.time()
                last_trade_time_for_pair = last_trade_time.get(trade_key, 0)
                time_since_last_trade = current_time - last_trade_time_for_pair

                if time_since_last_trade > 300:
                    trade_data = {
                        'exchange': exchange_name,
                        'order size (USDT)': initial_amount,
                        'first_symbol': first_symbol,
                        'second_symbol': second_symbol,
                        'third_symbol': third_symbol,
                        'first_price': first_price_impact,
                        'second_price': second_price_impact,
                        'third_price': third_price_impact,
                        'profit_percentage': real_profit_percentage,
                        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    }
                    tri_arb_opportunities.append(trade_data)
                    last_trade_time[trade_key] = current_time

    # Write updated trades to CSV
    df = pd.DataFrame(tri_arb_opportunities)
    df.to_csv(csv_file, index=False)

# Main function to start the bot
async def main():
    # Get user input on USDT initial amount
    while True:
        initial_amount_input = input("How many USDT do you want to trade? | Only numbers are accepted (in the form 1, 10, 20.1) \nUSDT amount: ")
        try:
            # Try to convert the input to a Decimal
            initial_amount = Decimal(initial_amount_input)
            break  # If the conversion succeeds, break out of the loop
        except InvalidOperation:
            print("Please enter a valid number.")

    print('\nFinding arbitrage opportunities...')

    iteration_count = 1  # To track the number of iterations
    while True:
        try:
            # Find opportunities across exchanges
            # await find_triangular_arbitrage_opportunities(binance, binance.markets, binance.fetch_tickers(), 'Binance', 0.001, initial_amount)
            await find_triangular_arbitrage_opportunities(kucoin, kucoin.markets, kucoin.fetch_tickers(), 'KuCoin', 0.001, initial_amount)
            await find_triangular_arbitrage_opportunities(xt, xt.markets, xt.fetch_tickers(), 'XT', 0.001, initial_amount)
            # await find_triangular_arbitrage_opportunities(huobi, huobi.markets, huobi.fetch_tickers(), 'Huobi', 0.001, initial_amount)

            iteration_count += 1
            print(f'\nFinished iteration {iteration_count}.')

            # Delay before the next iteration
            await asyncio.sleep(10)  # Adjust the delay as needed

        except Exception as e:
            logging.error("An error occurred: %s", str(e))
            traceback.print_exc()
            # Continue with the next iteration after a small delay
            await asyncio.sleep(5)

# Run the bot
asyncio.run(main())
