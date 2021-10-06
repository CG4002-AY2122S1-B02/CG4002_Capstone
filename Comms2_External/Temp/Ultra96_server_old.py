# Test Script to receive connection on Ultra96 from Laptops 

import argparse
import sys
import socket
import threading
import time
import base64

from Crypto import Random
from Crypto.Cipher import AES

# Initialise Variable Sizes
MESSAGE_SIZE = 4 # dancer_id | RTT | offset | raw_data 
FORMAT = 'utf8'

# Assign the host and port numbers of our Ultra96 Server 
IP_ADDR = '127.0.0.1'
PORT_NUM = [8001,8002,8003]
GROUP_ID = 2

class Server(threading.Thread):
    def __init__(self, ip_addr, port_num, group_id, secret_key):
        super(Server, self).__init__()

        # Create timestamps
        # Timestamp t2: When Ultra96 receives a sync packet from a Laptop
        self.t2 = 0
        # Timestamp t3: When Ultra96 sends a response packet to the Laptop
        self.t3 = 0

        # self.secret_key = secret_key

        # Create a TCP/IP socket and bind to port
        self.shutdown = threading.Event()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_address = (ip_addr, port_num)

        print('starting up on %s port %s' % server_address)
        self.socket.bind(server_address)

        # Listen for incoming connections
        self.socket.listen(5)
        self.client_address, self.secret_key = self.setup_connection(secret_key)

    def decrypt_message(self, cipher_text):
        # The data format currently is: # dancer_id | RTT | offset | raw_data
        decoded_message = base64.b64decode(cipher_text)
        iv = decoded_message[:16]
        secret_key = bytes(str(self.secret_key), encoding='utf8')

        cipher = AES.new(secret_key, AES.MODE_CBC, iv)

        decrypted_message = cipher.decrypt(decoded_message[16:]).strip()
        decrypted_message = decrypted_message.decode('utf8')

        decrypted_message = decrypted_message[decrypted_message.find('#'):]
        decrypted_message = bytes(decrypted_message[1:], 'utf8').decode('utf8')

        messages = decrypted_message.split('|')

        # Store the decrypted inputs from each dancer into variables
        dancer_id, RTT, offset, raw_data = messages[:MESSAGE_SIZE]
        return {
                'dancer_id': dancer_id, 'RTT': RTT, 'offset': offset, 'raw_data': raw_data
        }

    def setup_connection(self, secret_key):

        # Wait for a connection
        print('waiting for a connection')
        self.connection, client_address = self.socket.accept()

        if not secret_key:
            print("Enter the secret key: ")
            secret_key = sys.stdin.readline().strip()

        print('connection from', client_address)
        if len(secret_key) == 16 or len(secret_key) == 24 or len(secret_key) == 32:
            pass
        else:
            print("AES key must be either 16, 24, or 32 bytes long")
            self.stop()

        return client_address, secret_key

    def run(self):
        while not self.shutdown.is_set():
            data = self.connection.recv(1024)
            if data:
                self.t2 = time.time()
                try:
                    message = data.decode(FORMAT)
                    decrypted_message = self.decrypt_message(message)
                    if verbose:
                        print('Data received. Timestamp t2: ' + str(self.t2))
                    print('Received message: ', decrypted_message)

                    dancer_id = decrypted_message["dancer_id"]
                    raw_data = decrypted_message["raw_data"]

                    self.send_timestamp()

                except Exception as e:
                    print(e)
            else:
                print('no more data from', self.client_address)
                self.stop()

    def send_timestamp(self):
        self.t3 = time.time()
        timestamp = str(self.t2) + '|' + str(self.t3)

        if verbose:
            print('Sending Data. Timestamp t3: ' + str(self.t3))

        self.connection.sendall(timestamp.encode(FORMAT)
                )
    def stop(self):
        self.connection.close()
        self.shutdown.set()
        self.timer.cancel()

def main(dancer_id, secret_key):
    if dancer_id == 1:
        dancer_server1 = Server(IP_ADDR, PORT_NUM[0], GROUP_ID, secret_key)
        dancer_server1.start()
        print('Server Started for Dancer 1 on IP_ADDRESS: ' + IP_ADDR + ', PORT NUMBER: ' + str(PORT_NUM[0]))
    if dancer_id == 2:
        dancer_server2 = Server(IP_ADDR, PORT_NUM[1], GROUP_ID, secret_key)
        dancer_server2.start()
        print('Server Started for Dancer 2 on IP_ADDRESS: ' + IP_ADDR + ', PORT NUMBER: ' + str(PORT_NUM[1]))
    if dancer_id == 3:
        dancer_server3 = Server(IP_ADDR, PORT_NUM[2], GROUP_ID, secret_key)
        dancer_server3.start()
        print('Server Started for Dancer 3 on IP_ADDRESS: ' + IP_ADDR + ', PORT NUMBER: ' + str(PORT_NUM[2]))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Ultra96 Server set-up for Laptops to connect")
    parser.add_argument('-d', '--dancer_id', type=int, metavar='', required=True, help='dancer id')
    parser.add_argument('-s', '--secret_key', metavar='', default='cg40024002group2', help='secret key')
    parser.add_argument('-v', '--verbose', type=bool, default=False, help='verbose')

    args = parser.parse_args()

    dancer_id = args.dancer_id
    secret_key = args.secret_key
    verbose = args.verbose

    main(dancer_id, secret_key)
