from ib_insync import *
import json
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator
from ta.volatility import BollingerBands
from pyfiglet import Figlet
import datetime
from time import sleep

def welcome():
    f = Figlet(font='small')
    print(f.renderText('404 Profit Not Found'))
    print("\n\n\nWelcome to the trading bot, remember to open your IB Gateway before running the bot!")
    input("Press enter to continue...")
    print("\n\n\n")

def print_strings(string):
    print("["+str(datetime.datetime.now())+"]\t"+string)

def boot_IB():
    try:
        print_strings("IB Gateway connecting...")
        ib = IB()
        ib.connect('127.0.0.1', 7497, clientId=1)
        myAccount = ib.accountSummary()
        print_strings("IB Gateway connected")
        return myAccount, ib
    except:
        print_strings("Error connecting to IB Gateway")
        return None, None
        
def get_config():
    print_strings("Loading config file...")
    try:
        with open('config.json') as f:
            config = json.load(f)
        print_strings("Config file loaded")

        if config["Martingale_max"] <= 5:
            return config
        else:
            print_strings("Martingale_max should be less than 5")
    except:
        print_strings("Error loading config file")
        return None
    
def get_contract(config):
    try:
        print_strings("Getting contract for "+config["pair"]+"...")
        contract = Forex(config["pair"])
        print_strings("Contract for "+config["pair"]+" retrived!")
        return contract
    except:
        print_strings("Error getting contract for "+config["pair"])
        return None
    #FOREX PAIR ARE ALWAYS SHORTABLE

def detect_trigger(config,ib,contract):
    while True:
        SMA5_series, SMA25_series, RSI_series, Bollinger_H_series, Bollinger_L_series, myData, contract = get_parameters(ib, config,contract)
        
        if SMA5_series.iloc[-1] > SMA25_series.iloc[-1] and SMA5_series.iloc[-2] < SMA25_series.iloc[-2]:
            cross_value = -1 #long
        elif SMA5_series.iloc[-1] < SMA25_series.iloc[-1] and SMA5_series.iloc[-2] > SMA25_series.iloc[-2]:
            cross_value = 1
        else:
            cross_value = 0
        
        if RSI_series.iloc[-1] > config["RSI_high"]:
            RSI_value = 1
        elif RSI_series.iloc[-1] < config["RSI_low"]:
            RSI_value = -1
        else:
            RSI_value = 0
        
        if myData['close'].iloc[-1] > Bollinger_H_series.iloc[-1]:
            bollinger_value = 1
        elif myData['close'].iloc[-1] < Bollinger_L_series.iloc[-1]:
            bollinger_value = -1
        else:
            bollinger_value = 0

        
        print_strings(str(abs(cross_value)+abs(RSI_value)+abs(bollinger_value))+" Indicators met")

        if cross_value + RSI_value + bollinger_value >= config["minimum_indicators_to_open"]:
            order_info = {}
            if bool(config["Trending"]):
                order_info["type"] = "BUY"
            else:
                order_info["type"] = "SELL"
            initiate_strategy(contract, order_info, ib, config, myData)
            #handle after
        elif cross_value + RSI_value + bollinger_value <= -config["minimum_indicators_to_open"]:
            order_info = {}
            if bool(config["Trending"]):
                order_info["type"] = "SELL"
            else:
                order_info["type"] = "BUY"
            initiate_strategy(contract, order_info, ib, config, myData)
            #handle after
        else:
            sleep(config["sleep_time"])


def initiate_strategy(contract, order_info, ib, config, myData):
    print_strings("Sending market order: SIZE: "+str(config["Initial_size_trade"])+" TYPE: "+order_info["type"])
    order = MarketOrder(order_info["type"], config["Initial_size_trade"])
    trade = ib.placeOrder(contract, order)
    print_strings("Market order sent!")
    
    fill_processed = [False]  
    def on_fill(trade, fill):
        get_fibonacci_levels(myData, fill, config, order_info,ib)
        fill_processed[0] = True  
    trade.fillEvent += on_fill  
    while not fill_processed[0]:
        ib.sleep(0.5)

    
    
def get_fibonacci_levels(myData, fill,config, order_info,ib):
    fill_price = fill.execution.price
    print_strings("Market order filled! PRICE:"+str(fill_price))
    highest_price = myData['high'].tail(config["Fibonacci_duration"]).max()
    lowest_price = myData['low'].tail(config["Fibonacci_duration"]).min()

    #if myData['high'].idxmax() > myData['low'].idxmin():
     #   latest_price = highest_price
    #else:
     #   latest_price = lowest_price
    
    delta_diff = highest_price - lowest_price
    
    retracements = {
        1: [(fill_price+delta_diff*0.236).round(4),(fill_price-delta_diff*0.236).round(4)],
        2: [(fill_price+delta_diff*0.382).round(4),(fill_price-delta_diff*0.382).round(4)],
        3: [(fill_price+delta_diff*0.5).round(4),(fill_price-delta_diff*0.5).round(4)],
        4: [(fill_price+delta_diff*0.618).round(4),(fill_price-delta_diff*0.618).round(4)],
        5: [(fill_price+delta_diff*0.786).round(4),(fill_price-delta_diff*0.786).round(4)]
    }

    print_strings("Fibonacci retracements calculated!")
    
    print_strings("Sending limit orders...")

    
    
    send_limit_orders(order_info, config,ib,retracements)

def send_limit_orders(order_info, config,ib,retracements):
    
    for i in range(1,config["Martingale_max"]+1):
        if order_info["type"] == "BUY":
            price_limit = retracements[i][1]
        else:
            price_limit = retracements[i][0]
        
        size = round(config["Initial_size_trade"]*config["Martingale_multiplier"]**i,4)

        print_strings("Placing limit order: SIZE: "+str(size)+" TYPE: "+order_info["type"]+" PRICE: "+str(price_limit))
        order = LimitOrder(order_info["type"], size, price_limit)
        trade = ib.placeOrder(contract, order)
        print_strings("Limit order placed!")


def send_tp(size, price, ib):
    None

        


def get_parameters(ib,config,contract):

    print_strings("Getting historical data for "+config["pair"]+"...")
    try:
        bars = ib.reqHistoricalData(
            contract, endDateTime='', durationStr= config["durationStr"],
            barSizeSetting= config["barSizeSetting"], whatToShow='MIDPOINT', useRTH=0) # if you want, you can show BID or ASK
        print_strings("Historical data for "+config["pair"]+" downloaded")
    except:
        print_strings("Error downloading historical data for "+config["pair"])
        return None, None, None, None, None, None
    # convert to a pandas dataframe:
    
    try:
        print_strings("Calculating indicators...")
        myData = util.df(bars)
        SMA5_series = SMAIndicator(close=myData['close'], window=config["SMA_small_duration"]).sma_indicator()
        SMA25_series = SMAIndicator(close=myData['close'], window=config["SMA_big_duration"]).sma_indicator()
        RSI_series = RSIIndicator(close=myData['close'], window=config["RSI_duration"]).rsi()
        Bollinger_H_series = BollingerBands(close=myData['close'], window=config["bolinger_band_duration"], window_dev=config["bolinger_band_std_dev"]).bollinger_hband()
        Bollinger_L_series = BollingerBands(close=myData['close'], window=config["bolinger_band_duration"], window_dev=config["bolinger_band_std_dev"]).bollinger_lband()
        print_strings("Indicators calculated")
    except:
        print_strings("Error calculating indicators")
        return None, None, None, None, None, None

    return SMA5_series, SMA25_series, RSI_series, Bollinger_H_series, Bollinger_L_series, myData, contract


        
    #order = LimitOrder(order_info["type"], config["Initial_size_trade"], trade.orderStatus.avgFillPrice + config["Stop_loss"])




def plot_indicators(SMA5_series, SMA25_series, RSI_series, myData, Bollinger_H_series, Bollinger_L_series):
    import matplotlib.pyplot as plt
    # Create the figure and primary axis
    fig, ax1 = plt.subplots(figsize=(12, 8))  # Increasing the figure size
    # Create a secondary y-axis for the SMA and price data
    ax2 = ax1.twinx()
    # Plot SMA5, SMA25, and close prices
    ax2.plot(myData.index, SMA5_series, color='red', label='SMA5')
    ax2.plot(myData.index, SMA25_series, color='green', label='SMA25')
    ax2.plot(myData.index, Bollinger_H_series, color='purple', label='Bollinger')
    ax2.plot(myData.index, Bollinger_L_series, color='purple', label='Bollinger')
    ax2.plot(myData.index, myData['close'], color='black', label='Close')
    ax2.set_ylabel('Price Indicators', color='black')
    ax2.tick_params(axis='y', labelcolor='black')
    # Create a separate axis for RSI
    fig, ax3 = plt.subplots(figsize=(12, 4))  # Create a separate figure for RSI
    # Plot RSI on separate axis
    ax3.plot(myData.index, RSI_series, color='blue', label='RSI')
    ax3.set_ylabel('RSI', color='blue')
    ax3.tick_params(axis='y', labelcolor='blue')
    # Combine legends from both axes
    lines2, labels2 = ax2.get_legend_handles_labels()
    lines3, labels3 = ax3.get_legend_handles_labels()
    ax2.legend(lines2, labels2, loc='upper left')  # Only show legend for SMA and price data
    ax3.legend(lines3, labels3, loc='upper left')  # Show legend for RSI
    # Improve layout to make room for rotated x-axis labels
    plt.tight_layout()  # This might help to avoid clipping of labels
    plt.show()

    

        
welcome()

myAccount, ib = boot_IB()
config = get_config()
contract = get_contract(config)

detect_trigger(config,ib,contract)



#SMA5_series, SMA25_series, RSI_series, Bollinger_H_series, Bollinger_L_series, myData = get_parameters(ib,config)
#plot_indicators(SMA5_series, SMA25_series, RSI_series, myData, Bollinger_H_series, Bollinger_L_series)