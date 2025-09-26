#!/usr/bin/env python3
# cython:language_level=3
# -*- coding: utf-8 -*-
# @copyright: John Chen
import sys
import socket
import time
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QGridLayout, QVBoxLayout, 
    QLabel, QLineEdit, QPushButton, QCheckBox, QTextEdit, QMessageBox,
    QComboBox
)
# 修正导入：只保留需要的 PySide6.QtCore 模块，避免重复和冗余
from PySide6.QtCore import Qt, QThread, Signal, Slot, QObject 
from functools import partial
import function # 导入 function.py 模块
import CheckInput as Ck # 导入 CheckInput.py 模块
from ScanService import ScanService # 导入 ScanService.py 模块


version = 'V0.0.3-qt-SCAN'
port = "5555"
sn_head = "00570300004221C02117"


# --- 修复 socket.gaierror：使用健壮的 IP 获取方法 ---
def get_local_ip():
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

l_ip = get_local_ip()

# --- 核心业务逻辑线程类 ---
class Worker(QObject):
    finished = Signal()
    error = Signal(str)
    log_signal = Signal(str)
    
    def set_task(self, method, ip, mac, account, sn_head, is_recovering, is_resetting):
        self.method = method
        self.ip = ip
        self.mac = mac
        self.account = account
        self.sn_head = sn_head
        self.is_recovering = is_recovering
        self.is_resetting = is_resetting
        
    @Slot()
    def run(self):
        try:
            if self.method == 'core_program':
                self._core_program_thread_impl()
            elif self.method == 'reboot_device':
                self._reboot_device_thread_impl()
        except Exception as e:
            self.error.emit(f"业务逻辑执行异常: {e}")
        finally:
            self.finished.emit()

    def _core_program_thread_impl(self):
        ip, mac, account, sn_head = self.ip, self.mac, self.account, self.sn_head
        is_recovering = self.is_recovering
        is_resetting = self.is_resetting

        # 2. 修改 MAC
        if not function.mac_change(mac, ip, port, sn_head):
            self.log_signal.emit("MAC地址修改失败。尝试直接进行 SN/账号 修改...")
            if not function.change(ip, mac, account, sn_head, port):
                self.log_signal.emit("修改失败，请重新尝试。")
                return
        
        self.log_signal.emit("Mac地址修改成功。")

        # 3. 恢复出厂设置流程
        if is_recovering:
            if Ck.check_ottx_status(ip, port):
                self.log_signal.emit("开始恢复出厂设置...")
                if function.recovery(ip, port):
                    self.log_signal.emit("恢复出厂设置成功，等待设备重启和初始化 (约 70 秒)...")
                    function.sleep(70) 
                    
                    if function.rec_auto_change(mac, account, port):
                        self.log_signal.emit("自动拨号成功。")
                    else:
                        self.log_signal.emit("自动拨号失败。")
                else:
                    self.log_signal.emit("恢复失败，请重新尝试。")
            else:
                self.log_signal.emit("设备未处于 OTTX 状态，无法恢复出厂。")

        # 4. 只修改 SN/账号 + 可选重启流程
        elif is_resetting:
            if function.change(ip, mac, account, sn_head, port):
                self.log_signal.emit("串码/账号修改成功。")
                if function.reboot(ip, port):
                    self.log_signal.emit("设备重启命令发送成功！")
                else:
                    self.log_signal.emit("设备重启失败！")
            else:
                self.log_signal.emit("修改失败，请重新尝试。")

        else:
             self.log_signal.emit("所有操作完成。未进行重启或恢复出厂。")

    def _reboot_device_thread_impl(self):
        ip = self.ip

        if not Ck.check_adb_status(ip, port):
            self.log_signal.emit("请检查机顶盒 ADB 调试是否打开。")
            return
            
        self.log_signal.emit(f"已连接到: {ip}，正在执行重启...")
        if function.reboot(ip, port):
            self.log_signal.emit("设备重启命令发送成功！")
        else:
            self.log_signal.emit("设备重启失败！")


class MainGui(QMainWindow):
    """主窗口类，继承自 QMainWindow"""
    log_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'创维机顶盒串码修改工具 {version}')
        self.setGeometry(100, 100, 650, 500)
        self.setFixedSize(650, 500) 

        self.worker_thread = None
        self.scan_thread = None 
        self.scan_service = None

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.log_signal.connect(self.write_log_to_text)

        self._setup_scan_service()
        self._setup_ui(central_widget)

    def _setup_scan_service(self):
        """设置局域网扫描服务和线程"""
        self.scan_thread = QThread()
        self.scan_service = ScanService()
        self.scan_service.moveToThread(self.scan_thread)

        self.scan_thread.started.connect(lambda: self.scan_service.scan_network())
        self.scan_service.scan_finished.connect(self.on_scan_finished)
        self.scan_service.device_found.connect(self.on_device_found)

    def _setup_ui(self, parent):
        """设置界面布局和组件"""
        main_layout = QVBoxLayout(parent)
        
        # --- 1. 顶部信息和输入区域 (GridLayout) ---
        input_widget = QWidget()
        input_layout = QGridLayout(input_widget)

        # 本机 IP
        input_layout.addWidget(QLabel(f"**本机IP为：** <font color='blue'>{l_ip}</font>"), 0, 0, 1, 3)
        
        # IP 输入 (QComboBox)
        input_layout.addWidget(QLabel("机顶盒 IP 地址:"), 1, 0)
        self.ip_Combo = QComboBox()
        self.ip_Combo.setEditable(True)
        # 使用 setPlaceholderText (针对内部 QLineEdit)
        self.ip_Combo.lineEdit().setPlaceholderText("请输入或搜索机顶盒IP")
        default_ip_prefix = ".".join(l_ip.split('.')[:3]) + ".x"
        self.ip_Combo.addItem(default_ip_prefix) # 添加默认网段提示项
        self.ip_Combo.setCurrentText(default_ip_prefix) 
        input_layout.addWidget(self.ip_Combo, 1, 1)

        # 搜索按钮
        self.search_Button = QPushButton("搜索设备")
        self.search_Button.clicked.connect(self.start_scan)
        input_layout.addWidget(self.search_Button, 1, 2)


        # MAC 输入
        input_layout.addWidget(QLabel("MAC/SN 地址:"), 2, 0)
        self.mac_Entry = QLineEdit() # 初始文本为空
        # === 修正：使用 setPlaceholderText 实现自动清空/显示 ===
        self.mac_Entry.setPlaceholderText("请输入MAC地址") 
        input_layout.addWidget(self.mac_Entry, 2, 1)

        # 账号输入
        input_layout.addWidget(QLabel("账号:"), 3, 0)
        self.account_Entry = QLineEdit() # 初始文本为空
        # === 修正：使用 setPlaceholderText 实现自动清空/显示 ===
        self.account_Entry.setPlaceholderText("请输入账号")
        input_layout.addWidget(self.account_Entry, 3, 1)

        # Checkboxes & 按钮
        self.reset_Check = QCheckBox("改完重启")
        self.reset_Check.setChecked(True) 
        input_layout.addWidget(self.reset_Check, 2, 2)

        self.recovery_Check = QCheckBox("恢复出厂")
        input_layout.addWidget(self.recovery_Check, 3, 2)
        
        # 确定修改按钮
        self.confirm_Button = QPushButton("确定修改 (耗时操作)")
        self.confirm_Button.setStyleSheet("background-color: #6495ED; color: white;")
        self.confirm_Button.clicked.connect(self.start_core_program)
        input_layout.addWidget(self.confirm_Button, 4, 0, 1, 3)
        
        main_layout.addWidget(input_widget)
        
        # --- 2. 提示信息区域 (保持不变) ---
        tips_label = QLabel(
            "**操作提示：**\n"
            "1. 确保机顶盒与电脑在同一网络下，建议设为 DHCP。\n"
            "2. 机顶盒必须开启 **ADB 调试** (端口: 5555)。\n"
            "3. MAC 地址支持 XXXXXXXXXXXX 或 XX:XX:XX:XX:XX:XX 等格式。\n"
            "4. 账号自动添加ottx01@ottx，并且自动输入密码。"
        )
        tips_label.setWordWrap(True)
        main_layout.addWidget(tips_label)

        # --- 3. 操作按钮区域 (保持不变) ---
        button_widget = QWidget()
        button_layout = QGridLayout(button_widget)
        
        self.reboot_Button = QPushButton("单独重启机顶盒 (耗时操作)")
        self.reboot_Button.setStyleSheet("background-color: #90EE90;")
        self.reboot_Button.clicked.connect(self.start_reboot_device)
        button_layout.addWidget(self.reboot_Button, 0, 0)

        self.kill_Button = QPushButton("杀死后台 ADB 服务")
        self.kill_Button.setStyleSheet("background-color: #F08080;")
        self.kill_Button.clicked.connect(self.kill_adb)
        button_layout.addWidget(self.kill_Button, 0, 1)

        main_layout.addWidget(button_widget)

        # --- 4. 日志区域 (保持不变) ---
        main_layout.addWidget(QLabel("--- **操作日志** ---"))
        self.log_data_Text = QTextEdit()
        self.log_data_Text.setReadOnly(True)
        self.log_data_Text.setMaximumHeight(150) 
        main_layout.addWidget(self.log_data_Text)
        
        main_layout.addStretch()

    # --- 线程化操作入口 (保持不变) ---
    def _start_worker(self, method, ip, mac, account, sn_head, is_recovering, is_resetting):
        """通用启动工作线程的函数"""
        if self.worker_thread and self.worker_thread.isRunning():
            self.log_signal.emit("警告：当前已有耗时操作正在进行，请等待其完成。")
            return

        self.set_buttons_enabled(False)

        self.worker_thread = QThread()
        self.worker = Worker()
        self.worker.moveToThread(self.worker_thread)
        self.worker.set_task(method, ip, mac, account, sn_head, is_recovering, is_resetting)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.log_signal.connect(self.write_log_to_text)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.finished.connect(lambda: self.set_buttons_enabled(True))

        self.worker_thread.start()
        self.log_signal.emit(f"任务 '{method}' 已在后台线程启动...")

    @Slot()
    def start_core_program(self):
        """启动核心修改流程"""
        ip = self.ip_Combo.currentText().strip()
        mac = self.mac_Entry.text().strip()
        account = self.account_Entry.text().strip()

        if not self._check_preconditions(ip, mac, account):
            return

        self._start_worker(
            'core_program', ip, mac, account, sn_head, 
            self.recovery_Check.isChecked(), 
            self.reset_Check.isChecked()
        )

    @Slot()
    def start_reboot_device(self):
        """启动单独重启流程"""
        ip = self.ip_Combo.currentText().strip()

        if not Ck.check_ip(ip):
            self.log_signal.emit("请检查 IP 地址是否正确。")
            return
            
        self._start_worker(
            'reboot_device', ip, None, None, None, False, False
        )

    # --- 局域网搜索逻辑 (保持不变) ---
    @Slot()
    def start_scan(self):
        """启动局域网扫描"""
        if self.scan_thread and self.scan_thread.isRunning():
            self.log_signal.emit("警告：设备扫描正在进行中，请耐心等待。")
            return
        
        self.ip_Combo.clear()
        self.ip_Combo.addItem("正在扫描中...")
        self.ip_Combo.setEnabled(False)
        self.search_Button.setEnabled(False)
        self.search_Button.setText("扫描中...")
        self.log_signal.emit(f"开始扫描局域网 ({l_ip.rsplit('.', 1)[0]}.1-255)...")
        self.scan_thread.start()

    @Slot(str)
    def on_device_found(self, ip_port_str):
        """找到设备时更新 ComboBox"""
        ip = ip_port_str.split(':')[0]
        if self.ip_Combo.findText(ip) == -1:
            self.ip_Combo.addItem(ip)
            self.log_signal.emit(f"发现设备: {ip}")
        
    @Slot(list)
    def on_scan_finished(self, found_devices):
        """扫描完成后重置界面状态"""
        self.scan_thread.quit()
        
        self.ip_Combo.removeItem(self.ip_Combo.findText("正在扫描中..."))
        self.ip_Combo.setEnabled(True)
        self.search_Button.setText("搜索设备")
        self.search_Button.setEnabled(True)
        
        if not found_devices:
            self.log_signal.emit("扫描完成。未找到任何 ADB 设备。")
        else:
            self.log_signal.emit(f"扫描完成。共找到 {len(found_devices)} 个 ADB 设备。")
            # 默认选中第一个，并确保文本框显示的是 IP
            self.ip_Combo.setCurrentText(found_devices[0].split(':')[0]) 

    # --- 辅助方法 (保持不变) ---
    def set_buttons_enabled(self, enabled):
        """批量启用/禁用按钮"""
        self.confirm_Button.setEnabled(enabled)
        self.reboot_Button.setEnabled(enabled)
        self.kill_Button.setEnabled(enabled)
        # 注意：扫描线程完成后，搜索按钮才会被 on_scan_finished 启用
        if not self.scan_thread.isRunning():
            self.search_Button.setEnabled(enabled)

        if not enabled:
            self.log_signal.emit("GUI 锁定，正在执行后台操作...")
        else:
            self.log_signal.emit("后台操作完成，GUI 解锁。")
            
    def _check_preconditions(self, ip, mac, account):
        """检查IP、ADB状态和厂商是否正确"""
        if not ip.strip():
            self.log_signal.emit("请输入机顶盒IP地址。")
            return False
        
        if not Ck.check_ip(ip):
            self.log_signal.emit("请输入正确的机顶盒IP地址。")
            return False
        
        if not Ck.check_adb_status(ip, port):
            self.log_signal.emit("请检查机顶盒 **ADB 调试** 是否打开。")
            return False

        self.log_signal.emit(f"已连接到: {ip}")
        
        if not Ck.check_manufacturer("SKYWORTH", ip):
            self.log_signal.emit("厂商不正确，请检查是否为创维机顶盒。")
            return False
        
        self.log_signal.emit("厂家正确")
        
        if not mac.strip(): # 新增检查：MAC地址不能为空
            self.log_signal.emit("MAC地址不能为空。")
            return False
            
        if not Ck.check_mac(mac):
            self.log_signal.emit("请检查机顶盒MAC地址是否正确。")
            return False
            
        self.log_signal.emit("Mac地址格式正确")
        return True

    def kill_adb(self):
        """杀死后台 ADB 服务"""
        if function.kill():
            self.log_signal.emit("后台 ADB 进程已被杀死。")
        else:
            self.log_signal.emit("后台进程不能被杀死，请尝试 **以管理员权限** 运行。")
    
    def get_current_time(self):
        """获取当前时间"""
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))

    def write_log_to_text(self, logmsg):
        """将日志写入 QTextEdit"""
        current_time = self.get_current_time()
        logmsg_in = f"[{current_time}] {logmsg}\n"
        
        self.log_data_Text.insertPlainText(logmsg_in)
        self.log_data_Text.ensureCursorVisible()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = MainGui()
    main_window.show()
<<<<<<< HEAD
    sys.exit(app.exec())
=======
<<<<<<< HEAD
    sys.exit(app.exec())
=======
    sys.exit(app.exec())
>>>>>>> 03b0ff42d969c25c3dde7f85034c7680b6b8a1d9
>>>>>>> 47e68c7c0c317b86c0354ac19c9c1c9f3c935087
