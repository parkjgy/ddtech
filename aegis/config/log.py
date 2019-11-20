# -*- encoding:utf-8-*-

from django.conf import settings

import random
import logging
import threading

import requests
import json

logger_log = logging.getLogger("aegis.log")
logger_error = logging.getLogger("aegis.error.log")
logger_error.setLevel(logging.DEBUG)


def logSend(*args):
    """앱에서 게시물은 요청한다.

    :param: id 게시물의 id 이다

    :returns: json 양식으로 온다. {'S':'0', 'M':'POST 로 와야함'} {'S':'1', 'R':{'tit ... king'}}
    :returns: S: 성공 여부이다. 1: 성공, 0: 실패
    :returns: M: 실패 했을 때 메세지가 실려있다.
    :returns: R: json 양식으로된 게시물이다. {'title': '임신 중 ', 'text': '<!DOCTYPE html><html>...', 'published_date': '2018-10-04', 'author':'Thinking'}
    """
    global log_thread
    if not settings.IS_LOG:
        return
    log_thread.run(*args)
    return
    # log = ''.join([str(x) for x in args])
    # if settings.DEBUG:
    #     print(log)
    # logger_log.debug(log)
    # return

    # try:
    #     if not settings.IS_LOG:
    #         return
    #     str_list = []
    #     for arg in args:
    #         str_list.append(str(arg))
    #     logger_log.debug(''.join(str_list))
    # except Exception as e:
    #     logger_error.error(str(e))
    #     return


class LogSend(threading.Thread):

    def __init__(self):
        if settings.DEBUG:
            print('----------- init. logsend thread')
        threading.Thread.__init__(self)

    # def __del__(self):

    def run(self, *args: list):
        log = ''.join([str(x) for x in args])
        if settings.DEBUG:
            print('{}'.format(log))
        logger_log.debug(log)
        # print('----------- log: {}'.format(log))


log_thread = LogSend()


logger_header = logging.getLogger("aegis.header.log")


def logHeader(*args):
    global log_header_thread
    if not settings.IS_LOG:
        return
    log_header_thread.run(*args)
    return
    # try:
    #     str_list = []
    #     for arg in args:
    #         str_list.append(str(arg))
    #     logger_header.debug(''.join(str_list))
    # except Exception as e:
    #     logger_log.debug(str(e))
    #     return


class LogHeader(threading.Thread):

    def __init__(self):
       threading.Thread.__init__(self)

    # def __del__(self):

    def run(self, *args):
        log = ''.join([str(x) for x in args])
        if settings.DEBUG:
            print(log)
        logger_header.debug(log)


log_header_thread = LogHeader()


def logError(*args):
    """
    Yields
    ------
    err_code : int
        Non-zero value indicates error code, or zero on success.
    err_msg : str or None
        Human readable error message, or None on success.
    """
    log = ''.join([str(x) for x in args])
    if settings.DEBUG:
        print(log)
    logger_error.debug(log)
    return
    # try:
    #     str_list = []
    #     for arg in args:
    #         str_list.append(str(arg))
    #     logger_error.debug(''.join(str_list))
    # except Exception as e:
    #     logger_error.error(str(e))
    #     return


# 슬랙 연동용 코드
def send_slack(title, message, channel='#server_bug', username='알리미', icon_emoji='ghost'):
    slack_hook_url = 'https://hooks.slack.com/services/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'
    payload = {'text': ':pushpin: ' + title, 'username': username, 'icon_emoji': icon_emoji, 'attachments': []}
    payload['attachments'].append({'text': message})
    if channel is not None:
        payload['channel'] = channel
    requests.post(slack_hook_url, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
