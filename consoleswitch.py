#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import time
import telnetlib
import os
import json
import logging


class LogConfig:
    def __init__(self, log_type="console"):
        # 指定日志输出到控制台时的初始化
        if log_type == "console":
            logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        # 指定日志输出到文件的初始化
        elif log_type == "file":
            file_name = 'consoleswitch.log'
            root_logger = logging.getLogger()
            root_logger.setLevel(logging.INFO)
            handler = logging.FileHandler(filename=file_name, encoding='utf-8', mode='a')
            formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
            handler.setFormatter(formatter)
            root_logger.addHandler(handler)

    @staticmethod
    def getlogger():
        logger = logging.getLogger()
        return logger


class TelnetLib(object):

    def __init__(self):
        self.tn = None
        self.EXIT = b'quit\n'
        self.LOGIN = b'Login'
        self.USERNAME = b'Username:'
        self.PASSWORD = b'Password:'
        self.ERROR = b'Error:'

    @staticmethod
    def format(data):
        return data.encode('UTF-8') + b'\n'

    def link(self, host, port=23, timeout=3):
        # 连接设备
        try:
            self.tn = telnetlib.Telnet(host, port, timeout)
            return True
        except Exception:
            LogConfig("file").getlogger().warning('connect to :%s' % host + ' port:%s' % port + ' failed')
            print('连接到:%s' % host + ' 端口:%s' % port + '失败，')
            LogConfig("file").getlogger().warning('Please check the nework,IP address and Telnet Port enabled status.')
            print('请检查网络链接，IP地址是否正确，Telnet是否打开')
            input('按回车继续')
            start_switch()
            return False

    def login(self, username, password):
        log_type = "file"
        logger = LogConfig(log_type).getlogger()
        # 监听登录事件
        self.tn.read_until(self.LOGIN)
        # 监听输入账户事件
        self.tn.read_until(self.USERNAME)
        # 输入账户
        self.tn.write(self.format(username))
        # 监听输入密码事件
        self.tn.read_until(self.PASSWORD)
        # 输入密码
        self.tn.write(self.format(password))
        time.sleep(2)
        command_result = self.tn.read_very_eager().decode('ascii')
        if 'Error: Failed to get domain policy' in command_result:
            logger.error('Error: Failed to get domain policy')
            print('用户名不正确')
            return False
        elif 'Error: Local authentication is rejected' in command_result:
            logger.error('Error: Local authentication is rejected')
            print('登录被拒绝')
            return False
        elif 'Error: Failed to send authen-req' in command_result:
            logger.error('Error: Failed to send authen-req')
            print('发送认证请求失败')
            return False
        elif 'Error: Failed to log in.' in command_result:
            logger.error('Error: Failed to log in.')
            print('登录失败，用户名或密码错误。请修改配置文件')
            return False
        else:
            logger.info('login success.')
            print('登录成功')
            return True

    def shell(self, command):
        # 执行命令
        self.tn.write(self.format(command))
        # 延时0.5s
        time.sleep(1)
        # 在I/O不阻塞的情况下读取所有数据，否则返回空
        data = self.tn.read_very_eager()
        # 解码后返回数据
        return data.decode('UTF-8')

    def exit(self):
        # 退出设备
        self.tn.write(self.EXIT)
        # 关闭连接
        self.tn.close()


class Config:
    @staticmethod
    def setup():
        log_type = "file"
        logger = LogConfig(log_type).getlogger()
        logger.error("config not found.")
        logger.warning("create config File.")
        print('配置文件不存在')
        print("创建配置文件")
        host_ip = input("telnet IP:")
        username = input("用户名:")
        password = input("密码:")
        ottx_vid = input("OTTX_VID:")
        port_start = input("起始端口：")
        port_end = input("结束端口：")
        datafile = open("config.json", 'w')
        config = [{'host_ip': host_ip, 'username': username, 'password': password, 'OTTX_VID': ottx_vid, 'port_start': port_start, 'port_end': port_end, 'vid': '1'}]
        datafile.write(json.dumps(config, sort_keys=True, indent=4, separators=(',', ': ')))
        logger.info('config data: %s' % config)
        datafile.close()


def start_switch():
    while True:
        log_type = "file"
        logger = LogConfig(log_type).getlogger()
        if os.path.exists("config.json"):
            f = open('config.json', 'r', encoding='utf8')
            fp = f.read()
            data = json.loads(fp)
            config = data[0]
            vid = config['vid']
            network = "1"
            ottx = config['OTTX_VID']
            port_start = config['port_start']
            port_end = config['port_end']
            tl = TelnetLib()
            if tl.link(host=config['host_ip'], port=23, timeout=3):
                if tl.login(username=config['username'], password=config['password']):
                    tl.shell(command='system-view')
                    logger.warning('switch to system-view')
                    print('切换到系统视图')
                    tl.shell(command='vlan ' + vid)
                    logger.info('switch to vlan id ' + vid)
                    print('切换到vlan id ' + vid)
                    tl.shell(command='port Ethernet ' + port_start + ' to ' + port_end)
                    logger.info('add port Ethernet ' + port_start + ' to ' + port_end + ' to vlan id ' + vid)
                    print('添加端口 Ethernet ' + port_start + '至' + port_end + ' 到 vlan id ' + vid)
                    tl.shell(command='quit')
                    tl.shell(command='port-group ottx')
                    logger.info('create port-group ottx')
                    print('创建端口组ottx')
                    tl.shell(command='group-member Ethernet ' + port_start + ' to Ethernet ' + port_end)
                    logger.info('group-member Ethernet ' + port_start + ' to Ethernet ' + port_end + ' to ottx')
                    print('端口Ethernet ' + port_start + ' 至 Ethernet ' + port_end + '加入到组ottx')
                    tl.shell(command='shutdown')
                    logger.info('shutdown Ethernet ' + port_start + ' to Ethernet ' + port_end)
                    logger.info('shutdown Ethernet ' + port_start + ' to Ethernet ' + port_end)
                    print('关闭组内所有端口')
                    tl.shell(command='undo shutdown')
                    logger.info('activited Ethernet ' + port_start + ' to Ethernet ' + port_end)
                    print('重启组内所有端口')
                    logger.info('activited Ethernet ' + port_start + ' to Ethernet ' + port_end)
                    tl.exit()
                    if vid == network:
                        w = open("config.json", 'w', encoding='utf8')
                        config['vid'] = ottx
                        logger.info('change configflie vid to ' + ottx)
                        print("改写配置文件vlanID为: %s" % ottx)
                        config = [config]
                        logger.info('config info: %s' % config)
                        w.write(json.dumps(config, sort_keys=True, indent=4, separators=(',', ': ')))
                        w.close()
                        break
                    elif vid == ottx:
                        w = open("config.json", 'w', encoding='utf8')
                        config['vid'] = network
                        logger.info('change configflie vid to ' + network)
                        print("改写配置文件vlanID为: %s" % network)
                        config = [config]
                        logger.info('config info: %s' % config)
                        w.write(json.dumps(config, sort_keys=True, indent=4, separators=(',', ': ')))
                        w.close()
                        break
                    else:
                        w = open("config.json", 'w', encoding='utf8')
                        config['vid'] = network
                        logger.info('change configflie vid to default vld ' + network)
                        print("改写配置文件默认vlanID为: %s" % network)
                        config = [config]
                        logger.info('config info: %s' % config)
                        w.write(json.dumps(config, sort_keys=True, indent=4, separators=(',', ': ')))
                        w.close()
                        break
                else:
                    break
        elif not os.path.exists("config.json"):
            Config.setup()
            continue
        elif not os.access("config.json", os.W_OK):
            logger.warning('配置文件不可写入,请检查权限设置')
            break


start_switch()
