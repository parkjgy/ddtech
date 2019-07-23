
import json


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            if obj.utcoffset() is not None:
                obj = obj - obj.utcoffset() + timedelta(0, 0, 0, 0, 0, 9)
                # logSend('DateTimeEncoder >>> utcoffset() = ' + str(obj.utcoffset()) + ', obj = ' + str(obj))
            encoded_object = obj.strftime('%Y-%m-%d %H:%M:%S')
            # logSend('DateTimeEncoder >>> is YES >>>' + str(encoded_object))
        else:
            encoded_object = json.JSONEncoder.default(self, obj)
            # logSend('DateTimeEncoder >>> is NO >>>' + str(encoded_object))
        return encoded_object
