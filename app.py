from flask import Flask,jsonify
from SIMDetailsGetter import *
from flask import request
from datetime import datetime

app = Flask(__name__)
app.config['DEBUG'] = True


def timestamp_processor(input_value, timestamp_level):
    """
    时间戳处理器,默认输出的都是UTC时间
    :param input_value: 输入的值
    :param timestamp_level: 需要转化的时间戳的级别，秒级('s')还是毫秒级('ms')
    :return:datetime或者是时间戳(整数或者浮点)
    """
    # 如果输入的是datatime格式，说明是希望转换成时间戳
    if type(input_value) == datetime:
        # 转换成秒级时间戳
        if timestamp_level == 's':
            return input_value.timestamp()
        # 转换成毫秒级时间戳
        if timestamp_level == 'ms':
            return int(input_value.timestamp() * 1000)
    # 如果输入的是时间戳（整数或者浮点），说明是希望转换成datetime类型
    elif type(input_value) == int or type(input_value) == float:
        # 输入的是秒级时间戳
        if timestamp_level == 's':
            input_value = input_value / 1000
            return datetime.fromtimestamp(input_value, tz=timezone.utc)
        # 输入的是毫秒级时间戳
        if timestamp_level == 'ms':
            return datetime.fromtimestamp(input_value, tz=timezone.utc)


@app.route('/')
def root():
    return '这里什么也没有'

@app.route('/JasperGetter/SIMData',methods=['GET'])
def sim_data_getter():
    project= request.args.get('project', '')
    search_value = request.args.get('search_value', '')
    if project == '':
        response = {
            'code': '500',
            'data': {
                'error': '接口调用失败，请传入正确参数！'
            },
            'message': '后台错误！',
            'timeStamp': timestamp_processor(datetime.now(),'ms')
        }
        return jsonify(response), 500
    sim_info_getter = SIMInfoGetter(project, search_value)
    sim_data = sim_info_getter.get_sim_data()
    if sim_data["success"] == True:
        response = {
            'code': '200',
            'data': sim_data,
            'message': '请求成功！',
            'timeStamp': timestamp_processor(datetime.now(), 'ms')
        }
        return jsonify(response), 200
    elif sim_data["success"] == False:
        if sim_data["error_message"] == "cookies_need_update":
            if sim_info_getter.update_cookies():
                sim_data = sim_info_getter.get_sim_data()
                response = {
                    'code': '200',
                    'data': sim_data,
                    'message': '请求成功！',
                    'timeStamp': timestamp_processor(datetime.now(), 'ms')
                }
                return jsonify(response), 200
            else:
                response = {
                    'code': '500',
                    'data': {
                        'error': 'Jasper账号cookies更新失败！'
                    },
                    'message': '后台错误！',
                    'timeStamp': timestamp_processor(datetime.now(), 's')
                }
                return jsonify(response), 500

        else:
            response = {
                'code': '200',
                'data': sim_data,
                'message': '请求成功！',
                'timeStamp': timestamp_processor(datetime.now(), 'ms')
            }
            return jsonify(response), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)


