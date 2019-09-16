"""
Notification Processer

Copyright 2012 - 2019. Park, Jong-Kee. All rights reserved.

1. notificataion or notification_new
2. PushThread __init__
3. push_notification
4. APNs or FCM or GCM
5. PushThread __del__
"""
# -*- encoding:utf-8-*-

from django.conf import settings
import threading

# from APNSWrapper import *
# from AndroidMessage import *

import ssl
import json
# import socket
import struct
import binascii
from socket import socket, AF_INET, SOCK_STREAM
import time

from .log import logSend, logError

class PushThread(threading.Thread):

    def __init__(self, func, target_list, isSound, badge, contents):
        self.func = func
        self.target_list = target_list
        self.isSound = isSound
        self.badge = badge
        self.contents = contents
        self.result = ""
        threading.Thread.__init__(self)

    def __del__(self):
        logSend('   >>> PUSH del {} target_list = {}: result = {}'.format(self.func,
                                                                          self.target_list,
                                                                          self.result))

    def run(self):
        self.result = push_notification(self.func,
                                        self.target_list,
                                        self.isSound,
                                        self.badge,
                                        self.contents)
        logSend('   >>> PUSH run = {}: {}'.format(str(self.func), self.target_list))
        # self.__del__()

"""
    push_contents = {
        'target_list': [{'id': passer.id, 'token': passer.push_token, 'pType': passer.pType}],
        'func': 'user', 
        'isSound': True, 
        'badge': 3,
        'contents': {'title': '제목', 
                     'subtitle': '부제목', 
                     'body': {'action': 'testPush', 'current': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                     }
    }
"""
# @async
def push_notification(func, target_list, isSound, badge, contents):
    # 서버에서 스마트 폰으로 push 한다.
    # functionName, target_id 는 log 를 위해 필요하다.
    # return:
    #    string: "success"
    #    string: "fail: 사유"
    try:
        logSend('^ func: {}, isSound: {}, badge: {}\n^   contents: {}'.format(func, isSound, badge, contents))
        if (func[0:3] == 'app'):
            target_type = 'driver'
        elif (func[0:3] == 'mng'):
            target_type = 'mng'
        elif (func[0:4] == 'user'):
            target_type = 'user'
        if isSound:
            sound = 'default'
        else:
            sound = None
        apns_list = []
        for target in target_list:
            logSend('^ id: {}, type: {}, token: {}'.format(target['id'], target['pType'], target['token']))
            if target['pType'] == 10:
                apns_list.append(target)
            else:
                if (func[0:5] == 'voip_'):
                    func = func[5:]
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
        result = APNs(target_type, apns_list, None, sound, badge, contents)

        return result
    except Exception as e:
        logSend('   PUSH ' + func + ' Fail: ' + str(e))
        return "fail: " + str(e)


def APNs(target_type, target_list, alert, sound, badge, contents):
    if settings.IS_SERVICE:
        apns_address = ('gateway.push.apple.com', 2195)  # production url
    else:
        apns_address = ('gateway.sandbox.push.apple.com', 2195)  # development url
    logSend('apns_address = {}'.format(apns_address))

    if target_type == 'user':
        logSend('   >> User')
        certFile = settings.APNS_PEM_EMPLOYEE_FILE
    elif target_type == 'mng':
        logSend('   >> staff')
        certFile = settings.APNS_PEM_MANAGER_FILE
    else:
        return {'message': 'targetType unknown - \'user\' or \'mng\''}
    payload_list = []
    for target in target_list:
        new_payload = set_payload(target['token'], alert, sound, badge, contents)
        payload_list.append(new_payload)

    pushSocket = socket(AF_INET, SOCK_STREAM)
    pushSocket.connect(apns_address)
    logSend('   >>> 00 ' + certFile)
    sslSocket = ssl.wrap_socket(pushSocket, certFile, certFile)

    result = []
    for payload in payload_list:
        result.append(sslSocket.write(payload))
    sslSocket.close()
    logSend('<<< push result: {}'.format(result))
    return {'message': result}


def set_payload(token, alert, sound, badge, contents=None):
    identifier = 0  # default
    expiry = None   # default

    bin_token = binascii.unhexlify(token)
    aps = {
        'category': 'USER_MESSAGE_CATEGORY',
        'alert': contents,
        'sound': sound,
        'badge': badge,
    }
    logSend('  >>> aps init: {}'.format(aps))
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
    payload = json.dumps({'aps': aps, 'contents': contents})
    logSend('   >>> APNs payload = {}'.format(payload))
    length = len(payload)
    if expiry is None:
        expiry = int(time.time() + 365 * 86400)
    pack = struct.pack(
        "!bIIH32sH%(length)ds" % {"length": length},
        1, identifier, expiry,
        32, bin_token, length, payload.encode('utf8'))
    return pack


def notification(push_contents):
    """
    push_contents = {
        'target_list': [{'id': passer.id, 'token': passer.push_token, 'pType': passer.pType}],
        'func': 'user',
        'isSound': True,
        'badge': 3,
        'contents': {'title': '제목',
                     'subtitle': '부제목',
                     'body': {'action': 'testPush', 'current': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                     }
    }
    push_contents = {'func': 'mng_testPush', 'id': staff.id, 'token': staff.pToken, 'pType': staff.pType, \
            'push_control': {'alertMsg': '푸쉬를 시험합니다.', 'isSound': 1, 'badgeCount': 3}, \
            'push_contents': {'action':'testPush', 'current':datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
    """
    func = push_contents['func']
    target_list = push_contents['target_list']
    isSound = push_contents['isSound']
    badge = push_contents['badge']
    contents = push_contents['contents']
    PushThread(func, target_list, isSound, badge, contents).start()
    return "threading"



