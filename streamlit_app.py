import streamlit as st
from binance.client import Client
import config
import pprint
import streamlit as st
import psycopg2
import psycopg2.extras
import os
import pandas as pd
import time
import numpy as np
import datetime, pytz
from sklearn import preprocessing
import matplotlib.pyplot as plt
import altair as alt
from coinmarketcapapi import CoinMarketCapAPI, CoinMarketCapAPIError #pip install python-coinmarketcap
from bokeh.plotting import figure as bofig
import pickle
from st_aggrid import AgGrid
from st_aggrid.grid_options_builder import GridOptionsBuilder  # pip install streamlit-aggrid

refreshServer = True

pathFiles = '//DISKSTATION/home/scripts/python/python scripts/streamlit scripts/'

def intersection(lst1, lst2):
    lst3 = [value for value in lst1 if value in lst2]
    return lst3


# recuperation du mode (croisé ou isolé) sur la position en cours:
#1
# futures_leverage_bracket(symbol) ==> Cette fonction permet de determiner le "maint_lookup_table"
# https://python-binance.readthedocs.io/en/latest/binance.html?highlight=Leverage%20Brackets#binance.client.Client.futures_leverage_bracket
# https://binance-docs.github.io/apidocs/futures/en/#notional-and-leverage-brackets-user_data
# response:
# {
#     "symbol": "ETHUSDT",
#     "brackets": [
#         {
#             "bracket": 1,
#             "initialLeverage": 75,
#             "notionalCap": 10000,
#             "notionalFloor": 0,
#             "maintMarginRatio": 0.0065,
#             "cum":0
#         },
#     ]
# }


#2
# client.futures_change_leverage(symbol='BTCUSDT',leverage=3)
# Response:
# {
#     "leverage": 21,
#     "maxQty": "1000",  // maximum quantity of base asset
#     "symbol": "BTCUSD_200925"
# }

#2.5
# futures_change_margin_type(symbol='BTCUSDT',marginType='ISOLATED')


#3
# get_symbol_info(symbol)
# {
#     "symbol": "ETHBTC",
#     "status": "TRADING",
#     "baseAsset": "ETH",
#     "baseAssetPrecision": 8,
#     "quoteAsset": "BTC",
#     "quotePrecision": 8,
#     "orderTypes": ["LIMIT", "MARKET"],
#     "icebergAllowed": false,
#     "filters": [
#         {
#             "filterType": "PRICE_FILTER",
#             "minPrice": "0.00000100",
#             "maxPrice": "100000.00000000",
#             "tickSize": "0.00000100"
#         }, {
#             "filterType": "LOT_SIZE",
#             "minQty": "0.00100000",
#             "maxQty": "100000.00000000",
#             "stepSize": "0.00100000"
#         }, {
#             "filterType": "MIN_NOTIONAL",
#             "minNotional": "0.00100000"
#         }
#     ]
# }


# 4
# client.futures_account()
#
# {'feeTier': 0, 'canTrade': True, 'canDeposit': True, 'canWithdraw': True, 'updateTime': 0, 'totalInitialMargin': '0.00000000', 'totalMaintMargin': '0.00000000', 'totalWalletBalance': '73.98141976', 'totalUnrealizedProfit': '0.00000000', 'totalMarginBalance': '73.98141976', 'totalPositionInitialMargin': '0.00000000', 'totalOpenOrderInitialMargin': '0.00000000', 'totalCrossWalletBalance': '73.98141976', 'totalCrossUnPnl': '0.00000000', 'availableBalance': '73.98141976', 'maxWithdrawAmount': '73.98141976',
# 'assets': [{'asset': 'BNB', 'walletBalance': '0.04949536', 'unRealizedProfit': '0.00000000', 'marginBalance': '0.04949536', 'maintMargin': '0.00000000', 'initialMargin': '0.00000000', 'positionInitialMargin': '0.00000000', 'openOrderInitialMargin': '0.00000000', 'maxWithdrawAmount': '0.04949536', 'crossWalletBalance': '0.00000000', 'crossUnPnl': '0.00000000', 'availableBalance': '0.00000000', 'marginAvailable': False, 'updateTime': 1618114591045}, {'asset':

# 5
# liste des symboles existants en futures + balances
# client.futures_position_information()
if refreshServer:
    client = Client(config.API_KEY, config.API_SECRET)

# symbol = st.text_input("Symbol:", "BTCUSDT")
# #st.write(client.get_symbol_info(symbol))
# print(symbol)

def getClientOrderIDFromOrders(orders, orderId):
    res = ''
    for order in orders:
        if order['orderId'] == orderId:
            res = order['clientOrderId']
            break
    return res

def getPNL(client):
    positions = client.futures_position_information()
    pos = []
    pnl = 0
    for position in positions:
        if float(position['positionAmt']) != 0.0:
            pos.append(position)
            pnl = pnl + float(position['unRealizedProfit'])

    return round(pnl,2)

def get_market_ticker_price(client, ticker_symbol):
    '''
    Get ticker price of a specific coin
    '''
    for ticker in client.get_symbol_ticker():
        if ticker[u'symbol'] == ticker_symbol:
            return float(ticker[u'price'])
    return None

def getOrderClientIdFromPosition(symbol, position, orders):
    res = ""
    for order in orders:
        if order['symbol'] == symbol and position['positionAmt'] == order['origQty'] and order['status'] == 'FILLED':
            res = order['clientOrderId']
            #print('orderidtime {} :{}'.format(symbol, order['time']))
            break
    return res


def getEntryTimeFromTrade(trades, orderId):
    res = datetime.datetime(2021,1,1,1,1,1) # a changer plus tard ==> lorsque on depasse les 500 orders, on ne trouve pas la date d'entrée dans la position.
    for trade in trades:
        if trade['orderId'] == orderId:
            res = int(trade['time'])

    return res

def getEntryTimeForPosition(orders, position, position_side, trades):
    entryDate = datetime.datetime(2021,1,1,1,1,1) # a changer plus tard ==> lorsque on depasse les 500 orders, on ne trouve pas la date d'entrée dans la position.
    for order in orders:
        if order['symbol'] == position['symbol'] and position_side == order['side'] and order['status']=='FILLED':
            if order['type'] == 'LIMIT':
                entryDate = datetime.datetime.fromtimestamp(float(getEntryTimeFromTrade(trades, order['orderId']))/1000)
            else:
                entryDate = datetime.datetime.fromtimestamp(float(order['time'])/1000)
            break

    return entryDate

def get_balance_value(json_object, name):
        return [obj for obj in json_object if obj['asset']==name][0]['balance']


#futures_balance = round(float(client.futures_account_balance()[1]['balance']),2)

if refreshServer:
    bal_JSON = client.futures_account_balance()    
    futures_balance = round(float(get_balance_value(bal_JSON,'USDT')),2)

    pnl = getPNL(client)

    st.header("Balance Futures: " + str(futures_balance) + " $")
    st.write('PNL: {} ({})'.format(round(futures_balance+float(pnl),2),pnl))
page_to_display = st.sidebar.selectbox("Page to Display", ('analysis2','analysis', 'strategies', 'stats futures', 'test binance API', 'positions ouvertes', 'ordres ouverts', 'ordres symbole','tous les ordres','STD sur valeurs brutes', 'test cmc api', 'get klines', 'delete orphan orders', 'graph analysis - futures bot', 'trades'),0)

if page_to_display =='stats futures':
    df_stat_filename = './binance_trading/df_stats.pck'

    #initialisation des stats
    if os.path.exists(df_stat_filename):
        df_stats = pd.read_pickle(df_stat_filename)
    else:
        df_stats = pd.DataFrame()

    #st.write(df_stats)
    #df_display = df_stats[['datetime'],['avg'],['mean'],['pnl'],['bal.USDT']].copy()

    #df_display = df_stats['avg'].copy()

    # x = df_stats.values #returns a numpy array
    # min_max_scaler = preprocessing.MinMaxScaler(feature_range=(-1, 1))
    # x_scaled = min_max_scaler.fit_transform(x)

    # #df_normalized= pd.DataFrame(x_scaled, columns={'datetime','avg','mean','pnl','bal.USDT'})
    # df_normalized= pd.DataFrame(x_scaled, columns=df_stats.columns)


    # for col in df_stats.columns:
    #     # if float(col.find('avg'))>-1:
    #     #     df_chart = pd.append(df_normalized[col])
    #     if float(col.find('USDT'))>-1:
    #         df_stats = df_stats.drop(col,axis=1)
    #     # if float(col.find('close'))>-1:
    #     #     df_chart = df_normalized.drop(df_normalized[col],axis=1)
    #     # if float(col.find('open'))>-1:
    #     #     df_chart = df_normalized.drop(df_normalized[col],axis=1)
    #     # if float(col.find('USDT'))>-1:
    #     #     df_chart = df_normalized.drop(df_normalized[col],axis=1)



    # st.line_chart(df_normalized)

    # st.line_chart(df_stats[['avg'],['mean']].values) #,['mean'],['pnl'],['bal.USDT']])
    st.line_chart(df_stats['mean'])
    st.line_chart(df_stats['nbpositions'])
    # st.line_chart(df_stats['avg'])
    st.line_chart(df_stats['pnl'])
    st.line_chart(df_stats['bal.USDT'])

    # st.line_chart(df_stats['force_PT'])






if page_to_display =='analysis':
    nbTradesForAnalysis = 200


    # besoinde récuperer tous les orders pour retrouver l'entrytime d'une position
    orders = client.futures_get_all_orders()
    orders = sorted(orders , key = lambda item:float(item['time']),reverse = True)

    ordersSorted = orders


    trades = client.futures_account_trades(limit=1000)
    tradesSorted = sorted(trades , key = lambda item:float(item['time']),reverse = True)

    #Position ouvertes
    positions = client.futures_position_information()
    poss = []
    pnl = 0
    for position in positions:
        pos = {}
        if float(position['positionAmt']) != 0.0:

            if float(position['positionAmt']) > 0:
                position_side = 'BUY'
            else:
                position_side = 'SELL'
            entryTime = getEntryTimeForPosition(orders, position, position_side, trades)


            pos['symbol'] = position['symbol']
            pos['date'] = entryTime.strftime('%d/%m %H:%M')                  #datetime.datetime.fromtimestamp(int(position['updateTime'])/1000).strftime('%d/%m %H:%M')
            pos['pnl'] = round(float(position['unRealizedProfit']),3)
            pos['size'] = position['positionAmt']
            pos['price'] = position['entryPrice']
            pos['liquidationPrice'] = position['liquidationPrice']
            pos['leverage'] = position['leverage']
            pos['magic'] = getOrderClientIdFromPosition(position['symbol'], position, orders)
            poss.append(pos)

    st.write('Positions ouvertes')
    # st.table(poss, poss.styler.color_negative_red())
    #poss['date'] = datetime.datetime.strptime(poss['date'], '%d/%m/%y %H:%M:%S')



    poss = sorted(poss , key = lambda item:datetime.datetime.strptime(item['date'], '%d/%m %H:%M'),reverse = True)
    st.table(poss)

    #Ordres ouvert
    ordersList = client.futures_get_open_orders()
    orders = []

    for orderElement in ordersList:
        order = {}
        if float(orderElement['origQty']) != 0.0 and orderElement['type']=='LIMIT':
            order['symbol'] = orderElement['symbol']
            order['date'] = datetime.datetime.fromtimestamp(int(orderElement['time'])/1000).strftime('%d/%m %H:%M')
            order['size'] = orderElement['origQty']
            order['price'] = orderElement['price']
            order['status'] = orderElement['status']
            order['type'] = orderElement['type']
            order['side'] = orderElement['side']
            order['magic'] = orderElement['clientOrderId']
            orders.append(order)

    st.write('Ordres LIMIT ouverts')
    st.table(orders)



    # Trades
    trades = client.futures_account_trades()

    #st.write(trades)

    tradesSorted = sorted(trades , key = lambda item:float(item['time']),reverse = True)[:nbTradesForAnalysis]

    trades = []
    bnbinusdt = get_market_ticker_price(client, 'BNBUSDT')
    for trade in tradesSorted:
        commission = -100000
        pos={}
        pos['symbol'] = trade['symbol']
        pos['date'] = datetime.datetime.fromtimestamp(int(trade['time'])/1000).strftime('%d/%m %H:%M')
        comm = trade['commission']
        if trade['commissionAsset'] == 'BNB':
            commission = - float(comm) * bnbinusdt
        else:
            commission = - float(comm)
        if trade['buyer'] == True:
            pos['I/O'] = 'in'
            pos['side'] = trade['side']
        else:
            pos['I/O'] = 'out'
            pos['pnl'] = float(trade['realizedPnl']) + commission
            pos['realized'] = float(trade['realizedPnl'])
        pos['commission'] = commission
        pos['size'] = trade['qty']
        pos['price'] = trade['price']
        pos['ClientOrderId'] = getClientOrderIDFromOrders(ordersSorted, trade['orderId'])


        # >>> d.strftime("%d/%m/%y")
        # '11/03/02'
        # >>> d.strftime("%A %d. %B %Y")
        # 'Monday 11. March 2002'


        trades.append(pos)
    st.write(trades)

    positions = []
    two_out_for_one_in = False
    sizeTemp_first_out = 0
    realizedTemp_first_out = 0
    commTemp_first_out = 0
    for i in range(0,len(trades)):
        position = {}
        #st.write(trades[i]['I/O'])

        # cas ou on a detecté 2 out dans la boucle précendente
        if two_out_for_one_in:
            two_out_for_one_in = False
            if trades[i]['I/O'] == 'out':
                for j in range(i,len(trades)):
                    fixed = False
                    if trades[j]['I/O'] == 'in' and trades[j]['symbol'] == trades[i]['symbol']:
                        if float(trades[j]['size']) == float(trades[i]['size']) + sizeTemp_first_out:
                            position['symbol'] = trades[i]['symbol']
                            position['ouv.'] = trades[j]['date']
                            position['ferm.'] = trades[i]['date']
                            position['MA'] = trades[j]['ClientOrderId']
                            position['price o'] = trades[j]['price']
                            position['price f'] = trades[i]['price']
                            position['pnl'] = round(trades[i]['pnl'] + float(trades[j]['commission']),3)  + realizedTemp_first_out + commTemp_first_out
                            position['realized'] = round(float(trades[i]['realized']),3) + realizedTemp_first_out
                            position['commission'] = round(float(trades[i]['commission']) + float(trades[j]['commission']),3) + commTemp_first_out
                            position['size'] = trades[j]['size']

                            break
                        else:
                            for k in range(j,len(trades)):
                                if trades[k]['I/O'] == 'in' and trades[k]['symbol'] == trades[i]['symbol']:
                                    if float(float(trades[k]['size']) + float(trades[j]['size'])) == float(trades[i]['size']) + sizeTemp_first_out:
                                        position['symbol'] = trades[i]['symbol']
                                        position['ouv.'] = trades[j]['date']
                                        position['ferm.'] = trades[i]['date']
                                        position['MA'] = trades[j]['ClientOrderId']
                                        position['price o'] = trades[j]['price']
                                        position['price f'] = trades[i]['price']
                                        position['pnl'] = round(trades[i]['pnl'] + float(trades[j]['commission']) + float(trades[k]['commission']),3)
                                        position['realized'] = round(float(trades[i]['realized']),3)
                                        position['commission'] = round(float(trades[i]['commission']) + float(trades[j]['commission'])+ float(trades[k]['commission']),3)
                                        position['size'] = trades[i]['size']

                                        fixed = True
                                        break
                                # else:
                                #     #le cas ou il y a 2 out
                                #     # position['symbol'] = trades[i]['symbol']
                                #     # position['ouv.'] = trades[j]['date']
                                #     # position['pnl'] = 'PROBLEME'
                    if fixed:
                        break
                sizeTemp_first_out = 0
                realizedTemp_first_out = 0
                commTemp_first_out = 0
                positions.append(position)
        # cas nominal
        else:
            if trades[i]['I/O'] == 'out':
                for j in range(i,len(trades)):
                    fixed = False
                    if trades[j]['I/O'] == 'in' and trades[j]['symbol'] == trades[i]['symbol']:
                        if trades[j]['size'] == trades[i]['size']:
                            position['symbol'] = trades[i]['symbol']
                            position['ouv.'] = trades[j]['date']
                            position['ferm.'] = trades[i]['date']
                            position['MA'] = trades[j]['ClientOrderId']
                            position['price o'] = trades[j]['price']
                            position['price f'] = trades[i]['price']
                            position['pnl'] = round(trades[i]['pnl'] + float(trades[j]['commission']),3)
                            position['realized'] = round(float(trades[i]['realized']),3)
                            position['commission'] = round(float(trades[i]['commission']) + float(trades[j]['commission']),3)
                            position['size'] = trades[i]['size']

                            break
                        else:
                            for k in range(j,len(trades)):
                                if trades[k]['I/O'] == 'in' and trades[k]['symbol'] == trades[i]['symbol']:
                                    if float(float(trades[k]['size']) + float(trades[j]['size'])) == float(trades[i]['size']):
                                        position['symbol'] = trades[i]['symbol']
                                        position['ouv.'] = trades[j]['date']
                                        position['ferm.'] = trades[i]['date']
                                        position['MA'] = trades[j]['ClientOrderId']
                                        position['price o'] = trades[j]['price']
                                        position['price f'] = trades[i]['price']
                                        position['pnl'] = round(trades[i]['pnl'] + float(trades[j]['commission']) + float(trades[k]['commission']),3)
                                        position['realized'] = round(float(trades[i]['realized']),3)
                                        position['commission'] = round(float(trades[i]['commission']) + float(trades[j]['commission'])+ float(trades[k]['commission']),3)
                                        position['size'] = trades[i]['size']

                                        fixed = True
                                        break
                                else:
                                    #le cas ou il y a 2 out
                                    two_out_for_one_in = True
                                    sizeTemp_first_out = float(trades[i]['size'])
                                    realizedTemp_first_out = round(float(trades[i]['realized']),3)
                                    commTemp_first_out = round(float(trades[i]['commission']),3)

                                    # position['symbol'] = trades[i]['symbol']
                                    # position['ouv.'] = trades[j]['date']
                                    #position['pnl'] = 'PROBLEME
                                    #st.write(trades[i]['symbol'], trades[i]['date'],i)
                                    break
                    if fixed:
                        break
                    if two_out_for_one_in:
                        break

                if not two_out_for_one_in:
                    #st.write(trades[i]['symbol'], trades[i]['date'],trades[i]['I/O'],i)
                    positions.append(position)

    st.write('Trades passés')
    st.table(positions)

    st.table(trades)






    # 'buyer' = true, lors de l'entrée / buyer = false, lors de la sortie
    # une position (entree ou sortie) splittéé en plusieurs ordre (qty differentes) a le meme 'orderId'

    #    [ {
    #   "symbol": "MATICUSDT",
    #   "id": 35374068,
    #   "orderId": 9816170599,
    #   "side": "BUY",
    #   "price": "0.58738",
    #   "qty": "14",
    #   "realizedPnl": "0",
    #   "marginAsset": "USDT",
    #   "quoteQty": "8.22332",
    #   "commission": "0.00000520",
    #   "commissionAsset": "BNB",
    #   "time": 1619523225916,
    #   "positionSide": "BOTH",
    #   "buyer": true,
    #   "maker": false
    # },...]


    # positions = client.futures_position_information()
    # pos = []
    # pnl = 0
    # for position in positions:
    #     if float(position['positionAmt']) != 0.0:
    #         pos.append(position)
    #         pnl = pnl + float(position['unRealizedProfit'])
    # st.write(page_to_display, ': nb: ',len(pos))
    # st.write('PnL: ',round(pnl,2), ' $')
    # st.write(pos)
    
    
def getTSSuivantTrade(symb, TS, trades):
    suivTS = datetime.datetime.now().timestamp() * 1000
#     suivTS = 0
    # on assume que la liste est ordonné et part du plus recent
    for trade in trades:
        if trade['symbol'] == symb:
#             st.write('---- TS:{} / TSiteration:{} / suivTS:{}'.format(tsFormat(TS), tsFormat(trade['TS']), tsFormat(suivTS)))
            if trade['TS'] > TS:
                suivTS = trade['TS']
            else:
                break
    return suivTS
    
def getListOfOrdersId(symb, TS, TS_trade_suiv, in_out, trades):
    orderIdList = []
    
    for trade in trades:
        if trade['symbol'] == symb and trade['TS'] > TS and trade['TS'] < TS_trade_suiv:
#             st.write('{}/{} / TSout: {} / TSin maintenant: {}  / TSin suivant:{}'.format(trade['symbol'], trade['orderId'], tsFormat(trade['TS']), tsFormat(TS), tsFormat(TS_trade_suiv)))
            orderIdList.append(trade['orderId'])
    return orderIdList

def tsFormat(TS):
    return datetime.datetime.fromtimestamp(int(TS)/1000).strftime('%d/%m %H:%M')


def getTF(MA):
    myString = MA.split('_')
    if myString[0] == 'MA':
        return myString[2]
    else:
        return None
    
def getMagic(MA):
    myString = MA.split('_')
    if myString[0] == 'MA':
        return myString[1]
    elif myString[0] == 'MAN':
        return myString[0]
    else:
        return None
    
#     if MA.find('MA_') > 0:
        #dans ce cas, la TF est entre les 2 et 3 _
        
        
        

if page_to_display =='analysis2':

    
    nbTradesForAnalysis = 200

    if refreshServer:
        # besoinde récuperer tous les orders pour retrouver l'entrytime d'une position
        orders = client.futures_get_all_orders(limit=1000)
        
        with open(pathFiles+'orders.pck', 'wb') as f:
            pickle.dump(orders, f)
    else:
        with open(pathFiles+'orders.pck', 'rb') as f:
            orders = pickle.load(f)

        
    orders = sorted(orders , key = lambda item:float(item['time']),reverse = True)
    ordersSorted = orders

    
    if refreshServer:
        trades = client.futures_account_trades(limit=1000)
        
        with open(pathFiles+'trades.pck', 'wb') as f:
            pickle.dump(trades, f)
    else:
        with open(pathFiles+'trades.pck', 'rb') as f:
            trades = pickle.load(f)
           
        
    tradesSorted = sorted(trades , key = lambda item:float(item['time']),reverse = True)

    if refreshServer:
        #Position ouvertes
        positions = client.futures_position_information(limit=1000)
        with open(pathFiles+'positions.pck', 'wb') as f:
            pickle.dump(positions, f)
    else:
        with open(pathFiles+'positions.pck', 'rb') as f:
            positions = pickle.load(f)
    
    
    poss = []
    pnl = 0
    for position in positions:
        pos = {}
        if float(position['positionAmt']) != 0.0:

            if float(position['positionAmt']) > 0:
                position_side = 'BUY'
            else:
                position_side = 'SELL'
            entryTime = getEntryTimeForPosition(orders, position, position_side, trades)


            pos['symbol'] = position['symbol']
            pos['date'] = entryTime.strftime('%d/%m %H:%M')                  #datetime.datetime.fromtimestamp(int(position['updateTime'])/1000).strftime('%d/%m %H:%M')
            pos['pnl'] = round(float(position['unRealizedProfit']),3)
            pos['size'] = position['positionAmt']
            pos['price'] = position['entryPrice']
            pos['liquidationPrice'] = position['liquidationPrice']
            pos['leverage'] = position['leverage']
            pos['magic'] = getOrderClientIdFromPosition(position['symbol'], position, orders)
            poss.append(pos)

    st.write('Positions ouvertes')
    # st.table(poss, poss.styler.color_negative_red())
    #poss['date'] = datetime.datetime.strptime(poss['date'], '%d/%m/%y %H:%M:%S')



    poss = sorted(poss , key = lambda item:datetime.datetime.strptime(item['date'], '%d/%m %H:%M'),reverse = True)
    st.table(poss)

    if refreshServer:
        #Ordres ouvert
        ordersList = client.futures_get_open_orders(limit=1000)
        with open(pathFiles+'ordersList.pck', 'wb') as f:
            pickle.dump(ordersList, f)
    else:
        with open(pathFiles+'ordersList.pck', 'rb') as f:
            ordersList = pickle.load(f)
    
    
    
    orders = []

    for orderElement in ordersList:
        order = {}
        if float(orderElement['origQty']) != 0.0 and orderElement['type']=='LIMIT':
            order['symbol'] = orderElement['symbol']
            order['date'] = datetime.datetime.fromtimestamp(int(orderElement['time'])/1000).strftime('%d/%m %H:%M')
            order['size'] = orderElement['origQty']
            order['price'] = orderElement['price']
            order['status'] = orderElement['status']
            order['type'] = orderElement['type']
            order['side'] = orderElement['side']
            order['magic'] = orderElement['clientOrderId']
            orders.append(order)

    st.write('Ordres LIMIT ouverts')
    st.table(orders)


    if refreshServer:
        # Trades
        trades = client.futures_account_trades(limit=1000)
        with open(pathFiles+'trades.pck', 'wb') as f:
            pickle.dump(trades, f)
    else:
        with open(pathFiles+'trades.pck', 'rb') as f:
            trades = pickle.load(f) 
    #st.write(trades)

    tradesSorted = sorted(trades , key = lambda item:float(item['time']),reverse = True)[:nbTradesForAnalysis]

    trades = []
    tradesIn = []
    tradesOut = []
    if refreshServer:
        bnbinusdt = get_market_ticker_price(client, 'BNBUSDT')
    else:
        bnbinusdt = 660
    for trade in tradesSorted:
        commission = -100000
        pos={}
        pos['symbol'] = trade['symbol']
        pos['date'] = datetime.datetime.fromtimestamp(int(trade['time'])/1000).strftime('%d/%m %H:%M')
        pos['TS'] = trade['time']
        comm = trade['commission']
        if trade['commissionAsset'] == 'BNB':
            commission = - float(comm) * bnbinusdt
        else:
            commission = - float(comm)
        if trade['buyer'] == True:
            pos['I/O'] = 'in'
            pos['side'] = trade['side']
        else:
            pos['I/O'] = 'out'
            pos['pnl'] = float(trade['realizedPnl']) + commission
            pos['realized'] = float(trade['realizedPnl'])
        pos['commission'] = commission
        pos['size'] = trade['qty']
        pos['price'] = trade['price']
        pos['orderId'] = trade['orderId']
        pos['ClientOrderId'] = getClientOrderIDFromOrders(ordersSorted, trade['orderId'])


        # >>> d.strftime("%d/%m/%y")
        # '11/03/02'
        # >>> d.strftime("%A %d. %B %Y")
        # 'Monday 11. March 2002'

        if pos['I/O'] == 'in':
            tradesIn.append(pos)
        else:
            tradesOut.append(pos)
        trades.append(pos)
#     st.table(tradesIn[:10])

#     st.write(trades[0], trades[1])


    cpt_doublon = 0
    # suppression des doublons de tradeIn
#     tradesInWithoutDoublon = []
    for trade in tradesIn:
        orderId = trade['orderId']
        TS = trade['TS']
        
        TSdoublon = [obj for obj in tradesIn if obj['orderId']==orderId and obj['TS']!=TS] #[0]['TS']
        
        if len(TSdoublon) > 0:
#             st.write('-------> {} '.format(TSdoublon))
            
            trade['commission'] = float(trade['commission']) + float(TSdoublon[0]['commission'])
            trade['size'] =float(trade['size']) + float(TSdoublon[0]['size']) 
            
            tradesIn.pop(cpt_doublon+1)
        
        cpt_doublon = cpt_doublon +1
            
#         else:
#             tradesInWithoutDoublon.append(trade)
# #         [obj for obj in tradesOut if obj['orderId']==orderId][0]['size']

#     tradesIn = tradesInWithoutDoublon
    
    
    results = []

    for tradeIn in tradesIn:
        result = {}
#         if tradeIn['symbol'] == 'NKNUSDT':
#         st.write('-------------')
        TSSuivantTradeIn = getTSSuivantTrade(tradeIn['symbol'], tradeIn['TS'], tradesIn)
        tradesOutOrderIdsList = getListOfOrdersId(tradeIn['symbol'], tradeIn['TS'], TSSuivantTradeIn, 'out', tradesOut)
#         st.write('{} / orderId: {} / TSin: {} / TSSuivant: {} / listOutOrders: {}'.format(tradeIn['symbol'], tradeIn['orderId'], tsFormat(tradeIn['TS']), tsFormat(TSSuivantTradeIn), tradesOutOrderIdsList))
        sizeOut = 0.0
        pnlOut = 0.0
        tsFerm = 0
        highestPriceF = 0.0
        
        
        for orderId in tradesOutOrderIdsList:
            size = [obj for obj in tradesOut if obj['orderId']==orderId][0]['size']
            sizeOut = sizeOut + float(size)
            
            pnl = [obj for obj in tradesOut if obj['orderId']==orderId][0]['pnl']
            pnlOut = pnlOut + float(pnl)
            
            ts = [obj for obj in tradesOut if obj['orderId']==orderId][0]['TS']
            tsFerm = max(ts, tsFerm)
            
            priceTemp = [obj for obj in tradesOut if obj['orderId']==orderId][0]['price']
            highestPriceF = max(highestPriceF, float(priceTemp))
            
        pnlOut = round(pnlOut,2)
        
#         st.write('sizeOut {} / pnlOut {} / tsFerm {}'.format(sizeOut, pnlOut, tsFormat(tsFerm)))

#        if True or float(sizeOut) == float(tradeIn['size']):
#        if float(sizeOut) == float(tradeIn['size']):
        if float(sizeOut) > 0:            
            result['symb'] = tradeIn['symbol']
            result['ouv'] = str(tsFormat(tradeIn['TS']))
            result['ferm'] = str(tsFormat(tsFerm))
#             result['MA'] = tradeIn['ClientOrderId']
            result['magic'] = getMagic(tradeIn['ClientOrderId'])
            result['TF'] = getTF(tradeIn['ClientOrderId'])
            result['pnl'] = round (pnlOut - float(tradeIn['commission']),2)
            result['sizeIn'] = round(float(tradeIn['size']),2)
            result['sizeOut'] = round(sizeOut,2)
            result['price O'] = tradeIn['price']
            result['price F'] = highestPriceF
            results.append(result)
        else:
            if sizeOut > 0:
                st.write('Erreur {} / orderIdIn {}, sizeIn {} / sizeOut {} / Dates {} --> {}'.format(tradeIn['symbol'],tradeIn['orderId'], tradeIn['size'],sizeOut, tsFormat(tradeIn['TS']), tsFormat(tsFerm)))
                
#     st.table(tradesOut)
        


#     st.table(results)
    
    st.write('Trades passés')
    
    
    df = pd.DataFrame(data=results)
    


    # add this
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_pagination(enabled=False)
    gridOptions = gb.build()

    AgGrid(df, gridOptions=gridOptions)
    
    
    
    
    
    
    
    
    
#     
#     tradesSymbol = []
#     for trade in trades:
#          if trade['symbol'] == 'ICXUSDT':
#              tradesSymbol.append(trade)
#     
#     st.table(tradesSymbol)

    positions = []
    two_out_for_one_in = False
    sizeTemp_first_out = 0
    realizedTemp_first_out = 0
    commTemp_first_out = 0
    for i in range(0,len(trades)):
        position = {}
        #st.write(trades[i]['I/O'])

        # cas ou on a detecté 2 out dans la boucle précendente
        if two_out_for_one_in:
            two_out_for_one_in = False
            if trades[i]['I/O'] == 'out':
                for j in range(i,len(trades)):
                    fixed = False
                    if trades[j]['I/O'] == 'in' and trades[j]['symbol'] == trades[i]['symbol']:
                        if float(trades[j]['size']) == float(trades[i]['size']) + sizeTemp_first_out:
                            position['symbol'] = trades[i]['symbol']
                            position['ouv.'] = trades[j]['date']
                            position['ferm.'] = trades[i]['date']
                            position['MA'] = trades[j]['ClientOrderId']
                            position['price o'] = trades[j]['price']
                            position['price f'] = trades[i]['price']
                            position['pnl'] = round(trades[i]['pnl'] + float(trades[j]['commission']),3)  + realizedTemp_first_out + commTemp_first_out
                            position['realized'] = round(float(trades[i]['realized']),3) + realizedTemp_first_out
                            position['commission'] = round(float(trades[i]['commission']) + float(trades[j]['commission']),3) + commTemp_first_out
                            position['size'] = trades[j]['size']

                            break
                        else:
                            for k in range(j,len(trades)):
                                if trades[k]['I/O'] == 'in' and trades[k]['symbol'] == trades[i]['symbol']:
                                    if float(float(trades[k]['size']) + float(trades[j]['size'])) == float(trades[i]['size']) + sizeTemp_first_out:
                                        position['symbol'] = trades[i]['symbol']
                                        position['ouv.'] = trades[j]['date']
                                        position['ferm.'] = trades[i]['date']
                                        position['MA'] = trades[j]['ClientOrderId']
                                        position['price o'] = trades[j]['price']
                                        position['price f'] = trades[i]['price']
                                        position['pnl'] = round(trades[i]['pnl'] + float(trades[j]['commission']) + float(trades[k]['commission']),3)
                                        position['realized'] = round(float(trades[i]['realized']),3)
                                        position['commission'] = round(float(trades[i]['commission']) + float(trades[j]['commission'])+ float(trades[k]['commission']),3)
                                        position['size'] = trades[i]['size']

                                        fixed = True
                                        break
                                # else:
                                #     #le cas ou il y a 2 out
                                #     # position['symbol'] = trades[i]['symbol']
                                #     # position['ouv.'] = trades[j]['date']
                                #     # position['pnl'] = 'PROBLEME'
                    if fixed:
                        break
                sizeTemp_first_out = 0
                realizedTemp_first_out = 0
                commTemp_first_out = 0
                positions.append(position)
        # cas nominal
        else:
            if trades[i]['I/O'] == 'out':
                for j in range(i,len(trades)):
                    fixed = False
                    if trades[j]['I/O'] == 'in' and trades[j]['symbol'] == trades[i]['symbol']:
                        if trades[j]['size'] == trades[i]['size']:
                            position['symbol'] = trades[i]['symbol']
                            position['ouv.'] = trades[j]['date']
                            position['ferm.'] = trades[i]['date']
                            position['MA'] = trades[j]['ClientOrderId']
                            position['price o'] = trades[j]['price']
                            position['price f'] = trades[i]['price']
                            position['pnl'] = round(trades[i]['pnl'] + float(trades[j]['commission']),3)
                            position['realized'] = round(float(trades[i]['realized']),3)
                            position['commission'] = round(float(trades[i]['commission']) + float(trades[j]['commission']),3)
                            position['size'] = trades[i]['size']

                            break
                        else:
                            for k in range(j,len(trades)):
                                if trades[k]['I/O'] == 'in' and trades[k]['symbol'] == trades[i]['symbol']:
                                    if float(float(trades[k]['size']) + float(trades[j]['size'])) == float(trades[i]['size']):
                                        position['symbol'] = trades[i]['symbol']
                                        position['ouv.'] = trades[j]['date']
                                        position['ferm.'] = trades[i]['date']
                                        position['MA'] = trades[j]['ClientOrderId']
                                        position['price o'] = trades[j]['price']
                                        position['price f'] = trades[i]['price']
                                        position['pnl'] = round(trades[i]['pnl'] + float(trades[j]['commission']) + float(trades[k]['commission']),3)
                                        position['realized'] = round(float(trades[i]['realized']),3)
                                        position['commission'] = round(float(trades[i]['commission']) + float(trades[j]['commission'])+ float(trades[k]['commission']),3)
                                        position['size'] = trades[i]['size']

                                        fixed = True
                                        break
                                else:
                                    #le cas ou il y a 2 out
                                    two_out_for_one_in = True
                                    sizeTemp_first_out = float(trades[i]['size'])
                                    realizedTemp_first_out = round(float(trades[i]['realized']),3)
                                    commTemp_first_out = round(float(trades[i]['commission']),3)

                                    # position['symbol'] = trades[i]['symbol']
                                    # position['ouv.'] = trades[j]['date']
                                    #position['pnl'] = 'PROBLEME
                                    #st.write(trades[i]['symbol'], trades[i]['date'],i)
                                    break
                    if fixed:
                        break
                    if two_out_for_one_in:
                        break

                if not two_out_for_one_in:
                    #st.write(trades[i]['symbol'], trades[i]['date'],trades[i]['I/O'],i)
                    positions.append(position)

#     st.write('Trades passés')
#     st.table(positions)
#     st.table(trades)






    # 'buyer' = true, lors de l'entrée / buyer = false, lors de la sortie
    # une position (entree ou sortie) splittéé en plusieurs ordre (qty differentes) a le meme 'orderId'

    #    [ {
    #   "symbol": "MATICUSDT",
    #   "id": 35374068,
    #   "orderId": 9816170599,
    #   "side": "BUY",
    #   "price": "0.58738",
    #   "qty": "14",
    #   "realizedPnl": "0",
    #   "marginAsset": "USDT",
    #   "quoteQty": "8.22332",
    #   "commission": "0.00000520",
    #   "commissionAsset": "BNB",
    #   "time": 1619523225916,
    #   "positionSide": "BOTH",
    #   "buyer": true,
    #   "maker": false
    # },...]


    # positions = client.futures_position_information()
    # pos = []
    # pnl = 0
    # for position in positions:
    #     if float(position['positionAmt']) != 0.0:
    #         pos.append(position)
    #         pnl = pnl + float(position['unRealizedProfit'])
    # st.write(page_to_display, ': nb: ',len(pos))
    # st.write('PnL: ',round(pnl,2), ' $')
    # st.write(pos)    

if page_to_display =='test binance API':
    nbTradesForAnalysis = 200

    st.write('orders = client.futures_get_all_orders()')
    orders = client.futures_get_all_orders()

    ordersSorted = sorted(orders , key = lambda item:float(item['time']),reverse = True)[:nbTradesForAnalysis]
    for order in ordersSorted:
        if order['symbol'] == 'SFPUSDT':
            st.write(order)


    st.write('client.futures_account_trades()')
    trades = client.futures_account_trades()

    tradesSorted = sorted(trades , key = lambda item:float(item['time']),reverse = True)[:nbTradesForAnalysis]
    for trade in tradesSorted:
        if trade['symbol'] == 'SFPUSDT':
            st.write(trade)



    result = client.futures_leverage_bracket()
    #pprint.pprint(result)

    res3 = client.futures_position_information()

    #pprint.pprint(client.futures_account())
    # pprint.pprint(client.futures_account_balance())
    # pprint.pprint(client.futures_change_leverage(symbol='BTCUSDT',leverage=3))
    # pprint.pprint(client.futures_change_margin_type(symbol='BTCUSDT',marginType='ISOLATED'))

            # C'est normal que ca ne marche pas, c'est les FUTURES COIN et non les FUTURES USDT --> finalement c'est bon puisque ca nous interesse pas.
            # ERROR --> import pprint; pprint.pprint(client.futures_coin_account())
            # ERROR --> pprint.pprint(client.futures_coin_account_balance())
            # ERROR --> pprint.pprint(client.futures_coin_exchange_info())
            # ERROR --> pprint.pprint(client.futures_coin_funding_rate())
            # ERROR --> pprint.pprint(client.futures_coin_position_information(symbol='BTCUSDT'))


    # for symbol in client.futures_position_information():
    #      print(symbol)

    x= client.futures_exchange_info()
    #pprint.pprint(x)

    st.write('client.get_all_tickers()')
    st.write(client.get_all_tickers())


    palmares = client.get_ticker()
    st.write('client.get_ticker()')
    st.write(palmares)

    st.write('Resultat:')
    st.write(max(palmares,key=lambda item:float(item['priceChangePercent']))['symbol'])
    st.write(max(palmares,key=lambda item:float(item['priceChangePercent'])))

    st.write('Top 10')
    st.write(sorted(palmares , key = lambda item:float(item['priceChangePercent']),reverse = True)[:10])


    st.write('Top 10 losers')
    st.write(sorted(palmares , key = lambda item:float(item['priceChangePercent']),reverse = False)[:10])

    st.write('futures_leverage_bracket')
    st.write(client.futures_leverage_bracket())

if page_to_display =='positions ouvertes':
    positions = client.futures_position_information()
    pos = []
    pnl = 0
    for position in positions:
        if float(position['positionAmt']) != 0.0:
            pos.append(position)
            pnl = pnl + float(position['unRealizedProfit'])
    st.write(page_to_display, ': nb: ',len(pos))
    st.write('PnL: ',round(pnl,2), ' $')
    st.write(pos)

if page_to_display =='ordres ouverts':
    openOrders = client.futures_get_open_orders()
    st.write(page_to_display, ': nb: ',len(openOrders))
    st.write(openOrders)

if page_to_display =='ordres symbole':

    symb = st.text_input('symbol', 'BTCUSDT')

#     df_stat_filename = './binance_trading/df_stats.pck'
#
#     #initialisation des stats
#     if os.path.exists(df_stat_filename):
#         df_stats = pd.read_pickle(df_stat_filename)
#     else:
#         df_stats = pd.DataFrame()
#
#
#     st.line_chart(df_stats['mean'])
#     st.line_chart(df_stats[symb])



    ordersList = client.futures_get_all_orders()

    orders = []

    for orderElement in ordersList:
        order = {}
        if orderElement['symbol'] == symb:
            order['symbol'] = orderElement['symbol']
            order['date'] = datetime.datetime.fromtimestamp(int(orderElement['time'])/1000).strftime('%d/%m %H:%M')
            order['orderId'] = orderElement['orderId']
            order['clientOrderId'] = orderElement['clientOrderId']
            order['size'] = orderElement['origQty']
            order['price'] = orderElement['price']
            order['status'] = orderElement['status']
            order['type'] = orderElement['type']
            order['side'] = orderElement['side']
            orders.append(order)

    st.write('Ordres ouverts pour {}'.format(symb))
    st.table(orders)






if page_to_display =='tous les ordres':

    orders = client.futures_get_all_orders()
    st.write(page_to_display, ': nb: ',len(orders))
    st.write(sorted(orders , key = lambda item:float(item['time']),reverse = True)[:30])
    st.write(orders)



# # EMA_period = 20
# if page_to_display == 'STD sur moyenne':
#     topX = 3
#     EMA_period = 20
#     TIMESLEEP = 4

#     openOrders = client.futures_get_open_orders()
#     orders = client.futures_get_all_orders()
#     positions = client.futures_position_information()
#     pos = []
#     for position in positions:
#         if float(position['positionAmt']) != 0:
#             pos.append(position)

#     positions = pos

#     # INITIALISATION DES LA LISTE DES SYMBOLS à TRADER (strategie de trade pour Magic_1 )
#     connection = psycopg2.connect(host=config.DB_HOST, database=config.DB_NAME_DEV, user=config.DB_USER, password=config.DB_PASS)
#     cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
#     req = "SELECT id, base_asset, symbol FROM stock where futurestrading = true"
#     cursor.execute(req)
#     symbols_futures = cursor.fetchall()


#     json_db = "tops_flops.json"
#     # variable global qui stocke les valeurs des tops flops --> data frame
#     # ajoute de l'EMA 20 à cette data frame
#     # savegarde / load de cette dataframe dans un json


#     palmares = client.get_ticker()

#     symbols = []
#     for symbol_palmares in palmares:
#         for symbol_future in symbols_futures:
#             if symbol_future['symbol'] == symbol_palmares['symbol']:
#                 symbols.append(symbol_palmares)


#     symbols_top = sorted(symbols , key = lambda item:float(item['priceChangePercent']),reverse = True)[:topX]
#     symbols_flop = sorted(symbols , key = lambda item:float(item['priceChangePercent']),reverse = False)[:topX]

#     # pour test, on reduit le nombre de symbol au topX
#     symbols = symbols[:topX]

#     # remplissage de la Dataframe
#     # recuperation des données, si elles existent dans le fichier


#     i=0
#     gainer = []
#     gainerBTCEMA = []
#     df = pd.DataFrame()
#     df3 = pd.DataFrame()
#     df_tmp = pd.DataFrame()

#     if os.path.exists(json_db):
#         df2 = pd.read_json(json_db, lines=True)
#     else:
#         df2 = pd.DataFrame()

#     if len(df2) > 0:
#         for sy in symbols:
#             df3[sy['symbol']+'EMA'] = talib.SMA(df2[sy['symbol']],EMA_period)


#     my_chart_PT = st.line_chart(df2)
#     my_chart_EMA = st.line_chart(df3)
#     while True:

#         # for sy in symbols_top:
#         #     if i>0:
#         #         gainer = df[sy['symbol']]
#         #         gainerEMA = df[sy['symbol']+'EMA']
#         #     gainer = np.append(gainer, float(sy['priceChangePercent']))
#         #     # sum = 0
#         #     # for i in range(0,len(gainerBTC)):
#         #     #     sum = float(gainerBTC[i]) + sum
#         #     # gainerEMA = sum / len(gainerBTC)
#         #     # st.write(sy['priceChangePercent'] + ' ' + str(gainerEMA))
#         #     # gainerBTCEMA.append(gainerEMA)
#         #     gainerEMA = talib.EMA(gainer,5)



#         #     df[sy['symbol']] = gainer
#         #     df[sy['symbol']+'EMA'] = gainerEMA

#         #     gainer = []
#         # i=i+1
#         # st.write(df)

#         # palmares = client.get_ticker()
#         # time.sleep(2)

#         for sy in symbols:
#             gainer = np.append(gainer, float(sy['priceChangePercent']))
#             df[sy['symbol']] = gainer

#             gainer = []
#         #df['index'] = datetime.datetime.now()
#         df2 = df2.append(df, ignore_index=True)




#         for sy in symbols:
#             df_tmp[sy['symbol']+'EMA'] = talib.SMA(df2[sy['symbol']],EMA_period)
#             #st.write(len(df_tmp[sy['symbol']+'EMA']))

#         #st.write(str(len(df2)) + ' ' + str(len(df_tmp)))

#         # st.write(df2.tail(1))
#         # st.write(df_tmp.tail(1))

#         df3 = df3.append(df_tmp.tail(1), ignore_index=True)


#         # for sy in symbols:
#         #     if df2[sy['symbol']].iloc[-1] < 0 and df2[sy['symbol']+'EMA'].iloc[-1] > df2[sy['symbol']].iloc[-1] and df2[sy['symbol']+'EMA'].iloc[-2] < df2[sy['symbol']].iloc[-2]:
#         #         st.write('SELL {} / {} > {}'.format(sy['symbol'], df2[sy['symbol']+'EMA'].iloc[-1],df2[sy['symbol']].iloc[-1]))
#         #     if df2[sy['symbol']].iloc[-1] > 0 and df2[sy['symbol']+'EMA'].iloc[-1] < df2[sy['symbol']].iloc[-1] and df2[sy['symbol']+'EMA'].iloc[-2] > df2[sy['symbol']].iloc[-2]:
#         #         st.write('BUY {} / {} < {}'.format(sy['symbol'], df2[sy['symbol']+'EMA'].iloc[-1],df2[sy['symbol']].iloc[-1]))


#         my_chart_PT.add_rows(df)
#         my_chart_EMA.add_rows(df_tmp.tail(1))

#         #st.write(df3)

#         tail_value = EMA_period+int(round(EMA_period*20,0))


#         x = df3.values #returns a numpy array
#         min_max_scaler = preprocessing.MinMaxScaler()
#         x_scaled = min_max_scaler.fit_transform(x)

#         df_normalized= pd.DataFrame(x_scaled)

#         df_STD = df_normalized.std(axis=1,  skipna = True)
#         #st.write(df_normalized)

#         st.line_chart(df_normalized)
#         st.line_chart(df_STD)



#         df2 = df2.tail(tail_value)
#         df2.to_json(json_db, orient="records", lines=True)

#         df3 = df3.tail(tail_value)

#         #st.write(df2)


#         # gainerEMA = talib.EMA(df2[sy['symbol']],EMA_period)
#         # df[sy['symbol']+'EMA'] = gainerEMA
#         palmares = client.get_ticker()
#         symbols = []
#         for symbol_palmares in palmares:
#             for symbol_future in symbols_futures:
#                 if symbol_future['symbol'] == symbol_palmares['symbol']:
#                     symbols.append(symbol_palmares)


#         # pour test, on reduit le nombre de symbol au topX
#         symbols = symbols[:topX]
#         time.sleep(TIMESLEEP)


def listOfTopFlops(displayStreamlit = False):
    ALL = True          # il faut le laisser a true etant donné qu'on ne genere plus que ce fichier (xxxx_ALL.json)
    topX = 0
    top_buy_sell = 1
    thresold_buy_sell = 0.5
    numberOfRowsToAnalyse = 20              # MAX = 420
    # attention sur le portable fujitsu, json_db = "./../tops_flops_"
    json_db = "./tops_flops_"
    if ALL:
        json_db_file = json_db+'ALL.json'
    else:
        json_db_file = json_db+str(topX)+'.json'

    print(json_db_file)

    # for sy in symbols:
    #     gainer = np.append(gainer, float(sy['priceChangePercent']))
    #     df[sy['symbol']] = gainer

    #     gainer = []
    # #df['index'] = datetime.datetime.now()

    if os.path.exists(json_db_file):
        df_changeSPT = pd.read_json(json_db_file, lines=True)
        #df_changeSPT = df_changeSPT.tail(numberOfRowsToAnalyse)
        if ALL and topX>0:
            #onrecupere d'abord la column USDTUSDT qui est à lafin
            # colUSDT=df_changeSPT['USDTUSDT']
            df_changeSPT = df_changeSPT.iloc[:, : topX]
            # df_changeSPT['USDTUSDT'] = colUSDT
            #st.write(df_changeSPT)

    else:
        return ""


    #print(df_changeSPT)

    # df_changeSPT = df_changeSPT.append(df, ignore_index=True)

    #st.write(df_changeSPT.columns)

    x = df_changeSPT.values #returns a numpy array
    min_max_scaler = preprocessing.MinMaxScaler(feature_range=(-1, 1))
    x_scaled = min_max_scaler.fit_transform(x)

    df_normalized= pd.DataFrame(x_scaled, columns=df_changeSPT.columns)



    #df_STD = df_normalized.std(axis=1,  skipna = True)


    #df_normalized_avg = pd.DataFrame()
    df_normalized['avg'] =  df_normalized.mean(axis = 1, skipna = True)

    # ajout de la colonne 0 qui représente le USDT
    df_normalized['zero'] = 0.0

    # df_STD_0_AVG =  df_normalized[[df_changeSPT.columns[0],'avg']].std(axis=1,  skipna = True)
    # df_STD_1_AVG =  df_normalized[[df_changeSPT.columns[1],'avg']].std(axis=1,  skipna = True)
    # df_STD_2_AVG =  df_normalized[[df_changeSPT.columns[2],'avg']].std(axis=1,  skipna = True)

    df_STD_ind = pd.DataFrame()
    # on reduit la fenetre pour les calculs de la deviation standard
    df_normalized = df_normalized.tail(numberOfRowsToAnalyse)
    # for i in range(0,len(df_changeSPT.columns)):
    #     df_STD_ind[df_changeSPT.columns[i]] =  df_normalized[[df_changeSPT.columns[i],'zero']].std(axis=1,  skipna = True)
    #     deltaLast =  round(df_normalized[df_changeSPT.columns[i]].iloc[-1] - df_normalized['zero'].iloc[-1],2)
    #     if deltaLast <0:
    #         df_STD_ind[df_changeSPT.columns[i]] *= -1


    # pour la représentation dans Streamlit seulement, on fait une copie pour ne pas etre embeté par le *= -1
    df_STD_ind_temp = pd.DataFrame()

    for col in df_changeSPT.columns:
        df_STD_ind[col] =  df_normalized[[col,'zero']].std(axis=1,  ddof=0, skipna = True)
        df_STD_ind_temp = df_STD_ind
        deltaLast =  round(df_normalized[col].iloc[-1] - df_normalized['zero'].iloc[-1],2)
        if deltaLast <0:
            df_STD_ind[col] *= -1

    #tri des colonnes (les symboles) du plus petit au plus grand
    #last_row = df_STD_ind.loc[df_STD_ind.last_valid_index()]
    #lastOrderedListFromBuyToSell = last_row.argsort()

    #msg = lastOrderedListFromBuyToSell

    sorted_df = df_STD_ind.sort_values(df_STD_ind.last_valid_index(), axis=1)

    msg = sorted_df.tail(1)

    top_norm = sorted_df.iloc[:,-top_buy_sell:]
    flop_norm = sorted_df.iloc[:, : top_buy_sell]

    # symbols_top = df_changeSPT[top_norm.columns]
    # symbols_flop = df_changeSPT[flop_norm.columns]



    # on supprime celles qui sont audessus ou au dessous du thresold_buy_sell ==> Il reste à ranger les colonnes df_changeSPT dans l'ordre croissant

    symbols_top = df_changeSPT.drop(columns = sorted_df.columns[sorted_df.iloc[-1].lt(thresold_buy_sell)])
    symbols_flop = df_changeSPT.drop(columns = sorted_df.columns[sorted_df.iloc[-1].gt(-thresold_buy_sell)])


    symbols_top = symbols_top[intersection(symbols_top.columns, top_norm.columns)]
    symbols_flop = symbols_flop[intersection(symbols_flop,flop_norm.columns)]

    if displayStreamlit:
        return df_changeSPT,df_normalized,df_STD_ind_temp,df_changeSPT.columns,symbols_top,symbols_flop,msg
    else:
        return symbols_top,symbols_flop

if page_to_display == 'test cmc api':
    cmc = CoinMarketCapAPI(config.CMC_API_KEY)
    r = cmc.cryptocurrency_listings_latest()
    st.write(r.data)


if page_to_display == 'STD sur valeurs brutes':

    displayTreatments = False
    TIMESLEEP = 15

    if displayTreatments:

        updated_on = st.empty()
        st.write('Valeurs des changements en %')
        my_chart_PT = st.empty()
        st.write('Valeurs des changements en % normés')
        my_chart_NORM = st.empty()
        st.write('Standard Deviation / Max des composantes')
        my_chart_STD = st.empty()

        st.write('Standard Deviation de chacune des composantes par rapport à USDT ')
        my_chart_STD_X_AVG = st.empty()

        st.write('Top')
        my_chart_top = st.empty()
        st.write('Flop')
        my_chart_flop = st.empty()

    while True:
        if not displayTreatments:
            symbols_top,symbols_flop = listOfTopFlops(displayTreatments)

        if displayTreatments:
            df_changeSPT,df_normalized,df_STD_ind_temp,columns,symbols_top,symbols_flop,msg = listOfTopFlops(displayTreatments)

            my_chart_PT.line_chart(df_changeSPT)
            my_chart_NORM.line_chart(df_normalized)

            my_chart_STD_X_AVG.line_chart(df_STD_ind_temp[columns])
            my_chart_top.line_chart(symbols_top)
            my_chart_flop.line_chart(symbols_flop)



            if len(symbols_top.columns) > 0:
                st.write('liste des pair à acheter: {}\n{}'.format(symbols_top.columns,datetime.datetime.now()))
            if len(symbols_flop.columns) > 0:
                st.write('liste des pair à vendre: {}\n{}'.format(symbols_flop.columns,datetime.datetime.now()))

            st.write(msg)

        st.write('{}'.format(datetime.datetime.now()))
        msg = 'achat: '
        for symb in symbols_top.columns:
            msg = msg + symb + ', '
        st.write(msg)
        msg = 'vente: '
        for symb in symbols_flop.columns:
            msg = msg + symb + ', '
        st.write(msg)


        time.sleep(TIMESLEEP)


def get_COMPLETE_klines_binance_direct(client, symb, TF, nbCandleToLoad):
    res = ""
    klines = client.get_klines(symbol=symb,interval=TF,limit=nbCandleToLoad)
    data = pd.DataFrame(klines, columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore' ])

    # cas 1 heure de paris
    timeNow = datetime.datetime.now(tz=pytz.timezone("Europe/Paris"))   #heure de Paris
    data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms', utc=True) # Heure UTC
    data['timestamp'] = data['timestamp'].dt.tz_convert('Europe/Paris') # conversion UTC --> PAris

    # case 2 tout en heure UTC
    #timeNow = datetime.datetime.utcnow()   #heure UTC
    #data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms', utc=True) # Heure UTC
            # pas besoin de conversion mais c'est genant pour la suite ou on risque de melanger UTC et Paris


    data['close_time'] = pd.to_datetime(data['close_time'], unit='ms' , utc=True)
    data['close_time'] = data['close_time'].dt.tz_convert('Europe/Paris') # conversion UTC --> PAris

    st.write(data['timestamp'].iloc[-1], data['close_time'].iloc[-1], timeNow)

    if timeNow > data['timestamp'].iloc[-1] and timeNow < data['close_time'].iloc[-1]:
        data=data[:-1]

    #if timeNow > klines.iloc[-1][0]

    return data


if page_to_display =='get klines':
    klines = get_COMPLETE_klines_binance_direct(client, 'BTCUSDT','5m',5)
    st.write(klines)


if page_to_display == 'delete orphan orders':
    orders = client.futures_get_all_orders()
    st.write(orders)
    positions = client.futures_position_information()
    st.write(positions)
    trades = client.futures_account_trades()
    st.write(trades)

    symbol = 'RVNUSDT'

    for trade in trades:
        if trade['symbol']==symbol:

            for order in orders:
                if order['symbol']==symbol:
                    if trade['orderId'] == order['orderId']:
                        date = datetime.datetime.fromtimestamp(float(trade['time'])/1000)
                        st.write(trade['realizedPnl'], trade['commission'], order['clientOrderId'], date)
                        st.write(datetime.datetime.fromtimestamp(float(order['time'])/1000))
                        st.write(order)
                        st.write(trade)


#
#
#
#     for order in orders:
#         if order['status'] == 'NEW': #opened
#             foundPosition = False
#             for position in positions:
#                 if position['symbol'] == order['symbol'] and float(position['positionAmt']) != 0:
#
#                     # print(position['symbol'])
#                     # pprint.pprint(position)
#                     # pprint.pprint(order)
#
#                     foundPosition = True
#                     break
#             if not foundPosition and ((order['clientOrderId'].find('BUY')>=0 and order['side']=='SELL') or (order['clientOrderId'].find('SELL')>=0 and order['side']=='BUY') or order['clientOrderId']=="") and \
#                     (order['type'] == 'STOP_MARKET' or order['type'] == 'TAKE_PROFIT_MARKET'):
#                 client.futures_cancel_order(symbol=order['symbol'],orderId=order['orderId'])
#                 logger.info('{}: order {} has been cancelled because no position opened or already closed '.format(order['symbol'], order['orderId']))
#             try:
#                 # Cas des ordres limit mis en place et qui ne sont pas declenché, il faut les annnuler au bout de 30minutes ?
#                 now = datetime.datetime.now()
#                 timeOrder = datetime.datetime.fromtimestamp(int(order['time'])/1000)
#                 time_delta = now-timeOrder
#                 delta_in_minutes = time_delta.total_seconds()/60
#                 if order['type']=='LIMIT' and order['status'] == 'NEW' and delta_in_minutes > timeoutLimitOrders and (float(order['clientOrderId'].find(order['side'])) > -1) and float(order['clientOrderId'].find("MAN")) == -1:
#                     client.futures_cancel_order(symbol=order['symbol'],orderId=order['orderId'])
#                     logger.info('{}: LIMIT order {} has been cancelled because of TimeOut of {} min. '.format(order['symbol'], order['orderId'],timeoutLimitOrders))
#

# python3 -m streamlit run test_futures_specific_functions.py




if page_to_display == 'graph analysis - futures bot':
    path = "C:/Users/jsigrist/Downloads"
    filename = "df_statsREF2.pck"

    # load the dataset
    if os.path.exists(path +'/' + filename):

        data = pd.DataFrame()

        df = pd.read_pickle(path +'/' + filename)
        data['B_USDT'] = df['bal.USDT']
        data['Equity'] = data['B_USDT'] + df['pnl']

        data = data.tail(5000)
        data = data.reset_index()

        #st.line_chart(data)
        st.write(data)
        c = alt.Chart(data).mark_line().encode(
            alt.X('datetime'),
            alt.Y('Equity',scale=alt.Scale(domain=(data['Equity'].min(),data['Equity'].max()))),
           # alt.Y('B_USDT',scale=alt.Scale(domain=(120,180)))
        ).interactive()

        d = alt.Chart(data).mark_line().encode(
            alt.X('datetime'),
            alt.Y('B_USDT',scale=alt.Scale(domain=(data['B_USDT'].min(),data['B_USDT'].max()))),
           # alt.Y('B_USDT',scale=alt.Scale(domain=(120,180)))
        ).interactive()

        st.altair_chart(c + d, use_container_width=True)





        np.random.seed(42)
        source = pd.DataFrame(np.cumsum(np.random.randn(100, 3), 0).round(2),
                        columns=['A', 'B', 'C'], index=pd.RangeIndex(100, name='x'))

        source = source.reset_index().melt('x', var_name='category', value_name='y')

        # Create a selection that chooses the nearest point & selects based on x-value
        nearest = alt.selection(type='single', nearest=True, on='mouseover',
                            fields=['x'], empty='none')

        # The basic line
        line = alt.Chart(source).mark_line(interpolate='basis').encode(
        x='x:Q',
        y='y:Q',
        color='category:N'
        )

        # Transparent selectors across the chart. This is what tells us
        # the x-value of the cursor
        selectors = alt.Chart(source).mark_point().encode(
        x='x:Q',
        opacity=alt.value(0),
        ).add_selection(
        nearest
        )

        # Draw points on the line, and highlight based on selection
        points = line.mark_point().encode(
        opacity=alt.condition(nearest, alt.value(1), alt.value(0))
        )

        # Draw text labels near the points, and highlight based on selection
        text = line.mark_text(align='left', dx=5, dy=-5).encode(
        text=alt.condition(nearest, 'y:Q', alt.value(' '))
        )

        # Draw a rule at the location of the selection
        rules = alt.Chart(source).mark_rule(color='gray').encode(
        x='x:Q',
        ).transform_filter(
        nearest
        )

#         # Put the five layers into a chart and bind the data
#         alt.layer(
#         line, selectors, points, rules, text
#         ).properties(
#         width=600, height=300
#         )

        st.altair_chart(line + selectors + points + rules + text, use_container_width=True)






        #data = data.set_index('datetime')

        source = data.reset_index().melt('datetime', var_name='graph', value_name='y')

        st.write(source)

        # Create a selection that chooses the nearest point & selects based on x-value
        nearest = alt.selection(type='single', nearest=True, on='mouseover',
                            fields=['datetime'], empty='none')

        # The basic line
        line = alt.Chart(source).mark_line(interpolate='basis').encode(
        x='datetime:Q',
        y='y:Q',
        color='graph:N'
        )

        # Transparent selectors across the chart. This is what tells us
        # the x-value of the cursor
        selectors = alt.Chart(source).mark_point().encode(
        x='datetime:Q',
        opacity=alt.value(0),
        ).add_selection(
        nearest
        )

        # Draw points on the line, and highlight based on selection
        points = line.mark_point().encode(
        opacity=alt.condition(nearest, alt.value(1), alt.value(0))
        )

        # Draw text labels near the points, and highlight based on selection
        text = line.mark_text(align='left', dx=5, dy=-5).encode(
        text=alt.condition(nearest, 'y:Q', alt.value(' '))
        )

        # Draw a rule at the location of the selection
        rules = alt.Chart(source).mark_rule(color='gray').encode(
        x='datetime:Q',
        ).transform_filter(
        nearest
        )

#         # Put the five layers into a chart and bind the data
#         alt.layer(
#         line, selectors, points, rules, text
#         ).properties(
#         width=600, height=300
#         )

        #st.altair_chart(line + selectors + points + rules + text, use_container_width=True)


        # Generate random data
        x = np.arange(1, 11)
        y = np.random.rand(10)

        # Generate canvas
        fig = bofig(title='Line Chart Example',
             x_axis_label='x',
             y_axis_label='y',
             width=800,
             height=400)

        st.write(fig)






if page_to_display =='trades':

    symb = st.text_input('symbol', 'BTCUSDT')



#     # Trades
    trades = client.futures_account_trades(limit=1000)
    tradesSorted = sorted(trades , key = lambda item:float(item['time']),reverse = True)
#
    # besoinde récuperer tous les orders pour retrouver l'entrytime d'une position
    orders = client.futures_get_all_orders(limit=1000)
    ordersSorted = sorted(orders , key = lambda item:float(item['time']),reverse = True)


#     df_stat_filename = './binance_trading/df_stats.pck'
#
#     #initialisation des stats
#     if os.path.exists(df_stat_filename):
#         df_stats = pd.read_pickle(df_stat_filename)
#     else:
#         df_stats = pd.DataFrame()
#
#
#     st.line_chart(df_stats['mean'])
#     st.line_chart(df_stats[symb])




#
    orders = []

    for orderElement in ordersSorted:
        order = {}
        if orderElement['symbol'] == symb:
            order['symbol'] = orderElement['symbol']
            order['date'] = datetime.datetime.fromtimestamp(int(orderElement['time'])/1000).strftime('%d/%m %H:%M')
            order['orderId'] = orderElement['orderId']
            order['clientOrderId'] = orderElement['clientOrderId']
            order['size'] = orderElement['origQty']
            order['price'] = orderElement['price']
            order['status'] = orderElement['status']
            order['type'] = orderElement['type']
            order['side'] = orderElement['side']
            orders.append(order)

    st.write('Ordres pour {}'.format(symb))
    st.table(orders)
    #st.write(ordersSorted)


    trades = []

    for tradeElement in tradesSorted:
        trade = {}
        if tradeElement['symbol'] == symb:
            trade['symbol'] = tradeElement['symbol']
            trade['date'] = datetime.datetime.fromtimestamp(int(tradeElement['time'])/1000).strftime('%d/%m %H:%M')
            trade['orderId'] = tradeElement['orderId']
            trade['clientOrderId'] = getClientOrderIDFromOrders(ordersSorted, trade['orderId'])
            trade['qty'] = tradeElement['qty']
            trade['quoteQty'] = tradeElement['quoteQty']
            trade['price'] = tradeElement['price']
            trade['realizedPnl'] = tradeElement['realizedPnl']
            trade['commission'] = tradeElement['commission']
            trade['side'] = tradeElement['side']
            trades.append(trade)

    st.write('Trades pour {}'.format(symb))
    st.table(trades)

    #st.write(tradesSorted)



if page_to_display =='strategies':
    strategieList = []
    # besoinde récuperer tous les orders pour retrouver l'entrytime d'une position
    orders = client.futures_get_all_orders(limit=1000)
    ordersSorted = sorted(orders , key = lambda item:float(item['time']),reverse = True)

    for orderElement in ordersSorted:
        strat = orderElement['clientOrderId'].find('MA_')
        if strat > -1 and orderElement['clientOrderId'][:5] not in strategieList:
            strategieList.append(orderElement['clientOrderId'][:5])


    strategie = st.selectbox("Please select strategie", strategieList)
    OrderorTrades = st.checkbox("Order: On / Trades: Off", value=False)
    if not OrderorTrades:
        statusOrder = ""
        typeOrder = ""
        sideOrder = ""
    else:
        col1, col2, col3 = st.columns(3)

        with col1:
            statusOrder = st.radio("Please select statusOrder", ["","FILLED", "CANCELED"])

        with col2:
            typeOrder = st.radio("Please select typeOrder", ["","LIMIT", "MARKET", "TAKE_PROFIT", "STOP_MARKET"])

        with col3:
            sideOrder = st.radio("Please select sideOrder", ["","BUY", "SELL"])





#     strategie = st.text_input('strategie', 'MA_14')



#     # Trades
    trades = client.futures_account_trades(limit=1000)
    tradesSorted = sorted(trades , key = lambda item:float(item['time']),reverse = True)
#





#     df_stat_filename = './binance_trading/df_stats.pck'
#
#     #initialisation des stats
#     if os.path.exists(df_stat_filename):
#         df_stats = pd.read_pickle(df_stat_filename)
#     else:
#         df_stats = pd.DataFrame()
#
#
#     st.line_chart(df_stats['mean'])
#     st.line_chart(df_stats[symb])




#
    orders = []

    for orderElement in ordersSorted:
        order = {}
        if orderElement['clientOrderId'].find(strategie) > -1 and (statusOrder == orderElement['status'] or statusOrder == '')  and (typeOrder == orderElement['type'] or typeOrder == '') and (sideOrder == orderElement['side'] or sideOrder == '') :
            order['symbol'] = orderElement['symbol']
            order['date'] = datetime.datetime.fromtimestamp(int(orderElement['time'])/1000).strftime('%d/%m %H:%M')
            order['orderId'] = orderElement['orderId']
            order['clientOrderId'] = orderElement['clientOrderId']
            order['size'] = orderElement['origQty']
            order['price'] = orderElement['price']
            order['status'] = orderElement['status']
            order['type'] = orderElement['type']
            order['side'] = orderElement['side']
            orders.append(order)


    #st.write(ordersSorted)


    trades = []

    for tradeElement in tradesSorted:
        trade = {}
        if getClientOrderIDFromOrders(ordersSorted, tradeElement['orderId']).find(strategie) > -1 and tradeElement['side'] == 'BUY':
            trade['symbol'] = tradeElement['symbol']
            trade['date'] = datetime.datetime.fromtimestamp(int(tradeElement['time'])/1000).strftime('%d/%m %H:%M')
            trade['orderId'] = tradeElement['orderId']
            trade['clientOrderId'] = getClientOrderIDFromOrders(ordersSorted, trade['orderId'])
            trade['qty'] = tradeElement['qty']
            trade['quoteQty'] = tradeElement['quoteQty']
            trade['price'] = tradeElement['price']
            trade['realizedPnl'] = tradeElement['realizedPnl']
            trade['commission'] = tradeElement['commission']
            trade['side'] = tradeElement['side']
            trades.append(trade)


    if not OrderorTrades:
        st.write('Trades pour {} / nb:{}'.format(strategie, len(trades)))
        st.table(trades)
    else:
        st.write('Ordres pour {} / nb:{}'.format(strategie, len(orders)))
        st.table(orders)
