# Test Script to send data (two-way communication) from Laptop to Ultra96 Server
# Implementation using Python Socket API

import sys
import socket
import time
import base64

from Crypto import Random
from Crypto.Cipher import AES

# Initialise Socket Information
IP_ADDR = '127.0.0.1'
PORT_NUM = [8001,8002,8003]
GROUP_ID = 2
SECRET_KEY = 'cg40024002group2'

# Initialise Global Variables
BLOCK_SIZE = 16
PADDING = ' '
FORMAT = 'utf8'

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
        raw_message = '#' + str(dancer_id) + '|' + str(RRT) + '|' + str(offset) + '|' + raw_data
        padded_message = self.add_padding(raw_message)
        iv = Random.new().read(AES.block_size)
        aes_key = bytes(str(self.secret_key), encoding="utf8")
        cipher = AES.new(aes_key, AES.MODE_CBC, iv)
        encrypted_message = base64.b64encode(iv + cipher.encrypt(bytes(padded_message, "utf8")))
        return encrypted_message

    def send_data(self, dancer_id, RRT, offset, raw_data):
        # raw_message = raw_message.encode("utf8")
        encrypted_message = self.encrypt_message(dancer_id, RRT, offset, raw_data)
        self.socket.sendall(encrypted_message)

    def receive_timestamp(self):
        message = self.socket.recv(1024)
        timestamp = message.decode(FORMAT)
        return timestamp

    def stop(self):
        self.connection.close()
        self.shutdown.set()
        self.timer.cancel()

def main():
    if len(sys.argv) != 2:
        print('Invalid number of arguments')
        print('python Laptop_client.py [dancer_id]')
        sys.exit()

    dancer_id = int(sys.argv[1])
    ip_addr = '127.0.0.1'
    port_num = PORT_NUM[dancer_id-1]
    group_id = GROUP_ID
    secret_key = SECRET_KEY

    my_client = Client(ip_addr, port_num, group_id, secret_key)
    time.sleep(10)

    RTT = 0.0
    offset = 0.0

    # Simulate Data sent to Laptop every 5 seconds for 5 times
    count = 0
    action = ' '

    while action != "logout":
        # Timestamp t1: When laptop receives a packet from Bluno Beetle
        t1 = time.time()
        print('Sending Time Sync Packet. Timestamp t1: ', str(t1))
        my_client.send_data(dancer_id, RTT, offset, "raw_data")
        timestamp = my_client.receive_timestamp()
        # Timestamp t4: When laptop receives time sync response from Ultra96
        t4 = time.time()
        t2 = float(timestamp.split('|')[0])
        print('Ultra96 received Packet.  Timestamp t2: ', str(t2))
        t3 = float(timestamp.split('|')[1])
        print('Ultra96 sent response.    Timestamp t3: ', str(t3))
        print('Received Timestamp.       Timestamp t4: ', str(t4))
        
        RTT = (t2 - t1) - (t3 - t4)
        print('Round Trip Time: ', str(RTT))

        offset = (t2 - t1) - RTT/2
        print('Clock Offset: ', str(offset))

        time.sleep(5)
        count += 1
        if (count == 5):
            my_client.stop()

if __name__ == '__main__':
    main()
