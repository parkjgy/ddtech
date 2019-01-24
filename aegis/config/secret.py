#
#   encryption / decryption
#

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt  # POST 에서 사용

# log import
from config.common import logSend

AESkey = "\x3B\x2F\x2A\x20\x4E\x36\x3F\x67\x2D\x6B\x3B\x2C\x3B\x6B\x50\x31\x29\x5A\x47\x6C\x49\x79\x4C\x5F\x5C\x5A\x2C\x67\x73\x3A\x50\x47"
AESiv = "\x31\x47\x42\x75\x42\x7C\x6D\x31\x47\x7B\x22\x5F\x3B\x7B\x2D\x58"

from Crypto.Cipher import AES
from Crypto.Util.py3compat import *
import base64


# 기존 PKCS5 -> PKCS7 Padding

def pad(data_to_pad, block_size, style='pkcs7'):
    if isinstance(data_to_pad, str):
        data_to_pad = bytes(data_to_pad, encoding='utf-8')

    padding_len = block_size - len(data_to_pad) % block_size
    if style == 'pkcs7':
        padding = bchr(padding_len) * padding_len
    elif style == 'x923':
        padding = bchr(0) * (padding_len - 1) + bchr(padding_len)
    elif style == 'iso7816':
        padding = bchr(128) + bchr(0) * (padding_len - 1)
    else:
        raise ValueError("Unknown padding style")
    return data_to_pad + padding


def unpad(padded_data, block_size, style='pkcs7'):
    pdata_len = len(padded_data)
    if pdata_len % block_size:
        raise ValueError("Input data is not padded")
    if style in ('pkcs7', 'x923'):
        padding_len = bord(padded_data[-1])
        if padding_len < 1 or padding_len > min(block_size, pdata_len):
            raise ValueError("Padding is incorrect.")
        if style == 'pkcs7':
            if padded_data[-padding_len:] != bchr(padding_len) * padding_len:
                raise ValueError("PKCS#7 padding is incorrect.")
        else:
            if padded_data[-padding_len:-1] != bchr(0) * (padding_len - 1):
                raise ValueError("ANSI X.923 padding is incorrect.")
    elif style == 'iso7816':
        padding_len = pdata_len - padded_data.rfind(bchr(128))
        if padding_len < 1 or padding_len > min(block_size, pdata_len):
            raise ValueError("Padding is incorrect.")
        if padding_len > 1 and padded_data[1 - padding_len:] != bchr(0) * (padding_len - 1):
            raise ValueError("ISO 7816-4 padding is incorrect.")
    else:
        raise ValueError("Unknown padding style")
    return padded_data[:-padding_len]


# encrypt ( str or bytes ) return bytes;
def AES_ENCRYPT(msg) -> bytes:
    aes = AES.new(AESkey, AES.MODE_CBC, AESiv)
    return aes.encrypt(pad(msg, 16))


# encrypt ( str or bytes ) return base64:str;
def AES_ENCRYPT_BASE64(msg) -> str:
    return base64.b64encode(AES_ENCRYPT(msg)).decode(encoding='utf-8')


# decrypt ( bytes ) return bytes;
def AES_DECRYPT(msg) -> bytes:
    dec = AES.new(AESkey, AES.MODE_CBC, AESiv).decrypt(msg)
    return unpad(dec, 16)


# decrypt ( base64:str ) return bytes;
def AES_DECRYPT_BASE64(msg: str) -> str:
    msg += '=' * (-len(msg) % 4)
    msg = base64.b64decode(bytes(msg, encoding='utf-8'))
    return AES_DECRYPT(msg).decode(encoding='UTF-8')


# decrypt ( base64:str ) return bytes;
def AES_DECRYPT_BASE64Bytes(msg: str) -> bytes:
    msg += '=' * (-len(msg) % 4)
    msg = base64.b64decode(bytes(msg, encoding='utf-8'))
    return AES_DECRYPT(msg)


"""
Management: testEncryptionStr: get Encryption (Development only)
   문자열을 암호화한다.
http://dev.ddtechi.com:8055/dr/testEncryptionStr?plaintext=1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ 가나다라마바사아자차카타파하
http://dev1.ddtechi.com:8033/dr/testEncryptionStr?plaintext=1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ 가나다라마바사아자차카타파하
< plainText: 암호되지 않은 문서
> cipherText: 암호화된 문서
"""


@csrf_exempt
def testEncryptionStr(request):
    """
    Management: testEncryptionStr: get Encryption (Development only)
    문자열을 암호화한다.
    http://dev.ddtechi.com:8055/dr/testEncryptionStr?plaintext=1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ 가나다라마바사아자차카타파하
    http://dev1.ddtechi.com:8033/dr/testEncryptionStr?plaintext=1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ 가나다라마바사아자차카타파하
    < plainText: 암호되지 않은 문서
    > cipherText: 암호화된 문서
    """
    logSend('>>> testEncryptionStr: ' + request.META["QUERY_STRING"][10:])
    _plainText = request.META["QUERY_STRING"][10:]
    # _plainText = '1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ 가나다라마바사아자차카타파하'

    logSend(_plainText)
    r = '*** plainText = ' + _plainText
    _cipherText = AES_ENCRYPT(_plainText)
    r += '</br>*** cipherText(bytes) = ' + _cipherText.hex()
    b64cipherText = AES_ENCRYPT_BASE64(_plainText)
    r += '</br>*** base64 cipherText = ' + b64cipherText
    plainText = AES_DECRYPT_BASE64(b64cipherText)
    r += '</br>*** replainText = ' + plainText
    logSend(plainText)
    return HttpResponse(r)


"""
Management: testDecryptionStr: get Decryption (Development only)
   암호화된 문자열을 복호화한다.
http://dev.ddtechi.com:8055/dr/testDecryptionStr?cipherText=VAyRZxuerUAjgiDqh9WAx1MvNqb+jCfIN3scgwqUibTfo2eW3AF9DBwebHrCfQ2Eee5u4GhtPL4X1hTnHgKv2Z4T3t67ujIvu7wctmRp1Nidit2XwJjH4q6tLUmTjN+v7ww+T8I1AJH5bI03WgG7NJz4laube8S/rRN7bKzONr2u4QTTRtY0IRZYvxjJxPNRjUJM5nuH7johCspgEToWz/iM+CYmSBVeywfCCQJQAFo=
http://dev1.ddtechi.com:8033/dr/testDecryptionStr?cipherText=VAyRZxuerUAjgiDqh9WAx1MvNqb+jCfIN3scgwqUibTfo2eW3AF9DBwebHrCfQ2Eee5u4GhtPL4X1hTnHgKv2Z4T3t67ujIvu7wctmRp1Nidit2XwJjH4q6tLUmTjN+v7ww+T8I1AJH5bI03WgG7NJz4laube8S/rRN7bKzONr2u4QTTRtY0IRZYvxjJxPNRjUJM5nuH7johCspgEToWz/iM+CYmSBVeywfCCQJQAFo=
< cipherText: 암호화된 문서
> plainText: 복호화된 문서
"""


@csrf_exempt
def testDecryptionStr(request):
    """
    Management: testDecryptionStr: get Decryption (Development only)
       암호화된 문자열을 복호화한다.
    http://dev.ddtechi.com:8055/dr/testDecryptionStr?cipherText=VAyRZxuerUAjgiDqh9WAx1MvNqb+jCfIN3scgwqUibTfo2eW3AF9DBwebHrCfQ2Eee5u4GhtPL4X1hTnHgKv2Z4T3t67ujIvu7wctmRp1Nidit2XwJjH4q6tLUmTjN+v7ww+T8I1AJH5bI03WgG7NJz4laube8S/rRN7bKzONr2u4QTTRtY0IRZYvxjJxPNRjUJM5nuH7johCspgEToWz/iM+CYmSBVeywfCCQJQAFo=
    http://dev1.ddtechi.com:8033/dr/testDecryptionStr?cipherText=VAyRZxuerUAjgiDqh9WAx1MvNqb+jCfIN3scgwqUibTfo2eW3AF9DBwebHrCfQ2Eee5u4GhtPL4X1hTnHgKv2Z4T3t67ujIvu7wctmRp1Nidit2XwJjH4q6tLUmTjN+v7ww+T8I1AJH5bI03WgG7NJz4laube8S/rRN7bKzONr2u4QTTRtY0IRZYvxjJxPNRjUJM5nuH7johCspgEToWz/iM+CYmSBVeywfCCQJQAFo=
    < cipherText: 암호화된 문서
    > plainText: 복호화된 문서
    """
    logSend('>>> testDecryptionStr: ', request.META["QUERY_STRING"][11:])

    _b64CipherText = request.META["QUERY_STRING"][11:]
    r = '*** base64 cipherText = ' + _b64CipherText
    plainText = AES_DECRYPT_BASE64(_b64CipherText)
    r += '</br>*** plainText = ' + plainText
    return HttpResponse(r)
