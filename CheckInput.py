#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import string
import re
import socket # 暂时保留，虽然在本模块中未使用
from adb_shell.adb_device import AdbDeviceTcp
# from adb_shell.auth.sign_m2crypto import M2CryptoSigner # 假设不需要签名者

# --- 辅助函数：替换 GSO，使用 ADB 库执行 Shell 命令 ---

def _execute_adb_shell(ip, port, command):
    """
    内部辅助函数：连接到设备并执行 ADB Shell 命令。
    返回: (成功布尔值, 命令输出字符串)
    """
    try:
        # 尝试连接
        device = AdbDeviceTcp(ip, int(port), default_timeout_s=3)
        device.connect() # 假设不需要签名者

        # 执行命令
        output = device.shell(command)

        # ADB Shell 命令成功执行，返回 True
        return True, output.strip()

    except Exception as e:
        # 连接失败或命令执行失败，返回 False
        return False, str(e)

def _execute_adb_command(ip, port, command):
    """
    内部辅助函数：执行非 shell 的 ADB 命令，如 get-state。
    注意：adb_shell 库通过 'shell' 模拟许多非 shell 命令。
    对于 get-state 这种，我们必须依赖连接的成功与否来判断。
    """
    try:
        device = AdbDeviceTcp(ip, int(port), default_timeout_s=3)
        device.connect()
        # 对于 get-state，连接成功即表示状态为 device
        return True, "device"
    except Exception as e:
        # 连接失败
        return False, str(e)


# --- 状态检查函数 ---

def check_ottx_status(ip, port):
    """检查设备的 PPPoE 账号是否包含 'ottx' 关键字"""
    command = "skget skyworth.params.net.dhcpusr"
    success, info = _execute_adb_shell(ip, port, command)

    if success and "ottx" in info.lower(): # 转换为小写匹配
        return True
    else:
        return False


def check_manufacturer(manufacturer, ip):
    """检查设备的制造商信息"""
    port = "5555" # 假设端口固定为 5555
    command = "getprop ro.product.manufacturer"
    success, info = _execute_adb_shell(ip, port, command)
    
    # 注意：info.strip() 移除了空白字符，便于精确匹配
    if success and manufacturer.upper() in info.strip().upper():
        return True
    else:
        return False


def check_adb_status(ip, port):
    """检查 ADB 连接状态"""
    # 纯 Python ADB 库连接成功即意味着状态为 'device'
    success, info = _execute_adb_command(ip, port, "get-state")
    
    if success and info == 'device':
        return True
    else:
        # 如果 info 中包含 'cannot connect' 或其他连接失败信息，返回 False
        return False

# --- 输入验证函数（修正 Python 逻辑错误） ---

def check_mac(mac):
    """检查 MAC 地址的格式和内容是否为十六进制"""
    mac_original = mac.strip()
    
    if len(mac_original) == 12:
        # 修正：生成器表达式必须用 all() 或 next() 消耗掉
        if all(c in string.hexdigits for c in mac_original):
            return True
    
    elif len(mac_original) == 17:
        if ':' in mac_original:
            mac_clean = mac_original.replace(':', '')
        elif '-' in mac_original:
            mac_clean = mac_original.replace('-', '')
        else:
            return False
            
        if len(mac_clean) == 12 and all(c in string.hexdigits for c in mac_clean):
            return True
            
    return False # 默认失败

def check_sn(sn_head, mac):
    """检查 SN 串码的格式、长度和内容"""
    sn = sn_head + mac
    
    # 修正：生成器表达式必须用 all() 消耗掉
    if all(c in string.hexdigits for c in sn):
        if len(sn) == 32:
            return True
    
    return False

def check_account(account):
    """检查 PPPoE 账号是否为 11 位数字"""
    account = str(account).strip() # 确保是字符串并移除空格
    if len(account) == 11 and account.isdigit():
        return True
    return False


def check_ip(ip):
    """检查 IP 地址格式是否正确 (使用正则表达式)"""
    ip = ip.strip()
    # 修正：使用原始正则表达式，但添加 r'' 保持可读性
    compile_ip = re.compile(r'^(1\d{2}|2[0-4]\d|25[0-5]|[1-9]\d|[1-9])\.(1\d{2}|2[0-4]\d|25[0-5]|[1-9]\d|\d)\.(1\d{2}|2[0-4]\d|25[0-5]|[1-9]\d|\d)\.(1\d{2}|2[0-4]\d|25[0-5]|[1-9]\d|\d)$')
    if compile_ip.match(ip):
        return True
    return False
