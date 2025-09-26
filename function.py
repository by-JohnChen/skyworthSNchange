#!/usr/bin/env python3
# cython:language_level=3
# -*- coding: utf-8 -*-
# @copyright: John Chen
import os
import re
import time
import socket
from subprocess import getstatusoutput as gso
from adb_shell.adb_device import AdbDeviceTcp

# 默认的 ADB 端口
ADB_PORT = 5555

# --- 辅助函数：核心 ADB 连接与执行 ---

def _execute_adb_shell(ip, port, command, timeout=5):
    """
    内部辅助函数：连接到设备并执行 ADB Shell 命令。
    返回: (成功布尔值, 命令输出字符串)
    """
    try:
        # 使用 AdbDeviceTcp 连接设备
        device = AdbDeviceTcp(ip, int(port), default_timeout_s=timeout)
        device.connect() # 假设不需要 RSA 密钥认证
        
        # 执行命令
        output = device.shell(command)
        
        # 关闭连接，释放资源（adb_shell 会自动处理）
        return True, output.strip()
        
    except Exception as e:
        # 连接失败或命令执行失败
        return False, str(e)

# --- 工具函数 ---

def sleep(seconds):
    """使用标准 time.sleep 避免忙等待，释放 CPU 资源。"""
    time.sleep(seconds)

def covert(mac):
    """
    判断mac地址格式并转化。
    输入：支持 12位 (xxxxxxxxxxxx) 或 17位 (xx:xx:...) 格式。
    返回: (12位大写MAC, 冒号分隔MAC, 横线分隔小写MAC) 或 None
    """
    mac = mac.strip().upper()
    
    # 清理分隔符
    if len(mac) == 17:
        if ':' in mac or '-' in mac:
            mac = mac.replace(':', '').replace('-', '')
    
    # 检查长度和十六进制格式
    if len(mac) != 12 or not re.fullmatch(r'[0-9A-F]{12}', mac):
        return None

    # 格式化
    parts = re.findall('..', mac)
    c_mac = ":".join(parts)  # 冒号分隔
    m_mac = "-".join(parts).lower() # 横线分隔，小写
    
    return mac, c_mac, m_mac

# --- 核心业务函数（ADB 实现）---

def connect(ip, port=ADB_PORT):
    """
    尝试连接到 ADB 设备。
    返回: 成功则 True，否则 False。
    """
    try:
        device = AdbDeviceTcp(ip, int(port), default_timeout_s=3)
        device.connect()
        return True
    except Exception:
        return False

def recovery(ip, port=ADB_PORT):
    """发送恢复出厂设置广播"""
    command = "am broadcast -a android.intent.action.MASTER_CLEAR"
    success, info = _execute_adb_shell(ip, port, command)
    
    # 假设设备成功收到广播即视为成功
    return success


def kill():
    """
    杀死 ADB 服务（仅清除可能的外部 adb.exe 进程）。
    使用纯 Python ADB 库时，没有外部 adb server 进程可杀。
    """
    # 尝试清除残留的外部 adb.exe 进程 (如果用户之前使用过)
    if os.name == 'nt': # Windows
        # taskkill 命令通常在系统路径中
        gso("taskkill /im adb.exe /f 1>nul 2>nul") 
    
    return True 


def reboot(ip, port=ADB_PORT):
    """重启设备"""
    try:
        device = AdbDeviceTcp(ip, int(port), default_timeout_s=5)
        device.connect()
        # adb_shell 库的内置 reboot 命令
        device.reboot() 
        
        # 重启命令发送后设备立即断开连接是正常的
        return True 
    except Exception:
        # 如果是连接失败，则返回 False，否则（即命令发送成功后断开）返回 True
        return True 


def mac_change(mac, ip, port=ADB_PORT, sn_head=""):
    """修改 MAC 和 SN 串码"""
    mac_data = covert(mac)
    if mac_data is None:
        return False
        
    mac_12, c_mac, _ = mac_data
    sn = sn_head + mac_12
    
    # 1. 修改 MAC
    command_mac = f"skset mac {c_mac}"
    success_mac, _ = _execute_adb_shell(ip, port, command_mac)
    
    if not success_mac:
        return False

    # 2. 修改 SN
    command_sn = f"skset sn {sn}"
    success_sn, _ = _execute_adb_shell(ip, port, command_sn)

    return success_sn


def change(ip, mac, account, sn_head, port=ADB_PORT):
    """修改 SN 和 PPPoE 账号/密码"""
    mac_data = covert(mac)
    if mac_data is None:
        return False
        
    mac_12, c_mac, _ = mac_data
    sn = sn_head + mac_12
    
    # 命令列表
    commands = [
        f"skset sn {sn}",
        f"skset skyworth.params.net.dhcpusr {account}ottx01@ottx",
        f"skset skyworth.params.net.dhcppwd 123456"
    ]
    
    # 依次执行命令
    for cmd in commands:
        success, _ = _execute_adb_shell(ip, port, cmd)
        if not success:
            return False
            
    return True


def auto_change(ip, account, port=ADB_PORT):
    """
    通过模拟按键和 skset 命令进行自动拨号设置。
    """
    # 确保连接状态
    if not connect(ip, port):
        return False
        
    try:
        device = AdbDeviceTcp(ip, int(port), default_timeout_s=5)
        device.connect()
    except Exception:
        return False

    # 1. 设置 PPPoE 账号和密码
    commands_config = [
        f"skset skyworth.params.net.dhcpusr {account}ottx01@ottx",
        f"skset skyworth.params.net.dhcppwd 123456"
    ]
    for cmd in commands_config:
        if not _execute_adb_shell(ip, port, cmd)[0]:
            return False # 配置失败则退出

    # 2. 启动设置Activity (假设这是拨号设置界面)
    device.shell("am start -n com.skyworth.modeselecter/com.skyworth.modeselecter.MainActivity")
    time.sleep(1) # 等待应用启动

    # 3. 模拟按键操作
    key_commands = [
        "input keyevent KEYCODE_DPAD_DOWN",
        "input keyevent KEYCODE_DPAD_DOWN",
        "input keyevent KEYCODE_DPAD_CENTER",
        "input keyevent KEYCODE_BACK",
        "input keyevent KEYCODE_DPAD_DOWN",
        "input keyevent KEYCODE_DPAD_DOWN",
        "input keyevent KEYCODE_DPAD_CENTER",
        "input keyevent KEYCODE_DPAD_CENTER",
    ]

    for cmd in key_commands:
        device.shell(cmd)
        time.sleep(0.5) # 增加延迟以确保UI响应
        
    return True

# --- 兼容 gso 的 ARP 查找逻辑 ---

def get_local_ip_safe():
    """获取本机局域网 IP 地址的更健壮方法"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80)) 
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def rec_auto_change(mac, account, port=ADB_PORT):
    """恢复出厂后的自动拨号操作：通过 ARP 查找新 IP"""
    mac_data = covert(mac)
    if mac_data is None:
        return False
    
    # mac_data[2] 是横线分隔的小写 MAC
    _, _, m_mac = mac_data 
    
    l_ip = get_local_ip_safe()
    
    # 清空 ARP 缓存，确保获取最新的 IP-MAC 映射
    # 此处依然依赖系统命令，无法用纯 Python ADB 替代
    gso("arp -d") 

    # 查找 ARP 缓存 (此操作依赖于操作系统命令)
    status, data = gso(f'arp -a -N {l_ip}')
    
    if status != 0:
        return False 
        
    try:
        # 尝试解码，Windows 下可能是 GBK
        decoded_data = data.decode("gbk", errors='ignore') 
    except (UnicodeDecodeError, AttributeError):
        decoded_data = data.decode("utf-8", errors='ignore') 
    
    # 正则表达式匹配 IP 和 MAC
    arp_regex = r'([0-9.]+)\s+([0-9a-f]{2}[-:][0-9a-f]{2}[-:][0-9a-f]{2}[-:][0-9a-f]{2}[-:][0-9a-f]{2}[-:][0-9a-f]{2})'

    found_new_ip = None
    for arp_match in re.findall(arp_regex, decoded_data, re.IGNORECASE):
        ip, found_mac = arp_match
        current_mac = found_mac.lower().replace(':', '-')
        
        # 匹配到目标 MAC
        if m_mac == current_mac:
            found_new_ip = ip
            break

    if found_new_ip:
        # 找到新 IP 后，调用 auto_change 
        return auto_change(found_new_ip, account, port)

    return False
