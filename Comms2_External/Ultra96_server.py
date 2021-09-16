# Python script on Ultra96 Server to handle communication from each Laptop

import argparse
import base64
import random
import socket
import sys
import time
import threading

from Crypto import Random
from Crypto.Cipher import AES

# Initialize global values
FORMAT = 'utf8'
PADDING = ' '
BLOCK_SIZE = 16
MESSAGE_SIZE = 4 # dancer_id, RTT, offset, raw_data

# Initialize values for Ultra96 Server 
IP_ADDRESS = "127.0.0.1"
PORT_NUM = [8081, 8082, 8083]
GROUP_ID = 2

class Server(threading.Thread):
    def __init__(
        self,
        ip_addr,
        port_num,
        group_id,
        secret_key
    ):
        super(Server, self).__init__()

        # Time stamps
        # Indicate the time when the server receive the package
        self.t2 = 0
        # Indicate the time when the server send the package
        self.t3 = 0

        # Create a TCP/IP socket and bind to port
        self.shutdown = threading.Event()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_address = (ip_addr, port_num)

        print("starting up on %s port %s" % server_address)
        self.socket.bind(server_address)

        # Listen for incoming connections
        self.socket.listen(4)
        self.client_address, self.secret_key = self.setup_connection(secret_key)

    def decrypt_message(self, cipher_text):
        # The data format which will be used here will be "# dancer_id | RTT | offset | raw_data"
        decoded_message = base64.b64decode(cipher_text)
        iv = decoded_message[:16]
        secret_key = bytes(str(self.secret_key), encoding="utf8")

        cipher = AES.new(secret_key, AES.MODE_CBC, iv)
        decrypted_message = cipher.decrypt(decoded_message[16:]).strip()
        decrypted_message = decrypted_message.decode("utf8")

        decrypted_message = decrypted_message[decrypted_message.find("#") :]
        decrypted_message = bytes(decrypted_message[1:], "utf8").decode("utf8")

        messages = decrypted_message.split("|")
        dancer_id, RTT, offset, raw_data = messages[:MESSAGE_SIZE]
        return {
            "dancer_id": dancer_id,
            "RTT": RTT,
            "offset": offset,
            "raw_data": raw_data,
        }

    def run(self):
        while not self.shutdown.is_set():
            data = self.connection.recv(1024)
            if data:
                try:
                    self.t2 = time.time()
                    message = data.decode(FORMAT)
                    decrypted_message = self.decrypt_message(message)
                    raw_data = decrypted_message["raw_data"]
                    if verbose:
                        print("t2:" + str(self.t2))
                        print("Raw Data: ", raw_data)
                    self.send_timestamp()

                except Exception as e:
                    print(e)
            else:
                print("no more data from", self.client_address)
                self.stop()

    def send_timestamp(self):
        self.t3 = time.time()
        timestamp = str(self.t2) + "|" + str(self.t3)

        if verbose:
            print("t3:" + str(self.t3))

        self.connection.sendall(timestamp.encode())

    def setup_connection(self, secret_key):

        # print("No actions for 60 seconds to give time to connect")
        # self.timer = threading.Timer(self.timeout, self.send_timestamp)
        # self.timer.start()

        # Wait for a connection
        print("waiting for a connection")
        self.connection, client_address = self.socket.accept()

        print("Enter the secret key: ")
        if not secret_key:
            secret_key = sys.stdin.readline().strip()

        print("connection from", client_address)
        if len(secret_key) == 16 or len(secret_key) == 24 or len(secret_key) == 32:
            pass
        else:
            print("AES key must be either 16, 24, or 32 bytes long")
            self.stop()

        return client_address, secret_key

    def stop(self):
        self.connection.close()
        self.shutdown.set()
        self.timer.cancel()

def main(dancer_id, secret_key):
    if dancer_id == 1:
        dancer_server1 = Server(IP_ADDRESS, PORT_NUM[0], GROUP_ID, secret_key)
        dancer_server1.start()
        print(
            "dancer_server1 started: IP address:"
            + IP_ADDRESS
            + " Port Number: "
            + str(PORT_NUM[0])
            + " Group ID number: "
            + str(GROUP_ID)
        )
    if dancer_id == 2:
        dancer_server2 = Server(IP_ADDRESS, PORT_NUM[1], GROUP_ID, secret_key)
        dancer_server2.start()
        print(
            "dancer_server2 started: IP address:"
            + IP_ADDRESS
            + " Port Number: "
            + str(PORT_NUM[1])
            + " Group ID number: "
            + str(GROUP_ID)
        )

    if dancer_id == 3:
        dancer_server3 = Server(IP_ADDRESS, PORT_NUM[2], GROUP_ID, secret_key)
        dancer_server3.start()
        print(
            "dancer_server3 started: IP address:"
            + IP_ADDRESS
            + " Port Number: "
            + str(PORT_NUM[2])
            + " Group ID number: "
            + str(GROUP_ID)
        )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="External Comms")
    parser.add_argument('-d', '--dancer_id', type=int, help='dancer id', required=True)
    parser.add_argument('-v', '--verbose', default=False, help='verbose', type=bool)
    parser.add_argument('-s', '--secret_key', default='cg40024002group2', help='secret key')

    args = parser.parse_args()
    dancer_id = args.dancer_id
    verbose = args.verbose
    secret_key = args.secret_key

    main(dancer_id, secret_key)
