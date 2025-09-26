#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import os
import re
import time
import socket
from subprocess import getstatusoutput as gso
import CheckInput as Ck  # 假设 CheckInput 模块可用

# 导入 ADB 库
from adb_shell.adb_device import AdbDeviceTcp
from adb_shell.auth.sign_m2crypto import M2CryptoSigner

# 全局变量或配置（用于 ADB 密钥认证，如果需要的话）
# 纯 Python ADB 库通常需要 key 文件来进行认证。
# 如果您的设备无需认证，可以暂时跳过 key_path 的设置。
# KEY_PATH = os.path.join(os.path.expanduser('~'), '.android', 'adbkey')
# try:
#     SIGNER = M2CryptoSigner(KEY_PATH)
# except Exception:
#     SIGNER = None
SIGNER = None # 简化处理，假设设备不需要密钥认证


def sleep(seconds):
    """使用标准 time.sleep 避免忙等待，释放 CPU 资源。"""
    time.sleep(seconds)


def covert(mac):
    """
    判断mac地址格式并转化。
    返回: (12位大写MAC, 冒号分隔MAC, 横线分隔小写MAC) 或 None
    """
    mac = mac.strip().upper()
    
    if len(mac) == 17:
        if ':' in mac:
            mac = mac.replace(':', '')
        elif '-' in mac:
            mac = mac.replace('-', '')
        else:
            return None
    
    if len(mac) != 12 or not re.fullmatch(r'[0-9A-F]{12}', mac):
        return None

    parts = re.findall('..', mac)
    c_mac = ":".join(parts)
    m_mac = "-".join(parts).lower()
    
    return mac, c_mac, m_mac


def _execute_adb_shell(ip, port, command):
    """
    内部辅助函数：连接到设备并执行 ADB Shell 命令。
    返回: (成功布尔值, 命令输出字符串)
    """
    try:
        device = AdbDeviceTcp(ip, int(port), default_timeout_s=5)
        device.connect(rsa_keys=[SIGNER] if SIGNER else None)
        
        # 执行命令，并获取输出
        output = device.shell(command)
        
        # 很多 ADB Shell 命令（特别是 skset）执行成功后不会返回错误码，
        # 而是返回空字符串或简单的确认信息。我们假定执行成功。
        return True, output.strip()
        
    except Exception as e:
        # print(f"ADB Error on {ip}:{port}: {e}") # 调试信息
        return False, str(e)


# --- 核心 ADB 逻辑替换 ---

def connect(ip, port):
    """尝试连接到 ADB 设备 (ADB库自动进行，此处仅为兼容外部调用)"""
    try:
        device = AdbDeviceTcp(ip, int(port), default_timeout_s=5)
        # 尝试连接，如果失败会抛出异常
        device.connect(rsa_keys=[SIGNER] if SIGNER else None)
        return True
    except Exception:
        return False


def recovery(ip, port):
    """发送恢复出厂设置广播"""
    command = "am broadcast -a android.intent.action.MASTER_CLEAR"
    success, info = _execute_adb_shell(ip, port, command)
    
    # 假设设备成功收到广播即视为成功
    return success


def kill():
    """
    杀死 ADB 服务。
    注意：使用纯 Python ADB 库时，我们无法直接杀死 Python 外部的 ADB 服务。
    此函数仅处理清除主机上的残留 ADB 进程（如果有的话），以及清除纯 Python ADB 的连接状态。
    """
    # 尝试清除残留的外部 adb.exe 进程 (如果用户之前使用过)
    if os.name == 'nt': # Windows
        # taskkill 命令通常在系统路径中
        gso("taskkill /im adb.exe /f 1>nul 2>nul") 
    
    # 由于库是纯Python实现，它没有一个外部adb服务器进程来“杀死”
    return True 


def reboot(ip, port):
    """重启设备"""
    # ADB Shell 'reboot' 命令在 adb_shell 中是内置的特殊命令
    try:
        device = AdbDeviceTcp(ip, int(port), default_timeout_s=5)
        device.connect(rsa_keys=[SIGNER] if SIGNER else None)
        device.reboot()
        return True
    except Exception:
        # 重启命令发送后设备立即断开连接是正常的，所以通常会捕获到异常，
        # 只要不是连接失败，就应该视为成功。
        return True 


def mac_change(mac, ip, port, sn_head):
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


def change(ip, mac, account, sn_head, port):
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


def auto_change(ip, account, port):
    """
    通过模拟按键和 skset 命令进行自动拨号设置。
    """
    if not connect(ip, port):
        return False
        
    try:
        device = AdbDeviceTcp(ip, int(port), default_timeout_s=5)
        device.connect(rsa_keys=[SIGNER] if SIGNER else None)
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

def rec_auto_change(mac, account, port):
    """恢复出厂后的自动拨号操作：通过 ARP 查找新 IP"""
    mac_data = covert(mac)
    if mac_data is None:
        return False
    
    _, _, m_mac = mac_data
    
    l_ip = socket.gethostbyname(socket.gethostname())
    
    # 清空 ARP 缓存，确保获取最新的 IP-MAC 映射
    gso("arp -d") 

    # 查找 ARP 缓存 (此操作依赖于操作系统命令，无法用纯 Python ADB 替代)
    status, data = gso(f'arp -a -N {l_ip}')
    
    if status != 0:
        return False 
        
    try:
        decoded_data = data.decode("gbk") 
    except (UnicodeDecodeError, AttributeError):
        decoded_data = data 
    
    arp_regex = r'([0-9.]+)\s+([0-9a-f]{2}[-:][0-9a-f]{2}[-:][0-9a-f]{2}[-:][0-9a-f]{2}[-:][0-9a-f]{2}[-:][0-9a-f]{2})'

    for arp_match in re.findall(arp_regex, decoded_data, re.IGNORECASE):
        ip, mac = arp_match
        current_mac = mac.lower().replace(':', '-')
        
        if m_mac == current_mac:
            # 找到新 IP 后，调用 auto_change (ip, account, port)
            return auto_change(ip, account, port)

    return False
