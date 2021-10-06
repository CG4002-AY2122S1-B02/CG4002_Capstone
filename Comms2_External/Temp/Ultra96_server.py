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
FORMAT = 'utf8'
MAX_DANCERS = 4 #3
NUM_OF_DANCERS = 3
BLUNO_PER_LAPTOP = 1

# Assign the host and port numbers of our Ultra96 Server 
IP_ADDR = '127.0.0.1'
PORT_NUM = 3000
GROUP_ID = 2

# Initialise Global Variables
BLOCK_SIZE = 16
PADDING = ' '
FORMAT = 'utf8'

class Server(threading.Thread):
    def __init__(self, ip_addr, port_num, group_id, secret_key):
        super(Server, self).__init__()

        '''
        Create Data Structures to store each of the laptop connections here
        '''
        self.ip_addr = ip_addr
        self.port_num = port_num
        self.secret_key = secret_key
        self.shutdown = threading.Event()
        self.connections = []

        # Timestamp t2: When Ultra96 receives a sync packet from a Laptop
        self.t2 = 0
        # Timestamp t3: When Ultra96 sends a response packet to the Laptop
        self.t3 = 0

        # Create connections to laptops
        self.setup_connection()

    '''
    Allow and keep track of connections from each of the dancers laptops
    Each connection will be run on an individual thread
    '''
    def setup_connection(self):
        # Create a TCP/IP socket and bind to port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_address = (self.ip_addr, self.port_num)
        print('Ultra96 Server starting on %s port %s. Allowing connection from dancers laptops' % server_address)
        self.socket.bind(server_address)
        # Listen for incoming connections
        self.socket.listen(5)
        
        connection_counter = 0
        while True:
            connection, client_address = self.socket.accept()
            # connection.settimeout(10)
            print(f'Connection from {client_address} has been establised')
            connection_counter += 1
            if connection_counter <= MAX_DANCERS:
                client_thread = threading.Thread(target=self.client_connection, args=(connection_counter,connection,client_address))
                self.connections.append(connection)
                client_thread.daemon=True
                client_thread.start()
                if connection_counter == MAX_DANCERS:
                    print('The maximum number of client connections has been reached')
                    break

    '''
    Manage each laptop connection to receive and send data here
    '''
    def client_connection(self, conn_id, connection, client_address):
        if verbose:
            print(f'Thread for connection {conn_id} has started')
        while not self.shutdown.is_set():
            data = connection.recv(1024)
            if data:
                self.t2 = time.time()
                try:
                    message = data.decode(FORMAT)
                    decrypted_message = self.decrypt_message(message)
                    messages = decrypted_message.split('|')

                    # Store the decrypted inputs from each dancer into variables
                    packet_type = messages[0]
                    if "T" in packet_type: # Time Sync Packet
                        if verbose:
                            print('Data received. Timestamp t2: ' + str(self.t2))
                        self.send_timestamp(connection)

                    elif "O" in packet_type: # Dancer Clock Offset
                        clock_offset = messages[1]
                        print('Clock Offset: ' + clock_offset)

                    elif "E" in packet_type: # Emg Data Packet
                        emg = messages[1]

                    elif "D" in packet_type: # Raw Data Packet
                         Ax = messages[1]
                         Ay = messages[2]
                         Az = messages[3]
                         Rx = messages[4]
                         Ry = messages[5]
                         Rz = messages[6]

                    if verbose:
                        print('Received message: ' + decrypted_message)
                        print('Data Packet Type: ' + messages[0])

                except Exception as e:
                    print(e)
            else:
                print('no more data from', client_address)
                self.stop()

    def send_timestamp(self, connection):
        self.t3 = time.time()
        timestamp = str(self.t2) + '|' + str(self.t3)

        if verbose:
            print('Sending Data. Timestamp t3: ' + str(self.t3))

        connection.sendall(timestamp.encode(FORMAT))


    '''
    Encryption and Decryption of messages using AES
    '''

    def decrypt_message(self, cipher_text):
        decoded_message = base64.b64decode(cipher_text)
        iv = decoded_message[:16]
        secret_key = bytes(str(self.secret_key), encoding='utf8')

        cipher = AES.new(secret_key, AES.MODE_CBC, iv)

        decrypted_message = cipher.decrypt(decoded_message[16:]).strip()
        decrypted_message = decrypted_message.decode('utf8')

        decrypted_message = decrypted_message[decrypted_message.find('#'):]
        decrypted_message = bytes(decrypted_message[1:], 'utf8').decode('utf8')
        return decrypted_message

    def add_padding(self, message):
        pad = lambda s: s + (BLOCK_SIZE - (len(s) % BLOCK_SIZE)) * PADDING
        padded_message = pad(message)
        return padded_message

    def encrypt_message(self, plain_text):
        padded_message = self.add_padding(plain_text)
        iv = Random.new().read(AES.block_size)
        aes_key = bytes(str(self.secret_key), encoding="utf8")
        cipher = AES.new(aes_key, AES.MODE_CBC, iv)
        encrypted_message = base64.b64encode(iv + cipher.encrypt(bytes(padded_message, "utf8")))
        return encrypted_message

    def stop(self):
        for conn in self.connections:
            conn.close()
        self.shutdown.set()
        self.socket.close()
        print('Ultra96 Server has shutdown.')

    '''
    ADDITIONAL CONNECTIONS AND CONDITIONS
    '''
    # if CONNECT_TO_EVAL_SERVER:




def main(secret_key):
    u96_server = Server(IP_ADDR, PORT_NUM, GROUP_ID, secret_key)
    u96_server.start()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Ultra96 Server set-up for Laptops to connect")
    parser.add_argument('-s', '--secret_key', metavar='', default='cg40024002group2', help='secret key')
    parser.add_argument('-v', '--verbose', type=bool, default=False, help='verbose')

    args = parser.parse_args()

    secret_key = args.secret_key
    verbose = args.verbose

    main(secret_key)
