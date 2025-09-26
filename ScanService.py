#!/usr/bin/env python3
# cython:language_level=3
# -*- coding: utf-8 -*-
# @copyright: John Chen

import socket
import threading
from time import sleep
from PySide6.QtCore import QObject, Signal, Slot

# 导入 ADB 库
from adb_shell.adb_device import AdbDeviceTcp

# 默认的 ADB 端口
ADB_PORT = 5555

class ScanService(QObject):
    """
    负责在后台线程中扫描局域网中开放了 ADB 端口的设备。
    """
    # 定义信号
    # scan_finished: 扫描完成时发送，携带找到的设备列表 (ip:port)
    scan_finished = Signal(list)
    # device_found: 找到一个新设备时发送 (ip:port)
    device_found = Signal(str)
    # log_signal: 用于发送扫描过程中的日志信息
    log_signal = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_running = False
        self._found_devices = []
        self._threads = []

    def get_local_ip(self):
        """
        获取本机 IP 地址，用于确定网段。
        使用健壮的方法，避免 socket.gaierror。
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # 尝试连接一个外部地址，获取本地 IP（连接不会真正建立）
            s.connect(('8.8.8.8', 80))
            IP = s.getsockname()[0]
        except Exception:
            IP = '127.0.0.1'
        finally:
            s.close()
        return IP

    @Slot()
    def scan_network(self, start_octet=1, end_octet=255):
        """
        线程执行的入口：开始扫描局域网 IP。
        """
        if self._is_running:
            self.log_signal.emit("扫描已在运行中...")
            return

        self._is_running = True
        self._found_devices = []
        self._threads = []
        
        local_ip = self.get_local_ip()
        
        # 提取网段 (例如：从 '192.168.1.100' 得到 '192.168.1.')
        ip_parts = local_ip.split('.')
        if len(ip_parts) < 3:
             self.log_signal.emit(f"错误：无法从 {local_ip} 解析网段。")
             self.scan_finished.emit([])
             return

        network_prefix = ".".join(ip_parts[:3]) + "."

        self.log_signal.emit(f"开始扫描网段: {network_prefix}1-{end_octet}...")

        # 遍历网段内的所有 IP
        for i in range(start_octet, end_octet + 1):
            ip_to_check = f"{network_prefix}{i}"
            # 跳过本机 IP 
            if ip_to_check == local_ip:
                continue
                
            # 为每个 IP 创建一个线程进行异步尝试连接
            t = threading.Thread(target=self._check_adb_device, 
                                 args=(ip_to_check, ADB_PORT))
            self._threads.append(t)
            t.start()

        # 等待所有线程完成
        # 注意：这里不能使用简单的 t.join()，否则会阻塞线程。
        # 由于 Qt 信号机制的存在，我们只需要让主线程继续运行，并确保在退出时清理线程。
        # 但由于这个方法是在 QThread 中执行的，我们需要等待所有子线程完成。
        
        # 使用一个循环等待所有工作线程完成
        for t in self._threads:
            # 设置一个合理的超时时间，防止单个连接卡死整个扫描流程的等待
            t.join(timeout=1.0) 

        # 再次检查是否有线程未完成，并强制等待它们，以确保结果完整
        active_threads = [t for t in self._threads if t.is_alive()]
        while active_threads:
            sleep(0.1) # 短暂休眠
            active_threads = [t for t in self._threads if t.is_alive()]
            
        
        self.log_signal.emit(f"扫描完成，找到 {len(self._found_devices)} 个设备。")
        self._is_running = False
        self.scan_finished.emit(self._found_devices)

    def _check_adb_device(self, ip, port):
        """
        尝试连接单个 IP，检查是否为 ADB 设备。
        这是一个在子线程中运行的阻塞调用。
        """
        try:
            # 设置极短的连接超时 (例如 0.5 秒) 以快速跳过非活跃 IP
            device = AdbDeviceTcp(ip, port, default_timeout_s=0.5) 
            device.connect()
            
            # 连接成功即为 ADB 设备
            device_str = f"{ip}:{port}"
            self._found_devices.append(device_str)
            self.device_found.emit(device_str)
            
        except Exception:
            pass # 连接失败，不是 ADB 设备
