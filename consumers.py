import json
from decimal import *
from channels import Group
from channels.auth import channel_session_user_from_http, channel_session_user

from .models import Trade
from .models import Profile
from django.contrib.auth.models import User
import time
import threading
from django.utils import timezone

# {pid : [{pending Trades}, {trade history}, conNum, time, see below, a lock of the [2], see below, a lock of the [6]]}
# [2] is the number of people of a institution connected to the server
# [3] is the latest look up time of a institution
# [4] if the update function of that institution is running, the value is true, else is false
# [6] 0 means not waiting, 1 means is waiting, 2 means need to wait again
Trades = {}

# define the precise of the amount
getcontext().prec = 2

'''

Converts a Trade model into a standard python dictionary

'''
def trade_to_dic(trade):
    # get the last modified user name by user id, if the id is unknown, the user name will be set to None
    users = User.objects.filter(id=trade.ModifiedByID)
    userName = "None"
    for user in users:
        userName = user.username

    return {"id": trade.id,
    "buyer_id": trade.BuyerID_id,
    "buyer_name": trade.BuyerID.PartyName,
    "seller_id": trade.SellerID_id,
    "seller_name": trade.SellerID.PartyName,
    "seller_phone": trade.SellerID.PartyPhoneNumber,
    "time_pushed": trade.TimePushed,
    "time_actioned": trade.TimeActioned,
    "trade_type": trade.TradeType,
    "status": trade.Status,
    "currency_pair": trade.CurrencyPair,
    "institution_id": trade.institution_id,
    "amount_millions": str(trade.Amount_millions),
    "reason": trade.Reason,
    "modified_by_id": trade.ModifiedByID,
    "modified_by_name": userName,
    "rate": str(trade.Rate),
    "contra_amount": str(trade.Rate * trade.Amount_millions),
    }

'''

Converts all trades in a query set into dictionaries as above

'''
def to_dict(queryset):
    trade_dic = {}
    for trade in queryset:
        prn_obj(trade)
        trade_dic[trade.id] = trade_to_dic(trade)
    return trade_dic


'''

Used to track when trades are pushed/modified because the default python datetime doesn't play nice with Django.

'''
def getCurrentMilliTime():
    return int(round(time.time() * 1000))


'''

Each institution has its own thread of updateFromDB. this thread will look up the database per updateInterval second
(here set to 1). If new data is found in database, the queryset returned by database will be convert into a standard
python dictionary which can be convert to appropriate JSON data. The JSON data will be send to webpage.

'''

def updateFromDB(id):
    updateInterval = 1;
    # stop updateInterval second because the data has been looked up in a short time before this thread created
    time.sleep(updateInterval)
    global Trades
    Trades[id][5].acquire()
    # this thread should exist if any one connect to the server
    while Trades[id][2]:
        Trades[id][5].release()
        trades = Trade.objects.filter(TimePushed__gte = Trades[id][3]).filter(Status = "PENDING", institution=id)
        if(trades):
            Trades[id][3] = getCurrentMilliTime()
            dTrades = to_dict(trades)
            Group("chat-%d" % id).send({
            "text": json.dumps({"add_p": dTrades, "add_h": {}, "del": {"has_del": 0}})
            })
            Trades[id][0] = {**Trades[id][0], **dTrades}
        # get the data from database per updateInterval second for each institution
        time.sleep(updateInterval)
        # lock the Trades[id][2]
        Trades[id][5].acquire()
    Trades[id][4] = False
    Trades[id][5].release()


'''

Manages the local data being held in cache/memory. the local data of a institution will be removed after
iMax * timeInterval seconds when no one of that institution connect to server

'''
def deleteLocalData(id):
    # used to count the time, 1 means 10 seconds here
    i = 0
    # the time to check if there is nobody of a institution connection to the server, set iMax to 6 means it will check
    # 6 times
    iMax = 6
    timeInterval = 10
    Trades[id][5].acquire()
    while i < iMax and (Trades[id][2] == 0):
        Trades[id][5].release()
        time.sleep(timeInterval)
        i += 1
        # if someone connect to server and disconnect in timeInterval seconds (here is 10), the count need to be restart
        if Trades[id][6] == 2:
            i = 0
            Trades[id][7].acquire()
            Trades[id][6] = 1
            Trades[id][7].release()
        Trades[id][5].acquire()

    # if no one connect to server in iMax * timeInterval seconds (Trades[id][2] == 0) and no new user try to access (not
    #  access_locks[id].locked()), delete the local data, else make the local data available again
    if Trades[id][2] == 0 and (not access_locks[id].locked()):
        Trades.pop(id, None)
        accessLock.acquire()
        # if the last access is before iMax * timeInterval seconds, then delete the lock for that institution, and this
        # if is used to avoid delete the access_lock created by the user who just create the access_lock
        if(last_access_time[id] < getCurrentMilliTime() - iMax * timeInterval * 1000):
            access_locks.pop(id, None)
            last_access_time.pop(id, None)
        accessLock.release()
    else:
        Trades[id][5].release()

def prn_obj(obj):
    print(', '.join(['%s:%s\n' % item for item in obj.__dict__.items()]))



# used to lock the manipulation of the access_locks
accessLock = threading.Lock()
# used to lock the access of the different institution, see below
access_locks = {}
# used to judge whether to delete the access lock of an institution
# to avoid delete the access lock when delete the local data but a new one is accessing
last_access_time = {}


'''

This is the code that uses the Django Channels module to form an AJAX-like connection between the server and client.
Handles the first access from new client. Controls the method used to update local data.
Locking is used to ensure multiple simultaneous logins do not cause duplicate records to be created.

'''
@channel_session_user_from_http
def ws_connect(message):
    global Trades, accessLock, access_locks
    # user id
    uid = message.channel_session._session_cache["_auth_user_id"]
    # institution id
    insId = Profile.objects.get(user=User.objects.get(id=uid)).institution_id
    if insId is None:
        message.reply_channel.send({
            "text": json.dumps({"add_p": {}, "add_h": {}, "del": {"has_del": 0}})
        })
        return
    # lock the process of the creation of the institution data at the first time
    # to avoid two people in the same institution access at same time causing the creation multiple times
    accessLock.acquire()
    # if the access lock of institution insId doesn't exist, create it
    if(not (insId in access_locks)):
        access_locks[insId] = threading.Lock()
    # update the access time
    last_access_time[insId] = getCurrentMilliTime()
    accessLock.release()
    # avoid multiple people try to create local data cause duplicate
    access_locks[insId].acquire()
    # check if this company is added to the Trades
    if(not (insId in Trades)):
        # get the pending trades from the database
        pendingTrades = Trade.objects.filter(Status="PENDING", institution=insId).order_by('TimePushed')
        tradesHistory = Trade.objects.filter(institution=insId).exclude(Status="PENDING")
        Trades[insId] = [to_dict(pendingTrades), to_dict(tradesHistory), 1, getCurrentMilliTime(), True, threading.Lock(), 0, threading.Lock()]
        p = threading.Thread(target=updateFromDB, args=(insId,))
        p.setDaemon(True)
        p.start()
        access_locks[insId].release()
    else:
        Trades[insId][5].acquire()
        access_locks[insId].release()
        # if local data is exist but update thread has been stopped, restart update thread again
        if Trades[insId][2] == 0 and (not Trades[insId][4]):
            Trades[insId][4] = True
            p = threading.Thread(target=updateFromDB, args=(insId,))
            p.setDaemon(True)
            p.start()
        Trades[insId][2] += 1
        Trades[insId][5].release()
    message.reply_channel.send({'accept': True})
    # check if this company is added to the list
    # if added update and return
    # else add to the list and get value and return
    Group("chat-%d" % insId).add(message.reply_channel)
    message.reply_channel.send({
        "text": json.dumps({"add_p": Trades[insId][0], "add_h": Trades[insId][1], "del": {"has_del": 0}})
    })

'''

Handles the signals being sent by the client to affirm/reject/revert a trade.

'''
@channel_session_user
def ws_receive(message):
    # get the user id of the user who logged in
    uid = message.channel_session._session_cache["_auth_user_id"]
    # get the institution id of the user who logged in
    insId = Profile.objects.get(user=User.objects.get(id=uid)).institution_id
    # if the user don't have institution, return empty JSON
    if insId is None:
        message.reply_channel.send({
            "text": json.dumps({"add_p": {}, "add_h": {}, "del": {"has_del": 0}})
        })
        return
    # update the list (get new trade, and change the state of the old trade) and return the update
    action = json.loads(message["text"])
    global Trades
    action_id = int(action["id"])
    obj = Trade.objects.get(id = action_id)
    obj.TimeActioned = getCurrentMilliTime()
    trade = {}
    command = 0
    if(action["command"] == "revert"):
        # revert the trade to pending
        command = 1
        obj.Status = "PENDING"
        obj.ModifiedByID = uid
        obj.Reason = action["reason"]
        obj.save()
        Trades[insId][1].pop(action_id, None)
        Trades[insId][0][action_id] = trade = trade_to_dic(obj)
    else:
        command = 0
        if(action["command"] == "affirm"):
            # affirm a trade
            obj.Status = "AFFIRMED"
            obj.ModifiedByID = uid
            obj.save()
        else:
            # reject a trade
            obj.Status = "REJECTED"
            obj.ModifiedByID = uid
            obj.Reason = action["reason"]
            obj.save()
        print(Trades[insId][0].pop(action_id, None))
        Trades[insId][1][action_id] = trade = trade_to_dic(obj)
    # in action, 0 indicate affirm or reject, 1 indicate revert
    Group("chat-%d" % insId).send({
        "text": json.dumps({"add_p": {}, "add_h": {}, "del": {"has_del": 1,
                                                              "action": command,
                                                              "trade": trade}})
    })


'''

Handles the disconnecting message from client, and control the deleteLocalData thread to manage the local data

'''

@channel_session_user
def ws_disconnect(message):
    # get the user id of the user who logged in
    uid = message.channel_session._session_cache["_auth_user_id"]
    # get the institution id of the user who logged in
    insId = Profile.objects.get(user=User.objects.get(id=uid)).institution_id
    # if the user don't have institution, return empty JSON
    if insId is None:
        message.reply_channel.send({
            "text": json.dumps({"add_p": {}, "add_h": {}, "del": {"has_del": 0}})
        })
        return
    global Trades
    # reduce the count
    Trades[insId][5].acquire()
    Trades[insId][2] -= 1
    Trades[insId][5].release()
    # if no one of a institution connecting to the server, start or update the deleteLocalData
    if(Trades[insId][2] == 0):
        Trades[insId][7].acquire()
        # if Trades[insId][6] != 0, means deleteLocalData is running, so the time in deleteLocalData need to be reset
        # to 0
        if Trades[insId][6]:
            Trades[insId][6] = 2
            Trades[insId][7].release()
        else:
            # If no deleteLocalData is running, a new deleteLocalData thread need to be start
            Trades[insId][7].release()
            p = threading.Thread(target=deleteLocalData, args=(insId,))
            p.setDaemon(True)
            p.start()
    Group('chat-%d' %insId).discard(message.reply_channel)