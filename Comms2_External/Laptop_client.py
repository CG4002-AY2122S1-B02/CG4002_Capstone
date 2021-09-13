# Test Script to send data (one-way communication) from Ultra96 FPGA to Database Server
# Implementation using Python Socket API

import sys
import argparse
import socket
import time
import base64

from Crypto import Random
from Crypto.Cipher import AES

# Initialise Socket Information
# IP_ADDR = '127.0.0.1'
# PORT = 8001

# Initialise Global Variables
BLOCK_SIZE = 16
PADDING = ' '

class Client():
    def __init__(self, ip_addr, port_num, group_id, secret_key):
        super(Client, self).__init__()

        # Create a TCP/IP socket and connect to database server
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_address = (ip_addr, port_num)
        self.group_id = group_id
        self.secret_key = secret_key

        print('trying to connect to %s port %s' % server_address)
        self.socket.connect(server_address)
        print("Successfully connected to the Ultra96 server")

    def add_padding(self, message):
        pad = lambda s: s + (BLOCK_SIZE - (len(s) % BLOCK_SIZE)) * PADDING
        padded_message = pad(message)
        return padded_message

    def encrypt_message(self, dancer_id, RRT, offset, raw_data):
        raw_message = '#' + dancer_id + '|' + RRT + '|' + offset + '|' + raw_data
        print("Message to Encrypt: ", raw_message)
        padded_message = self.add_padding(raw_message)
        iv = Random.new().read(AES.block_size)
        aes_key = bytes(str(self.secret_key), encoding="utf8")
        cipher = AES.new(aes_key, AES.MODE_CBC, iv)
        encrypted_message = base64.b64encode(iv + cipher.encrypt(bytes(padded_message, "utf8")))
        return encrypted_message

    def send_data(self, dancer_id, RRT, offset, raw_data):
        # raw_message = raw_message.encode("utf8")
        encrypted_message = self.encrypt_message(dancer_id, RRT, offset, raw_data)
        print("Sending data to Evaluation Server", encrypted_message)
        self.socket.sendall(encrypted_message)

    def stop(self):
        self.connection.close()
        self.shutdown.set()
        self.timer.cancel()

def main():
    if len(sys.argv) != 5:
        print('Invalid number of arguments')
        print('python Laptop_client.py [IP address] [Port] [groupID] [secret_key]')
        sys.exit()

    ip_addr = sys.argv[1]
    port_num = int(sys.argv[2])
    group_id = sys.argv[3]
    secret_key = sys.argv[4]

    my_client = Client(ip_addr, port_num, group_id, secret_key)
    action = ""
    time.sleep(10)

    count = 0
    while action != "logout":
        # Send the Ultra96 the received data from the 3 laptops
        # my_client.send_data("# 1 | 4.5 | 1.5 | raw_data")
        my_client.send_data("1", "4.5", "1.5", "raw_data")
        time.sleep(2)
        count += 1
        if (count == 5):
            my_client.stop()

if __name__ == '__main__':
    main()
