#!/usr/bin/env python
# cython:language_level=3
# -*- coding: utf-8 -*-
# @copyright: John Chen
import sys
import socket
import time
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QGridLayout, QVBoxLayout, 
    QLabel, QLineEdit, QPushButton, QCheckBox, QTextEdit, QScrollArea,
    QMessageBox
)
from PySide6.QtCore import Qt, QTimer, Signal

# --- 占位符模块 (假设 function 和 CheckInput 存在) ---
# 在实际使用中，请确保 'function' 和 'CheckInput' 模块可用
# 为了代码的可执行性，这里沿用之前的 Mock 类
class MockFunction:
    def mac_change(self, mac, ip, port, sn_head): return True
    def recovery(self, ip, port): return True
    def rec_auto_change(self, mac, account, port): return True
    def auto_change(self, ip, account, port): return True
    def change(self, ip, mac, account, sn_head, port): return True
    def reboot(self, ip, port): return True
    def kill(self): return True
    def sleep(self, seconds): time.sleep(seconds)

class MockCheckInput:
    def check_ip(self, ip): return ip != '192.168.x.x' and len(ip.split('.')) == 4
    def check_adb_status(self, ip, port): return True
    def check_manufacturer(self, name, ip): return True
    def check_mac(self, mac): return mac not in ('', '请输入MAC地址')
    def check_ottx_status(self, ip, port): return True
    def check_account(self, account): return account not in ('', '请输入账号')

function = MockFunction()
Ck = MockCheckInput()
# --- 占位符结束 ---


version = 'V0.0.3-qt'
l_ip = socket.gethostbyname(socket.gethostname())
sn_head = "00570300004221C02117"
port = "5555"

class MainGui(QMainWindow):
    """主窗口类，继承自 QMainWindow"""

    # 定义一个信号，用于跨线程或跨方法发送日志消息
    log_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'创维机顶盒串码修改工具 {version}')
        self.setGeometry(100, 100, 600, 500)
        self.setFixedSize(600, 500) # 固定窗口大小

        # 核心 QWidget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 信号连接：将日志信号连接到日志写入槽函数
        self.log_signal.connect(self.write_log_to_text)

        self._setup_ui(central_widget)

    def _setup_ui(self, parent):
        """设置界面布局和组件"""
        main_layout = QVBoxLayout(parent)
        
        # --- 1. 顶部信息和输入区域 (GridLayout) ---
        input_widget = QWidget()
        input_layout = QGridLayout(input_widget)

        # 本机 IP
        input_layout.addWidget(QLabel(f"**本机IP为：** <font color='blue'>{l_ip}</font>"), 0, 0, 1, 2)
        
        # IP 输入
        input_layout.addWidget(QLabel("机顶盒 IP 地址:"), 1, 0)
        self.ip_Entry = QLineEdit("192.168.x.x")
        input_layout.addWidget(self.ip_Entry, 1, 1)

        # MAC 输入
        input_layout.addWidget(QLabel("MAC/SN 地址:"), 2, 0)
        self.mac_Entry = QLineEdit("请输入MAC地址")
        input_layout.addWidget(self.mac_Entry, 2, 1)

        # 账号输入
        input_layout.addWidget(QLabel("PPPoE 账号:"), 3, 0)
        self.account_Entry = QLineEdit("请输入账号")
        input_layout.addWidget(self.account_Entry, 3, 1)

        # Checkboxes
        self.reset_Check = QCheckBox("改完重启")
        self.reset_Check.setChecked(True) # 默认选中
        input_layout.addWidget(self.reset_Check, 1, 2)

        self.recovery_Check = QCheckBox("恢复出厂")
        input_layout.addWidget(self.recovery_Check, 2, 2)
        
        # 按钮
        self.confirm_Button = QPushButton("确定修改")
        self.confirm_Button.setStyleSheet("background-color: #6495ED; color: white;")
        self.confirm_Button.clicked.connect(self.core_program)
        input_layout.addWidget(self.confirm_Button, 3, 2)
        
        main_layout.addWidget(input_widget)
        
        # --- 2. 提示信息区域 ---
        tips_label = QLabel(
            "**操作提示：**\n"
            "1. 确保机顶盒与电脑在同一网络下，建议设为 DHCP。\n"
            "2. 机顶盒必须开启 **ADB 调试** (端口: 5555)。\n"
            "3. MAC 地址支持 XXXXXXXXXXXX 或 XX:XX:XX:XX:XX:XX 等格式。"
        )
        tips_label.setWordWrap(True)
        main_layout.addWidget(tips_label)

        # --- 3. 操作按钮区域 ---
        button_widget = QWidget()
        button_layout = QGridLayout(button_widget)
        
        self.reboot_Button = QPushButton("单独重启机顶盒")
        self.reboot_Button.setStyleSheet("background-color: #90EE90;")
        self.reboot_Button.clicked.connect(self.reboot_device)
        button_layout.addWidget(self.reboot_Button, 0, 0)

        self.kill_Button = QPushButton("杀死后台 ADB 服务")
        self.kill_Button.setStyleSheet("background-color: #F08080;")
        self.kill_Button.clicked.connect(self.kill_adb)
        button_layout.addWidget(self.kill_Button, 0, 1)

        main_layout.addWidget(button_widget)

        # --- 4. 日志区域 ---
        main_layout.addWidget(QLabel("--- **操作日志** ---"))
        self.log_data_Text = QTextEdit()
        self.log_data_Text.setReadOnly(True)
        self.log_data_Text.setMaximumHeight(200) # 限制日志框高度
        main_layout.addWidget(self.log_data_Text)
        
        main_layout.addStretch() # 填充底部空间

    def get_current_time(self):
        """获取当前时间"""
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))

    def write_log_to_text(self, logmsg):
        """将日志写入 QTextEdit"""
        current_time = self.get_current_time()
        logmsg_in = f"[{current_time}] {logmsg}\n"
        
        self.log_data_Text.insertPlainText(logmsg_in)
        # 确保滚动条在底部
        self.log_data_Text.ensureCursorVisible()

    def _check_preconditions(self, ip, mac, account):
        """检查IP、ADB状态和厂商是否正确"""
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
        
        if not Ck.check_mac(mac):
            self.log_signal.emit("请检查机顶盒MAC地址是否正确。")
            return False
            
        self.log_signal.emit("Mac地址格式正确")
        return True

    def _change_sn_and_reboot(self, ip, mac, account, sn_head):
        """执行串码/账号修改和重启逻辑"""
        
        if not Ck.check_account(account):
            self.log_signal.emit("请输入正确的账号。")
            return
            
        if function.change(ip, mac, account, sn_head, port):
            self.log_signal.emit("串码/账号修改成功。")
            
            if self.reset_Check.isChecked():
                self.log_signal.emit("正在重启设备...")
                if function.reboot(ip, port):
                    self.log_signal.emit("设备重启成功！")
                else:
                    self.log_signal.emit("设备重启失败！")
            else:
                 self.log_signal.emit("未选择重启，请手动操作。")
        else:
            self.log_signal.emit("修改失败，请重新尝试。")

    def core_program(self):
        """核心业务逻辑，通过 '确定修改' 按钮触发"""
        
        ip = self.ip_Entry.text().strip()
        mac = self.mac_Entry.text().strip()
        account = self.account_Entry.text().strip()

        if not self._check_preconditions(ip, mac, account):
            return

        is_recovering = self.recovery_Check.isChecked()
        is_resetting = self.reset_Check.isChecked()

        # 流程开始：修改 MAC
        if not function.mac_change(mac, ip, port, sn_head):
            self.log_signal.emit("MAC地址修改失败。尝试直接进行 SN/账号 修改...")
            self._change_sn_and_reboot(ip, mac, account, sn_head)
            return

        self.log_signal.emit("Mac地址修改成功。")
        
        # 流程分支 1：恢复出厂设置
        if is_recovering:
            if is_resetting:
                self.log_signal.emit("注意：已选择 '恢复出厂'，将忽略 '改完重启' 选项。")
            
            if Ck.check_ottx_status(ip, port):
                self.log_signal.emit("开始恢复出厂设置...")
                if function.recovery(ip, port):
                    self.log_signal.emit("恢复出厂设置成功，等待设备重启和初始化 (约 70 秒)...")
                    # Note: 在 GUI 应用中，长时间阻塞主线程会冻结界面，
                    # 实际生产代码中 function.sleep(70) 应该在 QThread 中执行。
                    function.sleep(10) # 模拟等待
                    
                    if function.rec_auto_change(mac, account, port):
                        self.log_signal.emit("自动拨号成功。")
                    else:
                        self.log_signal.emit("自动拨号失败。")
                else:
                    self.log_signal.emit("恢复失败，请重新尝试。")
            else:
                self.log_signal.emit("设备未处于 OTTX 状态，无法恢复出厂。")

        # 流程分支 2：只修改 SN/账号 + 可选重启
        elif is_resetting:
            # mac_change 成功，且只选择了重启 (reset)
            self._change_sn_and_reboot(ip, mac, account, sn_head)

        # 流程分支 3：只修改 MAC (mac_change 已成功)，不选重启，不选恢复
        else:
            self.log_signal.emit("所有操作完成。未进行重启或恢复出厂。")

    def kill_adb(self):
        """杀死后台 ADB 服务"""
        if function.kill():
            self.log_signal.emit("后台 ADB 进程已被杀死。")
        else:
            self.log_signal.emit("后台进程不能被杀死，请尝试 **以管理员权限** 运行。")

    def reboot_device(self):
        """单独重启机顶盒"""
        ip = self.ip_Entry.text().strip()
        
        if not Ck.check_ip(ip):
            self.log_signal.emit("请检查 IP 地址是否正确。")
            return
            
        if not Ck.check_adb_status(ip, port):
            self.log_signal.emit("请检查机顶盒 ADB 调试是否打开。")
            return
            
        self.log_signal.emit(f"已连接到: {ip}，正在执行重启...")
        if function.reboot(ip, port):
            self.log_signal.emit("设备重启命令发送成功！")
        else:
            self.log_signal.emit("设备重启失败！")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = MainGui()
    main_window.show()
<<<<<<< HEAD
    sys.exit(app.exec())
=======
    sys.exit(app.exec())
>>>>>>> 03b0ff42d969c25c3dde7f85034c7680b6b8a1d9
