# -*- encoding:utf-8-*-

import logging

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
    try:
        str_list = []
        for arg in args:
            str_list.append(str(arg))
        print(''.join(str_list))
        logger_log.debug(''.join(str_list))
    except Exception as e:
        logger_error.error(str(e))
        return


logger_header = logging.getLogger("aegis.header.log")


def logHeader(*args):
    try:
        str_list = []
        for arg in args:
            str_list.append(str(arg))
        print(''.join(str_list))
        logger_header.debug(''.join(str_list))
    except Exception as e:
        logger_log.debug(str(e))
        return


def logError(*args):
    """
    Yields
    ------
    err_code : int
        Non-zero value indicates error code, or zero on success.
    err_msg : str or None
        Human readable error message, or None on success.
    """
    try:
        str_list = []
        for arg in args:
            str_list.append(str(arg))
        print(''.join(str_list))
        logger_error.debug(''.join(str_list))
    except Exception as e:
        logger_error.error(str(e))
        return
