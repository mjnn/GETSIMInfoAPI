import time

import requests
from selenium import webdriver
from selenium.common import TimeoutException
import json
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime, timezone
from urllib.parse import urlencode
import logging


# 配置日志格式、级别和输出方式
handlers = [
    logging.StreamHandler(),  # 输出到终端
    logging.FileHandler("app.log", encoding="utf-8",mode='w')  # 输出到文件（可选）
]

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=handlers,  # 输出到终端  # 日志写入文件
)

def log_method(func):
    '''
    装饰器，用于给每个函数在运行前和后添加打印，用于后续日志
    :param func:
    :return:
    '''
    def wrapper(*args, **kwargs):
        logging.info(f"========Start of {func.__name__}========")
        result = func(*args, **kwargs)
        logging.info(f"========End of {func.__name__}========")
        return result
    return wrapper


class SIMInfoGetter:
    def __init__(self, project = None, search_value = None):
        logging.info('新建实例对象项目为：%s', project)
        # 需要查询的MOS项目
        self.__project__ = project
        # 传入的搜索值，ICCID或者VIN
        self.__search_value__ = search_value
        # cookie file文件路径
        self.cookies_file_path = 'config/cookies_for_request.json'
        # 当前项目的cookies_dict
        self.__project_cookies_dict__ = {}
        # 加载Cookie数据
        self.load_cookies()
        logging.debug('当前项目cookies的全局字典为：%s', json.dumps(self.__project_cookies_dict__, indent=4))

    @staticmethod
    @log_method
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
                input_value = input_value/1000
                return datetime.fromtimestamp(input_value, tz=timezone.utc)
            # 输入的是毫秒级时间戳
            if timestamp_level == 'ms':
                return datetime.fromtimestamp(input_value, tz=timezone.utc)

    @log_method
    def load_cookies(self):
        """
        用于加载cookies
        :return:直接修改全局变量 self.__project_cookies_dict__，返回True和False
        """
        all_cookies_json = {}
        try:
            logging.info('尝试打开cookies json文件')
            # 能够打开文件并且读取到数据
            all_cookies_json = self.read_all_cookies()
            try:
                # 提取当前项目的request cookies dict
                self.__project_cookies_dict__ = all_cookies_json[self.__project__]
                # 如果Cookie列表里面包含当前项目
                logging.info("cookies文件内容包含当前项目")
                logging.debug('成功获得当前项目cookies字典：%s', json.dumps(self.__project_cookies_dict__, indent=4))
                return True
            except KeyError as e:
                # Cookie列表里面没有当前项目，则在字典中创建当前项目键值的空列表并开始更新Cookie
                logging.debug('cookies文件内容缺少字段：%s', e)
                logging.info("cookies文件内容没有包含当前项目")
                logging.info("开始获取当前项目的cookies")
                return self.update_cookies()
        # 文件未找到,则创建文件并开始更新cookie
        except FileNotFoundError:
            logging.info('cookies文件不存在')
            logging.info("创建cookies文件")
            logging.info("开始获取当前项目的cookies")
            return self.update_cookies()
        # 文件为空的话就更新Cookie进去
        except json.decoder.JSONDecodeError:
            logging.info("cookies文件为空")
            logging.info("开始获取当前项目的cookies")
            return self.update_cookies()

    @log_method
    def process_cookies_dict(self):
        """
        处理cookies_dict
        :return: 返回处理后的cookies_dict
        """
        cookies_dict = {}
        cookies_list_from_webdriver = self.webdriver_cookies_getter()
        logging.debug(f'webdriver获取到的cookies list为：{json.dumps(cookies_list_from_webdriver, indent=4)}')
        # 如果cookies_list不为空
        if cookies_list_from_webdriver:
            cookies_dict = {cookie['name']:cookie['value'] for cookie in cookies_list_from_webdriver}
            logging.debug(f'处理后的cookies dict:{json.dumps(cookies_dict, indent=4)}')
            return cookies_dict
        else:
            return cookies_dict

    @log_method
    def webdriver_cookies_getter(self):
        """
        用于执行webdriver登录
        :return: 返回获取到的cookies_dict
        """
        # 初始化webdriver
        # 加载配置文件中的用户名和密码
        logging.debug('开始加载配置文件内容：')
        with open('.\\config\\mno_account.json', 'r') as f:
            mno_account_info_dict = json.load(f)
            username = mno_account_info_dict[self.__project__]['ID']
            password = mno_account_info_dict[self.__project__]['PW']
            logging.debug('用户名和密码配置加载完成')
        # 加载配置文件中的链接和元素
        with open('.\\config\\url_and_element.json', 'r') as f:
            url_and_element_dict = json.load(f)
            url_login = url_and_element_dict['urls']['Jasper_login']
            url_home = url_and_element_dict['urls']['Jasper_Homepage']
            element_xpath_dict = url_and_element_dict['element_xpath']
            logging.debug('url和页面元素配置加载完成')
        options = Options()
        # options.add_argument("--headless")  # 无头模式
        options.add_argument("--no-sandbox")  # 禁用沙盒（Docker 需要）
        options.add_argument("--disable-dev-shm-usage")  # 避免内存问题

        # 初始化 WebDriver
        driver = webdriver.Chrome(
            # 自动检测浏览器版本并下载对应驱动
            service=Service(ChromeDriverManager().install()),
            options=options
        )

        driver.get(url_login)  # 正常访问网页
        logging.info('访问： %s', url_login)

        try:
            with open('config/cookies_for_webdriver.json', 'r') as f:
                logging.info('读取cookies_for_webdriver')
                try:
                    cookies_for_webdriver = json.load(f)
                except json.decoder.JSONDecodeError:
                    logging.info('cookies_for_webdriver没有内容')
                    cookies_for_webdriver = {}
            if cookies_for_webdriver != {} and self.__project__ in cookies_for_webdriver.keys():
                logging.info('开始加载cookies到webdriver')
                driver.delete_all_cookies()
                for cookie in cookies_for_webdriver[self.__project__]:
                    driver.add_cookie(cookie)
                driver.get(url_login)
                logging.info('刷新driver完成')
                logging.debug(f'当前页面名：{driver.title}')
                if 'Welcome to the Control Center!' in driver.title:
                    pass
                elif '欢迎' in driver.title:
                    logging.info('登录成功')
                    cookies_list = driver.get_cookies()
                    return cookies_list
            else:
                logging.info('cookies_for_webdriver没有当前项目的内容')
                logging.info('开始获取cookies for webdriver')
                pass
        except FileNotFoundError:
            pass
        logging.info('开始更新cookies')
        cookies_list = self.webdriver_login(driver, element_xpath_dict, username, password)
        return cookies_list



    def webdriver_login(self,driver,element_xpath_dict,username,password):
        logging.info('开始Webdriver登录')
        # 找到用户名、密码和登录按钮
        try:
            # 输入用户名和密码
            username_input_box = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, element_xpath_dict['Input_box']['login_username']))
            )
            username_input_box.send_keys(username)
            password_input_box = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, element_xpath_dict['Input_box']['login_password']))
            )
            password_input_box.send_keys(password)
            logging.info('输入用户名和密码')
            # 提交登录表单
            login_button = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, element_xpath_dict['button']['login_submit']))
            )
            login_button.click()
            logging.info('点击登录')
            logging.debug(f'当前Webdriver中的cookies:{driver.get_cookies()}')
        except TimeoutException:
            logging.info('10秒内未找到元素')
            cookies_dict = []
            return cookies_dict
        while True:
            try:
                # 通过检查SIM卡搜索框有没有出现来判断检查是否登录成功
                WebDriverWait(driver, 30).until(
                    EC.title_contains('欢迎')
                    # EC.presence_of_element_located((By.XPATH, element_xpath_dict['Input_box']['search_sim']))
                )
                logging.info('登录成功')
                cookies_list = driver.get_cookies()
                # 删除所有的有效期字段
                # for cookie in cookies_list:
                #     if 'expiry' in cookie.keys():
                #         del cookie['expiry']
                logging.info('写入新的cookies到cookies_for_webdriver.json')
                with open('.\\config\\cookies_for_webdriver.json', 'r') as f:
                    # 有内容则加载到cookies_dict中
                    try:
                        cookies_dict = json.load(f)
                    # 没有内容则令cookies_dict为空
                    except json.decoder.JSONDecodeError:
                        cookies_dict = {}
                    logging.debug('加载cookies_for_webdriver.json中的内容')
                with open('.\\config\\cookies_for_webdriver.json', 'w') as f:
                    # 打开cookies_for_webdriver.json并写入当前项目的cookies_list
                    cookies_dict[self.__project__] = cookies_list
                    f.write(json.dumps(cookies_dict, indent=4))
                    logging.debug('写入当前项目cookies_list到cookies_for_webdriver.json')
                driver.close()
                logging.info('关闭浏览器')
                return cookies_list
            except TimeoutException:
                logging.info('10秒内未找到元素')
                if driver.title == '身份验证':
                    logging.info('请输入邮箱验证码！')
                    continue
                elif 'Welcome' in driver.title:
                    continue
                else:
                    print(driver.title)
                    cookies_list = []
                    logging.error('读取页面数据的时候遇到未知错误')
                    return cookies_list

    @log_method
    def mno_get_request(self,request_name,search_value):
        """
        构建jasper API的请求
        :param request_name: 请求名,参照http_request_parameter.json
        :param search_value: 请求的搜索值
        :return:
        """
        # 处理加载cookies
        cookies = ';'.join([f'{key}={value}' for key, value in self.__project_cookies_dict__.items()]),
        cookies = cookies[0]
        logging.debug('对该请求载入cookies:\n %s', cookies)
        # 根据输入的参数加载配置文件中的请求参数
        with open('.\\config\\http_request_parameter.json', 'r') as f:
            request_info_dict = json.load(f)
            base_url = request_info_dict[request_name]['base_url']
            logging.debug('加载Base url: \n %s', base_url)
            # 获取查询字符串
            request_args = request_info_dict[request_name]['request_args']
            search_args = request_info_dict[request_name]['request_args']['search']
            # 获取查询字符串
            param_dict = {
                "timestamp_now" : self.timestamp_processor(datetime.now(),'ms'),
                "search_value" : search_value
            }
            search_args = self.replace_placeholder(search_args,param_dict)
            request_args = self.replace_placeholder(request_args,param_dict)
            search_args = json.dumps(search_args)
            request_args['search']=search_args
            logging.debug('加载查询字符串：\n %s', json.dumps(request_args,indent=4))
            # 查询字符串编码
            query_string = urlencode(request_args)
            logging.debug('编码后的查询字符串：\n %s', query_string)
            headers = request_info_dict[request_name]['headers']
            param_dict = {
                'cookies' : cookies
            }
            headers = self.replace_placeholder(headers,param_dict)
            logging.debug('加载请求头：\n %s', headers)
        # 拼接请求url
        url = base_url + '?' + query_string
        logging.debug('拼接请求结果：\n %s', url)
        # 加载请求头发送请求
        response = requests.get(url, headers=headers)
        # 加载相应内容为字典
        response_data_dict = json.loads(response.text)
        logging.debug('加载请求响应结果到字典：\n %s', json.dumps(response_data_dict, indent=4))
        return response_data_dict

    @log_method
    def replace_placeholder(self, target_root_dict, param_dict=None):
        """
        递归替换占位符，支持字典嵌套列表、列表嵌套字典
        :param target_root_dict: 配置文件读取出来的字典
        :param param_dict: 需要替换的参数字典
        :return: 处理后的 target_root_dict
        """
        #判断当前根节点是否为字典
        if isinstance(target_root_dict, dict):
            # 遍历字典的每一个键值对
            for key, value in target_root_dict.items():
                # 判断当前值是否为字典或列表，如果是则递归调用本函数
                if isinstance(value, (dict, list)):
                    self.replace_placeholder(value, param_dict)
                #  判断当前值是否为字符串且以{}开头结尾，如果是则替换
                elif isinstance(value, str) and value.startswith('{') and value.endswith('}'):
                    param_name = value.strip('{}')
                    target_root_dict[key] = param_dict[param_name]
        # 判断当前根节点是否为列表
        elif isinstance(target_root_dict, list):
            #  遍历列表的每一个元素
            for i, item in enumerate(target_root_dict):
                #  判断当前元素是否为字典或列表，如果是则递归调用本函数
                if isinstance(item, (dict, list)):
                    self.replace_placeholder(item, param_dict)
                # 判断当前元素是否为字符串且以{}开头结尾，如果是则替换
                elif isinstance(item, str) and item.startswith('{') and item.endswith('}'):
                    param_name = item.strip('{}')
                    target_root_dict[i] = param_dict[param_name]
        return target_root_dict

    @log_method
    def if_cookies_need_update(self):
        '''
        用于检查cookies是否需要更新
        :return: bool值
        '''
        logging.info(f'检查{self.__project__}项目是否需要更新cookies')
        response_data_dict = self.mno_get_request('get_sim_id')
        try:
            if response_data_dict['errorMessage'] == 'Full authentication is required to access this resource':
                logging.info(f'{self.__project__}项目需要更新cookies')
                return True
            else:
                logging.debug(f'未知errorMessage%r', response_data_dict)
                logging.info(f'{self.__project__}项目不需要更新cookies')
                return False
        except KeyError:
            logging.debug('响应中没有找到errorMessage')
            logging.info(f'{self.__project__}项目不需要更新cookies')
            return False

    @log_method
    def update_cookies(self):
        '''
        该方法会更新cookies_for_request.json，并赋值当前项目cookies的全局变量__project_cookies_dict__
        :return:bool值
        '''
        all_cookies_json = self.read_all_cookies()
        all_cookies_json[self.__project__] = self.process_cookies_dict()
        if all_cookies_json[self.__project__] != {}:
            logging.info("开始写入当前项目cookies到cookies文件")
            with open(self.cookies_file_path, 'w') as f:
                f.write(json.dumps(all_cookies_json, indent=4))
                logging.info('当前项目cookies已经写入到cookies文件中')
        else:
            return False
        self.__project_cookies_dict__ = all_cookies_json[self.__project__]
        logging.debug('成功更新当前项目cookies的全局字典：%s', json.dumps(self.__project_cookies_dict__, indent=4))
        return True

    @log_method
    def read_all_cookies(self):
        '''
        :return:
        返回请求用的cookie dict，
        格式为：
        {
            "GP": {
            "jsAuthCookie--1270725091": "\"{n2pUb+qwJF3l2zveyFjlkw==}fWCjsYcW8vIIZ5+iiodlb4/rwndiu1DGYBgTN9kX3mFyHNkeOrgzP/FgrjK50+ER\"",
            "userPreferences": "{\"lang\":\"emhfQ04=\"}",
            "jsSessionCookie": "\"{/EIkGxr4qx7PS/ptZRbr0w==}cj7qAZYNF8z6a1zTh+ya8Ed3cQjCC3oLaET81SE1TaAgub2HdKBaZaHQqzv0PZOLD+kEBoKhwiDJ3TazDnqU4O5HdhmnAjfzxeu2DzJkpiYCpVliXCBcUTp4H5wyRShj\"",
            "JSESSIONID": "281135B2BD84574104EF69A88706E1DD",
            "jsDeviceCookie--1270725091": "\"{WfCJb8Ahd9gFAS3VNslPAw==}DPkf+zRqJCOiJXmcdNrpXEjCpNkp6RZ3fESrtqC+5iHv3IAaWiGfpmbbNASuCeUH\"",
            "BIGipServer~POD26~POOL_POD26_PGW": "!FsKDRUJWqYxqfQizzFNuNiVq2a4Ry+IAMd0wNq9Wn60saQmrr8+nvyeAjVsoNkABNjUogMupxuUzYEE="
            }，
            "CEI":{},
            "Audi_5G":{}
        }

        '''
        with open(self.cookies_file_path, 'r') as f:
            logging.info('cookies文件存在')
            # 如果文件有内容则直接赋值到变量
            try:
                all_cookies_json = json.load(f)
                logging.info('cookies文件有内容')
            except json.decoder.JSONDecodeError:
                all_cookies_json = {}
                logging.info('cookies文件无内容')
            logging.debug('all_cookies_json：%s', json.dumps(all_cookies_json, indent=4))
            return all_cookies_json

    @log_method
    def get_sim_data(self):
        '''
        发起两个请求，一个用于获取SIM卡基础信息和simId，一个用于查SIM卡变更历史
        :return: 返回一个字典，为全部SIM卡信息
        '''
        response = self.mno_get_request('sim_basic_data', self.__search_value__)
        if "totalCount" in response:
            sim_data = {}
            if response["totalCount"] == 0:
                result = {"success":False,"error_message":"can_not_find_sim"}
                return result
            elif response["totalCount"] > 1:
                result = {"success":False,"error_message":"more_than_one_sim"}
                return result
            elif response["totalCount"] == 1:
                sim_basic_data = response["data"]
                sim_id = sim_basic_data[0]["simId"]
                iccid = sim_basic_data[0]["iccid"]
                imei = sim_basic_data[0]["simAuxFieldsDTO"]["imei"]
                bound_vin = sim_basic_data[0]["custom1"]
                brand = sim_basic_data[0]["custom2"]
                lifecycle = sim_basic_data[0]["custom3"]
                session_type_now = sim_basic_data[0]["sessionType"]
                device_type = sim_basic_data[0]["simAuxFieldsDTO"]["custom9"]
                activation_datetime = self.timestamp_processor(sim_basic_data[0]["activationDate"],'s').strftime("%Y-%m-%d %H:%M:%S")
                sim_basic_data = {
                    "sim_id":sim_id,
                    "iccid": iccid,
                    "imei": imei,
                    "bound_vin": bound_vin,
                    "brand": brand,
                    "lifecycle": lifecycle,
                    "session_type_now": session_type_now,
                    "device_type": device_type,
                    "activation_datetime": activation_datetime,
                }
                logging.debug('sim_basic_data：%s', json.dumps(sim_basic_data, indent=4))

                response = self.mno_get_request('sim_change_history', str(sim_id))
                sim_change_history = {}
                if response["success"]:
                    sim_change_history_response = response["data"]
                    for record in sim_change_history_response:
                        change_type = record["changeTypeDisplay"]
                        target_value = record["targetValue"]
                        source_value = record["sourceValue"]
                        start_time = self.timestamp_processor(record["startTime"],'s').strftime("%Y-%m-%d %H:%M:%S")
                        end_time = self.timestamp_processor(record["endTime"],'s').strftime("%Y-%m-%d %H:%M:%S")
                        change_by = record["userName"]
                        sim_data["success"] = True
                        sim_change_history[change_type] = {
                                "target_value":target_value,
                                "source_value":source_value,
                                "start_time":start_time,
                                "end_time":end_time,
                                "change_by":change_by
                            }
                elif not response["success"]:
                    sim_data["success"] =False
                sim_data["sim_basic_data"] = sim_basic_data
                sim_data["sim_change_history"] = sim_change_history
                return sim_data
        else:
            if response["errorMessage"] == "Full authentication is required to access this resource":
                logging.info("cookies需要更新")
                result = {"success":False,"error_message": "cookies_need_update"}
                return result
            else:
                logging.info("未知错误")
                result = {"success":False,"error_message": "unknown_error"}
                return result
