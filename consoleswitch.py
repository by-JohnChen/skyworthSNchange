#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# 用于切换华为交换机vlan
import time
import telnetlib
import os
import json
import logging
from functools import wraps

# --- 全局日志配置控制 ---
# 使用一个全局变量来确保文件日志配置只执行一次
_FILE_LOG_CONFIGURED = False

class LogConfig:
    def __init__(self, log_type="console"):
        global _FILE_LOG_CONFIGURED
        
        # 避免重复配置
        if log_type == "file" and _FILE_LOG_CONFIGURED:
            return

        # 指定日志输出到控制台时的初始化
        if log_type == "console":
            logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        # 指定日志输出到文件的初始化
        elif log_type == "file":
            file_name = 'consoleswitch.log'
            root_logger = logging.getLogger()
            root_logger.setLevel(logging.INFO)
            
            # 检查是否已有FileHandler，防止重复添加（双重保险）
            if not any(isinstance(h, logging.FileHandler) for h in root_logger.handlers):
                handler = logging.FileHandler(filename=file_name, encoding='utf-8', mode='a')
                formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
                handler.setFormatter(formatter)
                root_logger.addHandler(handler)
            
            _FILE_LOG_CONFIGURED = True

    @staticmethod
    def getlogger():
        # 直接获取根Logger，依赖于外部的初始化
        return logging.getLogger()


class TelnetLib(object):

    def __init__(self):
        self.tn = None
        self.EXIT = b'quit\n'
        self.LOGIN = b'Login'
        self.USERNAME = b'Username:'
        self.PASSWORD = b'Password:'
        self.ERROR = b'Error:'
        self.logger = LogConfig.getlogger()

    @staticmethod
    def format(data):
        return data.encode('UTF-8') + b'\n'

    def link(self, host, port=23, timeout=3):
        # 连接设备
        try:
            self.tn = telnetlib.Telnet(host, port, timeout)
            self.logger.info(f'connect to {host}:{port} success')
            return True
        except Exception as e:
            self.logger.warning(f'connect to {host}:{port} failed: {e}')
            print(f'连接到: {host} 端口: {port} 失败。')
            self.logger.warning('Please check the nework,IP address and Telnet Port enabled status.')
            print('请检查网络链接，IP地址是否正确，Telnet是否打开')
            # 移除 start_switch() 的递归调用
            input('按回车键返回主程序或退出...')
            return False

    def login(self, username, password):
        # 监听登录事件
        try:
            self.tn.read_until(self.LOGIN, timeout=5)
            # 监听输入账户事件
            self.tn.read_until(self.USERNAME, timeout=5)
        except EOFError:
             self.logger.error('Telnet connection closed unexpectedly before login prompt.')
             print('Telnet连接意外中断，无法到达登录提示。')
             return False

        # 输入账户
        self.tn.write(self.format(username))
        # 监听输入密码事件
        self.tn.read_until(self.PASSWORD, timeout=5)
        # 输入密码
        self.tn.write(self.format(password))
        time.sleep(2)
        
        command_result = self.tn.read_very_eager().decode('ascii', errors='ignore')
        
        # 统一处理登录失败的情况
        if 'Error:' in command_result or 'Failure' in command_result:
            if 'Error: Failed to get domain policy' in command_result:
                self.logger.error('Login failed: Failed to get domain policy')
                print('用户名不正确')
            elif 'Error: Local authentication is rejected' in command_result:
                self.logger.error('Login failed: Local authentication is rejected')
                print('登录被拒绝')
            elif 'Error: Failed to send authen-req' in command_result:
                self.logger.error('Login failed: Failed to send authen-req')
                print('发送认证请求失败')
            elif 'Error: Failed to log in.' in command_result:
                self.logger.error('Login failed: Failed to log in.')
                print('登录失败，用户名或密码错误。请修改配置文件')
            else:
                 self.logger.error(f'Login failed with unspecific error: {command_result.strip()}')
                 print('登录失败，请检查用户名、密码或设备状态。')
            return False
        else:
            self.logger.info('login success.')
            print('登录成功')
            return True

    def shell(self, command):
        # 执行命令
        self.tn.write(self.format(command))
        # 延时0.5s
        time.sleep(0.5) # 缩短延时，提高效率
        # 在I/O不阻塞的情况下读取所有数据，否则返回空
        data = self.tn.read_very_eager()
        # 解码后返回数据
        return data.decode('UTF-8', errors='ignore')

    def exit(self):
        # 退出设备
        self.tn.write(self.EXIT)
        # 关闭连接
        self.tn.close()


class Config:
    @staticmethod
    def setup():
        logger = LogConfig.getlogger()
        logger.error("config not found.")
        logger.warning("create config File.")
        print('配置文件不存在')
        print("创建配置文件")
        
        # 强制要求输入有效值
        host_ip = input("telnet IP:").strip()
        username = input("用户名:").strip()
        password = input("密码:").strip()
        ottx_vid = input("OTTX_VID (目标VLAN ID):").strip()
        port_start = input("起始端口 (如 0/0/1):").strip()
        port_end = input("结束端口 (如 0/0/24):").strip()

        datafile = open("config.json", 'w', encoding='utf-8')
        
        # 默认 vid 设置为 '1' (网络VLAN)
        config = [{'host_ip': host_ip, 'username': username, 'password': password, 'OTTX_VID': ottx_vid, 'port_start': port_start, 'port_end': port_end, 'vid': '1'}]
        datafile.write(json.dumps(config, sort_keys=True, indent=4, separators=(',', ': ')))
        logger.info(f'config data written: {config}')
        datafile.close()


def start_switch():
    # --- 1. 确保文件日志仅配置一次 ---
    LogConfig("file")
    logger = LogConfig.getlogger()
    
    # 允许无限循环尝试（或直到成功/用户退出）
    while True:
        
        # --- 2. 检查配置文件 ---
        if os.path.exists("config.json"):
            try:
                with open('config.json', 'r', encoding='utf8') as f:
                    data = json.loads(f.read())
                
                # 确保配置格式正确
                if not data or not isinstance(data, list) or not isinstance(data[0], dict):
                    logger.error("config.json file content format error.")
                    print("配置文件内容格式错误，请删除后重新生成。")
                    input("按回车继续")
                    break
                    
                config = data[0]
                
                # 强制转换为字符串，确保在命令中安全使用
                vid = str(config['vid'])
                network = "1" # 默认网络VLAN
                ottx = str(config['OTTX_VID'])
                port_start = str(config['port_start'])
                port_end = str(config['port_end'])
                
            except Exception as e:
                logger.error(f"Failed to read or parse config.json: {e}")
                print("读取或解析配置文件失败，请检查文件内容或权限。")
                input("按回车继续")
                break
            
            # --- 3. Telnet 连接和登录 ---
            tl = TelnetLib()
            if not tl.link(host=config['host_ip'], port=23, timeout=3):
                # link失败，回到while循环开头，等待用户输入后重试
                continue
            
            if not tl.login(username=config['username'], password=config['password']):
                # login失败，退出程序
                tl.exit()
                break

            # --- 4. 配置命令序列 ---
            try:
                # 切换到系统视图
                tl.shell(command='system-view')
                logger.info('switch to system-view')
                print('切换到系统视图')
                
                # 配置VLAN ID
                tl.shell(command=f'vlan {vid}')
                logger.info(f'switch to vlan id {vid}')
                print(f'切换到vlan id {vid}')
                
                # 将端口加入该VLAN
                tl.shell(command=f'port Ethernet {port_start} to {port_end}')
                logger.info(f'add port Ethernet {port_start} to {port_end} to vlan id {vid}')
                print(f'添加端口 Ethernet {port_start} 至 {port_end} 到 vlan id {vid}')
                
                # 退出VLAN视图
                tl.shell(command='quit')
                
                # 创建并配置端口组
                tl.shell(command='port-group ottx')
                logger.info('create port-group ottx')
                print('创建端口组ottx')
                
                tl.shell(command=f'group-member Ethernet {port_start} to Ethernet {port_end}')
                logger.info(f'group-member Ethernet {port_start} to Ethernet {port_end} to ottx')
                print(f'端口Ethernet {port_start} 至 Ethernet {port_end} 加入到组ottx')
                
                # 重启端口组
                tl.shell(command='shutdown')
                logger.info(f'shutdown port-group ottx (Ethernet {port_start} to Ethernet {port_end})')
                print('关闭组内所有端口')
                
                # 增加延时，确保端口关闭完成
                time.sleep(1) 
                
                tl.shell(command='undo shutdown')
                logger.info(f'activited port-group ottx (Ethernet {port_start} to Ethernet {port_end})')
                print('重启组内所有端口')
                
                # 退出端口组视图
                tl.shell(command='quit') 
                
                # 退出Telnet连接
                tl.exit()

                # --- 5. 更新配置文件并退出 ---
                with open("config.json", 'w', encoding='utf8') as w:
                    if vid == network:
                        config['vid'] = ottx
                        new_vid = ottx
                    elif vid == ottx:
                        config['vid'] = network
                        new_vid = network
                    else:
                        # 如果 vid 既不是 network 也不是 ottx，则重置为 network
                        config['vid'] = network
                        new_vid = network
                        logger.warning(f'current vid {vid} invalid, change config to default vlan {network}')

                    logger.info(f'change configfile vid to {new_vid}')
                    print(f"操作完成，下次运行将切换到VLAN ID: {new_vid}")
                    
                    config_list = [config] # 重新封装成列表
                    w.write(json.dumps(config_list, sort_keys=True, indent=4, separators=(',', ': ')))
                    
                break # 成功完成操作，退出while循环
                
            except Exception as e:
                logger.error(f"Telnet command sequence failed: {e}")
                print(f"执行 Telnet 命令序列时发生错误: {e}")
                tl.exit()
                break # 命令执行失败，退出程序

        # --- 6. 配置文件不存在或不可写 ---
        elif not os.path.exists("config.json"):
            Config.setup()
            # setup完成后回到while循环开头，尝试读取新生成的配置
            continue
            
        elif not os.access("config.json", os.W_OK):
            logger.warning('配置文件不可写入,请检查权限设置')
            print('配置文件不可写入,请检查权限设置')
            break

# 主程序入口
if __name__ == '__main__':
    start_switch()
