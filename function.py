#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from subprocess import getstatusoutput as gso
import re
import time
import socket
import CheckInput as Ck


def sleep(seconds):
    start_time = time.time()
    while time.time() - start_time < seconds:
        pass


def covert(mac):
    # 判断mac地址格式并转化
    if len(mac) == 12:
        mac = mac.upper()
    elif len(mac) == 17:
        if ':' in mac:
            mac = mac.replace(':', '')
            mac = mac.upper()
        elif '-' in mac:
            mac = mac.replace('-', '')
            mac = mac.upper()
        else:
            return False
    # 将转化的MAC地址格式化
    mac1 = mac[0:2]
    mac2 = mac[2:4]
    mac3 = mac[4:6]
    mac4 = mac[6:8]
    mac5 = mac[8:10]
    mac6 = mac[10:12]
    colon = ":"
    minus = "-"
    c_mac = mac1 + colon + mac2 + colon + mac3 + colon + mac4 + colon + mac5 + colon + mac6
    c_mac = str(c_mac)
    m_mac = mac1 + minus + mac2 + minus + mac3 + minus + mac4 + minus + mac5 + minus + mac6
    m_mac = str(m_mac).lower()
    return mac, c_mac, m_mac


def connect(ip, port):
    out, info = gso("adb connect %s:%s" % (ip, port))
    if 'cannot connect to' in info:
        return False
    elif 'connected to' in info:
        return True
    elif 'already connected to' in info:
        return True
    else:
        return False


def recovery(ip, port):
    out, info = gso("adb -s %s:%s shell am broadcast -a android.intent.action.MASTER_CLEAR" % (ip, port))
    if out == 0:
        if 'Broadcast completed' in info:
            return True
        else:
            return False
    else:
        return False


def kill():
    out, info = gso("adb kill-server 1>nul 2>nul")
    if out == 0:
        gso("taskkill /im adb.exe /f 1>nul 2>nul")
        return True
    else:
        return False


def reboot(ip, port):
    out, info = gso("adb -s %s:%s  reboot " % (ip, port))
    if out == 0:
        if 'error: device' in info:
            return False
        elif 'not found' in info:
            return False
        else:
            return True


def mac_change(mac, ip, port, sn_head):
    mac, c_mac, m_mac = covert(mac)
    sn = sn_head + mac
    device = "adb -s %s:%s shell" % (ip, port)
    if gso(device + " skset mac %s" % c_mac):
        if gso(device + " skset sn %s" % sn):
            return True
        else:
            return False
    else:
        return False


def change(ip, mac, account, sn_head, port):
    mac, c_mac, m_mac = covert(mac)
    # 开始操作机顶盒
    device = "adb -s %s:%s shell" % (ip, port)
    sn = sn_head + mac
    if gso(device + " skset sn %s" % sn):
        if gso(device + " skset skyworth.params.net.dhcpusr %sottx01@ottx" % account):
            if gso(device + " skset skyworth.params.net.dhcppwd 123456"):
                return True
            else:
                return False
        else:
            return False
    else:
        return False


def auto_change(ip, account, port):
    gso("adb connect %s:%s" % (ip, port))
    device = "adb -s %s:%s shell" % (ip, port)
    if Ck.check_adb_status(ip, port):
        out, info = gso(device + " am start -n com.skyworth.modeselecter/com.skyworth.modeselecter.MainActivity")
        print(out, info)
        out, info = gso(device + " skset skyworth.params.net.dhcpusr %sottx01@ottx" % account)
        print(out, info)
        out, info = gso(device + " skset skyworth.params.net.dhcppwd 123456")
        print(out, info)
        out, info = gso(device + " input keyevent KEYCODE_DPAD_DOWN")
        print(out, info)
        out, info = gso(device + " input keyevent KEYCODE_DPAD_DOWN")
        print(out, info)
        out, info = gso(device + " input keyevent KEYCODE_DPAD_CENTER")
        print(out, info)
        out, info = gso(device + " input keyevent KEYCODE_BACK ")
        print(out, info)
        out, info = gso(device + " input keyevent KEYCODE_DPAD_DOWN")
        print(out, info)
        out, info = gso(device + " input keyevent KEYCODE_DPAD_DOWN")
        print(out, info)
        out, info = gso(device + " input keyevent KEYCODE_DPAD_CENTER")
        print(out, info)
        out, info = gso(device + " input keyevent KEYCODE_DPAD_CENTER")
        print(out, info)
        return True
    else:
        return False


def rec_auto_change(mac, account, port):
    mac, c_mac, m_mac = covert(mac)
    l_ip = socket.gethostbyname(socket.gethostname())
    out, info = gso("arp -d")
    if out == 0:
        o, data = gso('arp -a -N %s' % l_ip)
        for arp in re.findall('([-.0-9]+)\s+([-0-9a-f]{17})\s', data):
            ip, mac = arp
            print(mac, m_mac)
            if m_mac == mac:
                ip = ip.decode("gbk").encode("utf-8")
                auto_change(account, port, ip)
    else:
        return False
