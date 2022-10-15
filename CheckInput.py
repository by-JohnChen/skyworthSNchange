import string
from subprocess import getstatusoutput as gso
import re


def check_ottx_status(ip, port):
    out, info = gso("adb -s %s:%s shell skget skyworth.params.net.dhcpusr" % (ip, port))
    if "ottx" in info:
        return True
    else:
        return False


def check_mac(mac):
    if len(mac) == 12:
        if(c in string.hexdigits for c in mac):
            return True
        else:
            return False
    elif len(mac) == 17:
        if ':' in mac:
            mac = mac.replace(':', '')
            if (c in string.hexdigits for c in mac):
                return True
            else:
                return False
        elif '-' in mac:
            mac = mac.replace('-', '')
            if (c in string.hexdigits for c in mac):
                return True
            else:
                return False
    else:
        return False


def check_sn(sn_head, mac):
    sn = sn_head + mac
    if(c in string.hexdigits for c in sn):
        if len(sn) == 32:
            return True
        else:
            return False
    else:
        return False


def check_account(account):
    if len(account) == 11:
        if account.isdigit():
            return True
        else:
            return False


def check_adb_status(ip, port):
    ip = ip.decode("gbk").encode("utf-8")
    gso("adb connect %s:%s" % (ip, port))
    out, info = gso("adb -s %s:%s get-state" % (ip, port))
    if out == 0:
        if 'device' in info:
            return True
        elif 'offline' in info:
            return False
        else:
            return False
    else:
        return False


def check_ip(ip):
    compile_ip = re.compile('^(1\d{2}|2[0-4]\d|25[0-5]|[1-9]\d|[1-9])\.(1\d{2}|2[0-4]\d|25[0-5]|[1-9]\d|\d)\.(1\d{2}|2[0-4]\d|25[0-5]|[1-9]\d|\d)\.(1\d{2}|2[0-4]\d|25[0-5]|[1-9]\d|\d)$')
    if compile_ip.match(ip):
        return True
    else:
        return False


def check_manufacturer(manufacturer, ip):
    out, info = gso("adb -s " + ip + ":5555 shell getprop ro.product.manufacturer")
    if out == 0:
        if manufacturer in info:
            return True
        else:
            return False
