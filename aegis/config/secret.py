#
#   encryption / decryption
#

# log import
from config.common import logSend
from config.common import logHeader
from config.common import logError

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt, csrf_protect, ensure_csrf_cookie # POST 에서 사용


AESkey = "\x3B\x2F\x2A\x20\x4E\x36\x3F\x67\x2D\x6B\x3B\x2C\x3B\x6B\x50\x31\x29\x5A\x47\x6C\x49\x79\x4C\x5F\x5C\x5A\x2C\x67\x73\x3A\x50\x47"
AESiv = "\x31\x47\x42\x75\x42\x7C\x6D\x31\x47\x7B\x22\x5F\x3B\x7B\x2D\x58"

from Crypto.Cipher import AES
from Crypto import Random
import base64


def AES_ENCRYPT(msg):
    aes = AES.new(bytes(AESkey), AES.MODE_CBC, AESiv)

    msg2 = 32 - (len(msg) % 32)
    msg2 = '%s%s' % (msg, chr(msg2) * msg2)

    return aes.encrypt(msg2)


def base64encode(msg):
    return base64.urlsafe_b64encode(msg).strip(b'=')


def AES_ENCRYPT_HEX(msg):
    cipherText = AES_ENCRYPT(msg)
    r = ''
    i = 0
    for ch in cipherText:
        r += '%02X' % ord(ch) + ' '
        i += 1
    return r + 'Length = ' + str(i)


def AES_DECRYPT(msg):
    try:
        dec = AES.new(bytes(AESkey), AES.MODE_CBC, AESiv).decrypt(msg)
        return dec[:-ord(dec[len(dec) - 1])]
    except Exception as e:
        logError('ERROR: AES_DECRYPT')
        logSend('ERROR: AES_DECRYPT')
        return '......'


def base64decode(msg):
    try:
        pad = b'=' * (-len(msg) % 4)
        """
        logSend('>>> base64decode ' + msg + ' >>> ' + `base64.urlsafe_b64decode(msg + pad)`)
        msg = msg.replace('-', '+')
        logSend('   >>> base64decode ' + msg + ' >>> ' + `base64.urlsafe_b64decode(msg + pad)`)
        """
        return base64.urlsafe_b64decode(msg + pad)
    except Exception as e:
        logError('ERROR: base64decode')
        logSend('ERROR: base64decode')
        return 'Li4uLi4u'


def AES_DECRYPT_HEX(msg):
    # logSend('AES_DECRYPT >>>' + `AES_DECRYPT(msg.decode('Hex'))` + '>>>' + `AES_DECRYPT(msg.decode('Hex')).rstrip('\0')`)
    return AES_DECRYPT(msg.decode('Hex')).rstrip('\0')


"""
Management: testEncryptionStr: get Encryption (Development only)
   문자열을 암호화한다.
http://localhost:8000/dr/testEncryptionStr?plaintext=1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ 가나다라마바사아자차카타파하
http://dev.seole.net:8000/dr/testEncryptionStr?plaintext=1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ 가나다라마바사아자차카타파하
< plainText: 암호되지 않은 문서
> cipherText: 암호화된 문서
"""


@csrf_exempt
def testEncryptionStr(request):
    logSend('>>> testEncryptionStr: ' + request.META["QUERY_STRING"][10:])
    _plainText = request.META["QUERY_STRING"][10:]
    # _plainText = '1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ 가나다라마바사아자차카타파하'

    # aaa = _plainText.encode('unicode-escape')
    # logSend('aaa' + aaa.encode('utf-8'))
    # bbb = _plainText.decode('unicode-escape')
    # logSend('bbb' + bbb.encode('utf-8'))
    # logSend('*****' + _plainText.encode('utf-8'))
    logSend(_plainText.decode('utf-8'))
    r = '*** plainText = ' + _plainText
    _cipherText = AES_ENCRYPT(_plainText)
    r += '</br>*** cipherText(bytes) = ' + AES_ENCRYPT_HEX(_cipherText)
    b64cipherText = base64encode(_cipherText)
    r += '</br>*** base64 cipherText = ' + b64cipherText
    cipherText = base64decode(b64cipherText)
    r += '</br>*** cipherText(bytes) = ' + AES_ENCRYPT_HEX(cipherText)
    plainText = AES_DECRYPT(cipherText)
    r += '</br>*** replainText = ' + plainText
    logSend(plainText.decode('utf-8'))
    return HttpResponse(r)


"""
Management: testDecryptionStr: get Decryption (Development only)
   암호화된 문자열을 복호화한다.
http://localhost:8000/dr/testDecryptionStr?cipherText=bPRlRWGlo2jEJ0o1UuzqFG_-YCFOJLZn9LFk_213X0rbrALoPyF3x1YhRobhUdJCvk13FUA8Xrs4F0aajD3r-4ak9GYxYD97Plo1CAtxtS77Z7rsYFqTak_JKo3pSCTm
http://dev.seole.net:8000/dr/testDecryptionStr?cipherText=bPRlRWGlo2jEJ0o1UuzqFG_-YCFOJLZn9LFk_213X0rbrALoPyF3x1YhRobhUdJCvk13FUA8Xrs4F0aajD3r-4ak9GYxYD97Plo1CAtxtS77Z7rsYFqTak_JKo3pSCTm
< cipherText: 암호화된 문서
> plainText: 복호화된 문서
"""


@csrf_exempt
def testDecryptionStr(request):
    logSend('>>> testDecryptionStr: ' + request.META["QUERY_STRING"][11:])

    _b64CipherText = request.META["QUERY_STRING"][11:]
    r = '*** base64 cipherText = ' + _b64CipherText
    _cipherText = base64decode(_b64CipherText)
    r += '</br>*** cipherText = ' + AES_ENCRYPT_HEX(_cipherText)
    plainText = AES_DECRYPT(_cipherText)
    r += '</br>*** plainText = ' + plainText
    logSend(plainText.decode('utf-8'))
    # r += '</br>*** plainText = ' + plainText
    return HttpResponse(r)
