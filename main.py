#!/usr/bin/env python
# cython:language_level=3
# -*- coding: utf-8 -*-
# @copyright: John Chen
from tkinter import *
import socket
import time
import function
import CheckInput as Ck
LOG_LINE_NUM = 0
version = 'V0.0.2-beta'
l_ip = socket.gethostbyname(socket.gethostname())
sn_head = "00570300004221C02117"
port = "5555"


class MainGui:
    def __init__(self, init_window_name):
        self.reset = None
        self.recovery = None
        self.sk = init_window_name

    def write_log_to_text(self, logmsg):
        global LOG_LINE_NUM
        current_time = self.get_current_time()
        logmsg_in = str(current_time) + " " + str(logmsg) + "\n"  # 换行
        if LOG_LINE_NUM <= 7:
            self.sk.log_data_Text.insert(END, logmsg_in)
            LOG_LINE_NUM = LOG_LINE_NUM + 1
        else:
            self.sk.log_data_Text.delete(1.0, 2.0)
            self.sk.log_data_Text.insert(END, logmsg_in)

    def set_init_window(self):
        self.reset = IntVar()
        self.recovery = IntVar()
        self.sk.title('创维机顶盒串码修改工具 ' + version)
        self.sk.iconbitmap('Skyworth.ico')
        self.sk.geometry('550x410+10+10')
        self.sk.tips1_label = Label(self.sk, text="机顶盒要和电脑要在同一网络下，将机顶盒网络设置设为DHCP或无线连接")
        self.sk.tips1_label.grid(row=2, column=0)
        self.sk.tips2_label = Label(self.sk, text="机顶盒必须开启ADB调试")
        self.sk.tips2_label.grid(row=4, column=0)
        self.sk.tips3_label = Label(self.sk, text="将盒子IP地址在下方输入")
        self.sk.tips3_label.grid(row=6, column=0)
        self.sk.tips4_label = Label(self.sk, text="Mac地址格式支持:XXXXXXXXXXXX或XX:XX:XX:XX:XX:XX,\nXX-XX-XX-XX-XX-XX。三种格式不区分大小写")
        self.sk.tips4_label.grid(row=8, column=0)
        self.sk.init_ip_label = Label(self.sk, text="本机IP为：" + l_ip)
        self.sk.init_ip_label.grid(row=10, column=0)
        self.sk.ip_Text = Text(self.sk, width=18, height=1)
        self.sk.ip_Text.insert(INSERT, '请输入IP')
        self.sk.ip_Text.grid(row=11, column=0, rowspan=11, columnspan=1)
        self.sk.mac_Text = Text(self.sk, width=18, height=1)
        self.sk.mac_Text.insert(INSERT, '请输入MAC地址')
        self.sk.mac_Text.grid(row=15, column=0, rowspan=10, columnspan=1)
        self.sk.account_Text = Text(self.sk, width=18, height=1)
        self.sk.account_Text.insert(INSERT, '请输入账号')
        self.sk.account_Text.grid(row=30, column=0, rowspan=10, columnspan=1)
        self.sk.check_button = Checkbutton(self.sk, text='改完重启', variable=self.reset, onvalue=1, offvalue=0)
        self.sk.check_button.grid(row=10, column=11)
        self.sk.check_button = Checkbutton(self.sk, text='恢复出厂', variable=self.recovery, onvalue=1, offvalue=0)
        self.sk.check_button.grid(row=12, column=11)
        self.sk.log_label = Label(self.sk, text="操作日志")
        self.sk.log_label.grid(row=60, column=0)
        self.sk.log_data_Text = Text(self.sk, width=66, height=9, )  # 日志框
        self.sk.log_data_Text.grid(row=80, column=0, columnspan=10)
        self.sk.reboot_button = Button(self.sk, text="重启机顶盒", bg="lightblue", width=10, command=self.reboot)
        self.sk.reboot_button.grid(row=30, column=11)
        self.sk.kill_button = Button(self.sk, text="杀死后台服务", bg="lightblue", width=10, command=self.kill)
        self.sk.kill_button.grid(row=20, column=11)
        self.sk.confirm_button = Button(self.sk, text="确定", bg="lightblue", width=10, command=self.core_program)
        self.sk.confirm_button.grid(row=13, column=11)
        self.reset.set(1)

    def core_program(self):
        ip = self.sk.ip_Text.get('0.0', END).strip('\n')
        mac = self.sk.mac_Text.get('0.0', END).strip('\n')
        account = self.sk.account_Text.get('0.0', END).strip('\n')
        if Ck.check_ip(ip):
            if Ck.check_adb_status(ip, port):
                self.write_log_to_text("已连接到：%s" % ip)
                if Ck.check_manufacturer("SKYWORTH", ip):
                    self.write_log_to_text("厂家正确")
                    if Ck.check_mac(mac):
                        self.write_log_to_text("Mac地址正确")
                        if function.mac_change(mac, ip, port, sn_head):
                            self.write_log_to_text("Mac地址修改成功")
                            if self.recovery.get() == 1 and self.reset.get() == 0:
                                if Ck.check_ottx_status(ip, port):
                                    if function.recovery(ip, port):
                                        self.write_log_to_text("恢复出厂设置成功")
                                        function.sleep(70)
                                        if function.rec_auto_change(mac, account, port):
                                            self.write_log_to_text("自动拨号成功")
                                        else:
                                            self.write_log_to_text("自动拨号失败")
                                    else:
                                        self.write_log_to_text("恢复失败，请重新尝试")

                                else:
                                    if function.auto_change(ip, account, port):
                                        self.write_log_to_text("自动拨号成功")
                                    else:
                                        self.write_log_to_text("没有恢复")
                                        self.write_log_to_text("自动拨号失败")
                            elif self.reset.get() == 1 and self.recovery.get() == 0:
                                if function.change(ip, mac, account, sn_head, port):
                                    if Ck.check_account(account):
                                        self.write_log_to_text("修改成功")
                                        if function.reboot(ip, port):
                                            self.write_log_to_text("重启成功！")
                                        else:
                                            self.write_log_to_text("重启失败！")
                                    else:
                                        self.write_log_to_text("请输入正确的账号")
                                else:
                                    self.write_log_to_text("修改失败请重新尝试")
                            else:
                                if function.change(ip, mac, account, sn_head, port):
                                    if Ck.check_account(account):
                                        self.write_log_to_text("修改成功")
                                        if function.reboot(ip, port):
                                            self.write_log_to_text("重启成功！")
                                        else:
                                            self.write_log_to_text("重启失败！")
                                    else:
                                        self.write_log_to_text("请输入正确的账号")
                                else:
                                    self.write_log_to_text("修改失败请重新尝试")
                        else:
                            self.write_log_to_text("MAC修改失败")
                    else:
                        self.write_log_to_text("请检查机顶盒MAC地址是否正确")
                else:
                    self.write_log_to_text("厂商不正确无法修改，请检查是否为创维机顶盒")
            else:
                self.write_log_to_text("请检查机顶盒USB调试是否打开")
        else:
            self.write_log_to_text("请输入正确的机顶盒IP地址，然后按确认")

    @staticmethod
    def get_current_time():
        current_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
        return current_time

    def kill(self):
        if function.kill():
            self.write_log_to_text("后台已被杀死")
        else:
            self.write_log_to_text("后台不能被杀死，请以管理员权限打开然后重试")

    def reboot(self):
        ip = self.sk.ip_Text.get('0.0', END).strip('\n')
        if Ck.check_ip(ip):
            if Ck.check_adb_status(ip, port):
                self.write_log_to_text("已连接到：%s" % ip)
                if function.reboot(ip, port):
                    self.write_log_to_text("重启成功！")
                else:
                    self.write_log_to_text("重启失败！")
            else:
                self.write_log_to_text("请检查机顶盒USB调试是否打开")
        else:
            self.write_log_to_text("请检查IP地址是否正确")


def start_gui():
    init_window = Tk()
    skyworth_sn_change = MainGui(init_window)
    skyworth_sn_change.set_init_window()
    init_window.mainloop()


start_gui()
