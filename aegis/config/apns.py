"""
Customer view

Copyright 2019. DaeDuckTech Corp. All rights reserved.
"""
# -*- encoding:utf-8-*-

from django.conf import settings
import threading

# from APNSWrapper import *
# from AndroidMessage import *

import ssl
# import json
# import socket
import struct
import binascii
from socket import socket, AF_INET, SOCK_STREAM

from .log import logSend, logError

# from common import logSend
# from common import logHeader
# from common import logError


############################################################################
#
#   Common Constant
#

############################################################################
#
#   common function
#

class PushThread(threading.Thread):

    def __init__(self, functionName, target_id, token, phoneType, alert, isSound, data):
        self.functionName = functionName
        self.target_id = target_id
        self.token = token
        self.phoneType = phoneType
        self.alert = alert
        self.isSound = isSound
        self.data = data
        self.result = ""
        threading.Thread.__init__(self)

    def __del__(self):
        logSend('   >>> PUSH del ' + self.functionName + ' target_id = ' + str(
            self.target_id) + ': result = ' + self.result)

    def run(self):
        self.result = push_notification(self.functionName, self.target_id, self.token, self.phoneType, self.alert,
                                        self.isSound, self.data)
        logSend('   >>> PUSH run = ' + str(self.target_id) + ' ' + self.token)
        # self.__del__()


def APNs(token, targetType, isSound, alert, data):
    if settings.IS_SERVICE:
        apns_address = ('gateway.push.apple.com', 2195)  # production url
        if targetType == 'user':
            logSend('   >> User')
            certFile = settings.APNS_PEM_USER
        elif targetType == 'driver':
            logSend('   >> Driver')
            certFile = settings.APNS_PEM_DRIVER
        elif targetType == 'mng':
            logSend('   >> staff')
            certFile = settings.APNS_PEM_MNG
        elif targetType == 'voip_mng':
            logSend('   >> voip_mng')
            certFile = settings.APNS_PEM_VOIP_MNG
        elif targetType == 'voip_user':
            logSend('   >> voip_user')
            certFile = settings.APNS_PEM_VOIP_USER
        elif targetType == 'voip_driver':
            logSend('   >> voip_driver')
            certFile = settings.APNS_PEM_VOIP_DRIVER
    else:
        apns_address = ('gateway.sandbox.push.apple.com', 2195)  # development url
        if targetType == 'user':
            logSend('   >> User')
            certFile = settings.DEV_PEM_USER
        elif targetType == 'driver':
            logSend('   >> Driver')
            certFile = settings.DEV_PEM_DRIVER
        elif targetType == 'mng':
            logSend('   >> staff')
            certFile = settings.DEV_PEM_MNG
        elif targetType == 'voip_mng':
            logSend('   >> VoIP staff')
            certFile = settings.APNS_PEM_VOIP_MNG
        elif targetType == 'voip_user':
            logSend('   >> VoIP user')
            certFile = settings.APNS_PEM_VOIP_USER
        elif targetType == 'voip_driver':
            logSend('   >> VoIP driver')
            certFile = settings.APNS_PEM_VOIP_DRIVER
    logSend('apns_address = ' + apns_address)
    pushSocket = socket(AF_INET, SOCK_STREAM)
    pushSocket.connect(apns_address)
    # sslSocket = ssl.wrap_socket(pushSocket, certFile, certFile, ssl_version=ssl.PROTOCOL_SSLv3)
    logSend('   >>> 00 ' + certFile)
    sslSocket = ssl.wrap_socket(pushSocket, certFile, certFile)
    # logSend('   >>> 01')
    token = binascii.unhexlify(token)
    # >>> notification 1 'user_pushMessage': target_id = 1L, alert = 알림, data = {'action': 'Message', 'msg': '알림 시험'}
    aps = {}
    if isSound:
        aps['sound'] = 'default'
    # aps['content-available'] = 1  # content-available: 1
    aps['alert'] = alert
    aps['badge'] = 0
    # aps['badge'] = random.randint(0, 5)
    """
    aps = {
        'category' : 'NEW_MESSAGE_CATEGORY',
        'alert' : {
            'title' : 'Game Request',
            'body' : 'Bob wants to play poker',
            'action-loc-key' : 'PLAY'
        },      
        'badge' : 3,
        'sound' : 'chime.aiff'
    }
    """
    message = {}
    message['aps'] = aps
    # aps = {'aps' : {"sound": "default", "alert": "알림"}, }
    for cell in data:
        message[cell] = data[cell]
    # logSend('   >>> APNs message = ' + `message`)
    # '\x00\x00 =\xbb\x14\x00n{"aps":{"sound":"default","alert":"알림"},"action":"Message","msg":"알림 시험"}'
    payload = json.dumps(message)
    # payload = json.dumps({"apn": {"alert":"APNs test", "badge":1, "sound":"bingbong.aiff"}})
    # payload = {alert : data}
    # logSend('   >>> APNs payload = ' + payload)
    fmt = "!cH32sH{0:d}s".format(len(payload))
    cmd = '\x00'
    msg = struct.pack(fmt, cmd, len(token), token, len(payload), payload)
    sslSocket.write(msg)
    sslSocket.close()
    return payload


def notification(functionName, target_id, token, phoneType, alert, isSound, data):
    if len(token) < 20:
        logSend('>>> notification : cancel >>> none token')
        return "None token"
    # push_notification(functionName, target_id, token, phoneType, alert, data)
    PushThread(functionName, target_id, token, phoneType, alert, isSound, data).start()
    return "threading"


def notification_new(push_contents):
    """
    push_contents = {'func': 'mng_testPush', 'id': staff.id, 'token': staff.pToken, 'pType': staff.pType, \
            'push_control': {'alertMsg': '푸쉬를 시험합니다.', 'isSound': 1, 'badgeCount': 3}, \
            'push_contents': {'action':'testPush', 'current':datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
    """
    functionName = push_contents['func']
    target_id = push_contents['id']
    token = push_contents['token']
    phoneType = push_contents['pType']
    alert = push_contents['push_control']['alertMsg']
    isSound = push_contents['push_control']['isSound']
    # isUpdate = push_contents['push_control']['isUpdate']
    data = push_contents['push_contents']
    if len(token) < 20:
        logSend('>>> notification : cancel >>> none token')
        return "None token"
    # push_notification(functionName, target_id, token, phoneType, alert, data)
    PushThread(functionName, target_id, token, phoneType, alert, isSound, data).start()
    return "threading"


# @async
def push_notification(functionName, target_id, token, phoneType, alert, isSound, data):
    # 서버에서 스마트 폰으로 push 한다.
    # functionName, target_id 는 log 를 위해 필요하다.
    # return:
    #    string: "success"
    #    string: "fail: 사유"
    try:
        # logSend('>>> phoneType ' + str(phoneType))
        # logSend('   >>> notification ' + functionName + ': target_id = ' + target_id + ', alert = ' + unicode(alert, "UTF-8") + ', data = ' + data + token)
        logSend('>>> notification ' + functionName + ': target_id = ' + str(target_id) + ', action = ' + str(
            data['action']))  # + ' token:' + token)
        # logSend('>>> notification ' + functionName + ': target_id = ' + str(target_id) + ', action = ' + str(data))
        # send push
        if (phoneType == 00):
            if (functionName[0:3] == 'app'):
                targetType = 'driver'
            elif (functionName[0:3] == 'mng'):
                targetType = 'mng'
            elif (functionName[0:4] == 'user'):
                targetType = 'user'
            elif (functionName[0:8] == 'voip_mng'):
                targetType = 'voip_mng'
            elif (functionName[0:9] == 'voip_user'):
                targetType = 'voip_user'
            elif (functionName[0:8] == 'voip_app'):
                targetType = 'voip_driver'
            result = APNs(token, targetType, isSound, alert, data)
            result = "success: APNS " + str(target_id)  # + ', data = ' + result
        else:
            if (functionName[0:5] == 'voip_'):
                functionName = functionName[5:]
            """
            if (functionName[0:3] == 'app') :
                gcmKey = 'AIzaSyCRNWBpY_7buR6cDSbaTmdvTkvwNX7MjEk' # 정용조
            else :
                gcmKey = 'AIzaSyAXEuxGB6aUDrewz50yJaQjgyEaI5bOEXM' # 정용조
            """
            # gcmKey = 'AIzaSyD0KiBW4vFeF_qK6g_0sIHcSJ66KQyTeKk' # 곽명석
            # gcmKey = 'AIzaSyBjAijsOskVybwlWbEo17XNDS9Q7XFOCC0' # 정용조 설레

            gcmKey = 'AIzaSyCSbKzbIwHjMc9IeSRmNKCs5tLgL_t8BB8'  # 'AIzaSyBvwG9bqJnnygadmDwjf6AbPeyZUIrvlUU'
            sender = GoogleCloudMessaging(gcmKey)
            sender.registrationId = token
            # sender.collapseKey = 1
            # logSend('>>> push GCM ' + str(data))
            data['alert'] = alert
            data['isSound'] = isSound
            logSend('>>> push GCM ' + str(data))
            sender.data = data

            response = sender.sendMessage()
            result = "success: GCM response = " + str(target_id) + ', ' + str(response)  # + ', data = ' + str(data)
            # logSend('>>> debugging 02 ' + result)

        return result
    except Exception as e:
        logSend('   PUSH ' + functionName + ' Fail: ' + str(e))
        return "fail: " + str(e)
