#!/usr/bin/env python
# -*- coding:utf-8 -*-

import logging
import select
import socket
import struct
import sys
import threading


def send_data(sock, data):
    # print data
    #已传字节数
    bytes_sent = 0
    while True:
        r = sock.send(data[bytes_sent:])
        if r < 0:
            return r
        bytes_sent += r
        if bytes_sent == len(data):
            return bytes_sent


def tcp_conn(sock, remote):
    # 处理 client socket 和 remote socket 的数据流
    try:
        fdset = [sock, remote]
        while 1:
            # IO 多路复用 select 监听套接字是否有数据流
            r, w, e = select.select(fdset, [], [])
            if sock in r:
                data = sock.recv(4096)
                if len(data) <= 0:
                    break
                result = send_data(remote, data)
                if result < len(data):
                    raise Exception('failed to send all data')

            if remote in r:
                data = remote.recv(4096)
                if len(data) <= 0:
                    break
                result = send_data(sock, data)
                if result < len(data):
                    raise Exception('failed to send all data')
    finally:
        sock.close()
        remote.close()


def socks5_conn(sock, addr):
    # 接受客户端的请求，完成socks5的认证和连接过程    
    try:
        sock.recv(262)
        # ver=5, method=0(no authentication)
        sock.send("\x05\x00")
        data = sock.recv(4) or '\x00' * 4
        mode = ord(data[1])
        # CMD=0x01 即 CONNECT 继续
        if mode != 1:
            logging.warn('mode != 1')
            return
        # 对 DST.ADDR 进行判断
        addrtype = ord(data[3])
        # IPv4
        if addrtype == 1:
            addr_ip = sock.recv(4)
            addr = socket.inet_ntoa(addr_ip)
        # 域名
        elif addrtype == 3:
            addr_len = sock.recv(1)
            addr = sock.recv(ord(addr_len))
        # IPv6
        elif addrtype == 4:
            addr_ip = sock.recv(16)
            addr = socket.inet_ntoa(socket.AF_INET6, addr_ip)
        else:
            logging.warn('addr_type not support')
            # not support
            return
        # DST.PORT
        addr_port = sock.recv(2)
        port = struct.unpack('>H', addr_port)
        try:
            # 返回给客户端 success
            reply = "\x05\x00\x00\x01"
            reply += socket.inet_aton('0.0.0.0') + struct.pack(">H", 2222)
            sock.send(reply)
            # 拿到 remote address 的信息后，建立连接
            remote = socket.create_connection((addr, port[0]))
            logging.info('connecting %s:%d' % (addr, port[0]))
        except socket.error, e:
            logging.warn(e)
            return
        tcp_conn(sock, remote)
    except socket.error, e:
        logging.warn(e)


def main():
    # 支持自定义端口，默认端口1080
    port = 1080
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    print "Listen on port %s....." % (port)

    # socket.AF_INET 服务器之间网络通信， socket.SOCK_STREAM 流式socket for TCP
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # 设置端口释放即可重用
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    s.bind(('', port))
    s.listen(5)

    try:
        while 1:
            # 使用多线程监听来自客户端的请求
            sock, addr = s.accept()
            t = threading.Thread(target=socks5_conn, args=(sock, addr))
            t.start()
    except socket.error, e:
        logging.error(e)
    except KeyboardInterrupt:
        s.close()


if __name__ == '__main__':
    main()
