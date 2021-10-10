# Test Script to receive connection on Ultra96 from Laptops 

import argparse
import sys
import socket
import threading
import time
import base64
import random
from multiprocessing import Process,Queue,Pipe
from queue import Queue

import packet_pb2
import math_loser
import pandas as pd

from Crypto import Random
from Crypto.Cipher import AES

# Initialise Variable Sizes
MAX_DANCERS = 3
MAX_DB_CONNECTIONS = 4
BLUNO_PER_LAPTOP = 1

# Assign the host and port numbers of our Ultra96 Server 
IP_ADDR = '127.0.0.1'
PORT_NUM = 8000
GROUP_ID = 2

# Assign the host and port numbers of our Evaluation Server
EVAL_IP_ADDR = '127.0.0.1'
EVAL_PORT_NUM = 9000

# Assign the port numbers to allow connections from db client
PORT_NUMS = [8880,8881,8882,8883]

# Initialise Global Variables
BLOCK_SIZE = 16
PADDING = ' '
FORMAT = "utf8"

# By default set to False. Specify '-D' while running script to connect to database server.
CONNECT_TO_DATABASE = False

# By default set to False. Specify '-E' while running script to connect to eval server.
CONNECT_TO_EVAL_SERVER = False

# By default set to False. Specify '-C' while running script for data collection mode.
DATA_COLLECTION_MODE = False

position_stream_test = [
    packet_pb2.Position(
        position="123"
    ),
    packet_pb2.Position(
        position="213"
    ),
    packet_pb2.Position(
        position="312"
    ),
    packet_pb2.Position(
        position="321"
    ),
    packet_pb2.Position(
        position="231"
    ),
    packet_pb2.Position(
        position="132"
    ),
]

packet_stream_test = [
    packet_pb2.Packet(
        dance_move = "Dab",
        accuracy=2,
    ),
    packet_pb2.Packet(
        dance_move = "Scarecrow",
        accuracy=1,
    ),
    packet_pb2.Packet(
        dance_move = "Window360",
        accuracy=3,
    ),
    packet_pb2.Packet(
        dance_move = "James Bond",
        accuracy=3,
    ),
    packet_pb2.Packet(
        dance_move = "Mermaid",
        accuracy=2,
    ),
    packet_pb2.Packet(
        dance_move = "Push Back",
        accuracy=2,
    ),
    packet_pb2.Packet(
        dance_move = "Snake",
        accuracy=3,
    ),
    packet_pb2.Packet(
        dance_move = "Cowboy",
        accuracy=1,
    )
]

class Ultra96_Server(threading.Thread):
    def __init__(self, ip_addr, port_num, group_id, secret_key):
        super(Ultra96_Server, self).__init__()

        '''
        Create Data Structures to store each of the laptop connections here
        '''
        self.ip_addr = ip_addr
        self.port_num = port_num
        self.secret_key = secret_key
        self.shutdown = threading.Event()

        # For the purpose of testing
        self.num_of_moves_predicted = 0
        self.predicted_move = 0

        # Variables for Time Sync Protocol
        self.dancer_sync_delay = 0
        self.dancer_time_offset = {
            1 : 0,
            2 : 0,
            3 : 0
        }

        self.start_time_map_dancers = {
            1 : -1,
            2 : -1,
            3 : -1
        }

        # Data Structures to store raw data from dancers
        self.dancer_1_data = Queue()
        self.dancer_2_data = Queue()
        self.dancer_3_data = Queue()

        # Data Structures to store positional data from dancers
        self.current_positions = '1 2 3'
        self.actual_dance_positions = '1 2 3'
        self.dancer_1_position_data = Queue()
        self.dancer_2_position_data = Queue()
        self.dancer_3_position_data = Queue()

        # Data Structures and Variables to ensure proper synchronization
        self.laptop_connections = []
        self.laptops_connected = False
        self.db_connections = []
        self.database_connected = False
        self.start_evaluation = False

        self.dancer_1_send_position = False
        self.dancer_2_send_position = False
        self.dancer_3_send_position = False

        self.dancer_1_send_packet = False
        self.dancer_2_send_packet = False
        self.dancer_3_send_packet = False

        self.is_dancers_predicted = [False,False,False]

        # Sequence 0: Start the Evaluation Server
        # Sequence 1: Start this Ultra96_db_server.py Script
        # Sequence 2: Create connections to laptops
        self.setup_connection_to_laptops()

        # Sequence 3: Create connection to eval server
        if CONNECT_TO_EVAL_SERVER:
            self.setup_connection_to_eval_server()

            self.prediction_thread = threading.Thread(target=self.generate_predictions)
            self.prediction_thread.daemon = True
            self.prediction_thread.start()

        # Sequence 4: Create connections to database
        if CONNECT_TO_DATABASE:
            self.setup_connection_to_database()

        #if DATA_COLLECTION_MDOE:
        #    self.write_to_file()

    '''
    Allow and keep track of connections from each of the dancers laptops
    Each connection will be run on an individual thread
    '''
    def setup_connection_to_laptops(self):
        # Create a TCP/IP socket and bind to port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_address = (self.ip_addr, self.port_num)
        print(f'Ultra96 Server starting on %s port %s. Allowing connection from {MAX_DANCERS} dancers laptops' % server_address)
        self.socket.bind(server_address)
        # Listen for incoming connections
        self.socket.listen(5)
        
        connection_counter = 0
        while True:
            connection, client_address = self.socket.accept()
            print(f'Connection from {client_address} has been establised')
            connection_counter += 1
            if connection_counter <= MAX_DANCERS:
                client_thread = threading.Thread(target=self.receive_and_send_data_laptop, args=(connection_counter,connection,client_address))
                self.laptop_connections.append(connection)
                client_thread.daemon=True
                client_thread.start()
                if connection_counter == MAX_DANCERS:
                    self.laptops_connected = True
                    print('The maximum number of dancer laptop connections has been reached')
                    break

    '''
    Manage each laptop connection to receive and send data here
    '''
    def receive_and_send_data_laptop(self, conn_id, connection, client_address):
        if verbose:
            print(f'Thread for connection {conn_id} has started')
        while not self.shutdown.is_set():
            if self.start_evaluation:
                data = connection.recv(1024)
                if data:
                    t2 = time.time()
                    try:
                        message = data.decode(FORMAT)
                        decrypted_message = self.decrypt_message(message)
                        messages = decrypted_message.split('|')

                        # Store the decrypted inputs from each dancer into variables
                        packet_type = messages[0]
                        dancer_id = int(messages[1])
                        if verbose:
                            print(' ')
                            print('Dancer Id: ', dancer_id)
                            print('Received message: ', decrypted_message)
                            
                        if 'T' in packet_type: # Time Sync Packet
                            #if verbose:
                                #print('Data received. Timestamp t2: ' + str(t2))
                            self.send_timestamp(t2, connection)

                        elif 'O' in packet_type: # Store new Dancer Clock Offset
                            clock_offset = float(messages[2])
                            self.dancer_time_offset[dancer_id] = clock_offset
                            print(f'Dancer {dancer_id} Clock Offset: ', str(self.dancer_time_offset[dancer_id]))
                            
                        #elif 'E' in packet_type: # Emg Data Packet
                            #emg = messages[2]
                            #Send to dashboard

                        elif 'D' in packet_type: # Raw Data Packet
                            Ax = float(messages[2])
                            #Ay = messages[3]
                            #Az = messages[4]
                            #Rx = messages[5]
                            #Ry = messages[6]
                            #Rz = messages[7]
                            start_flag = messages[8] # S | N
                            timestamp = messages[9]

                            # Do Data processing here
                            if start_flag == 'S':
                                if dancer_id in self.start_time_map_dancers:
                                    if self.start_time_map_dancers[dancer_id] == -1:
                                        self.start_time_map_dancers[dancer_id] = float(timestamp)
                                        self.is_dancers_predicted[dancer_id-1] = bool(True)
                                        if verbose:
                                            print(f'Start of first move detected from dancer {dancer_id}!')
                                    else:
                                        # Store the start timestamp of the dance move as well
                                        self.start_time_map_dancers[dancer_id] = float(timestamp)  

                            if dancer_id == 1:
                                self.dancer_1_send_packet = True
                                #raw_data = Ax + '|' + Ay + '|' + Az + '|' + Rx + '|' + Ry + '|' + Rz
                                self.dancer_1_data.put(Ax)
                            elif dancer_id == 2:
                                self.dancer_2_send_packet = True
                                #raw_data = Ax + '|' + Ay + '|' + Az + '|' + Rx + '|' + Ry + '|' + Rz
                                self.dancer_2_data.put(Ax)
                            elif dancer_id == 3:
                                self.dancer_3_send_packet = True
                                #raw_data = Ax + '|' + Ay + '|' + Az + '|' + Rx + '|' + Ry + '|' + Rz
                                self.dancer_3_data.put(Ax)

                    except Exception as e:
                        print(e)
                else:
                    print('no more data from', client_address)
                    self.stop()

    def send_timestamp(self, t2, connection):
        t3 = time.time()
        timestamp = '#' + str(t2) + '|' + str(t3) + '|'

        #if verbose:
            #print('Sending Data. Timestamp t3: ' + str(t3))

        encrypted_message = self.encrypt_message(timestamp)
        connection.sendall(encrypted_message)

    '''
    Establish connection with eval server and send data over through the socket
    Creates one socket for one connection to the eval server
    '''
    def setup_connection_to_eval_server(self):
        # Create a TCP/IP socket and bind to port
        self.eval_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.eval_server_address = (EVAL_IP_ADDR, EVAL_PORT_NUM)
        print('Ultra96 Client starting on %s port %s. Establishing connection with Eval Server' % self.eval_server_address)
        self.eval_server_socket.connect(self.eval_server_address)
        print('Ultra96 Client has connected to Evaluation Server')

    def send_and_receive_eval_server(self,action):
        # Receive the predicted positions from ML
        # Calculate the sync delay in milliseconds
        timings_list = []
        for key in self.start_time_map_dancers:
            # Start dance move timestamp + Dancer Clock Offset = Actual timestamp relative to Ultra96
            timings_list.append(self.start_time_map_dancers[key] + self.dancer_time_offset[key])
            if timings_list[key-1] == -1:
                print(f'The start timing for dancer {key} has not been updated!')
                break
        self.dancer_sync_delay = (max(timings_list) - min(timings_list)) * 1000
        eval_data = '#' + self.current_positions + '|' + action + '|' + str(self.dancer_sync_delay) + '|'
        print('Sending the following message to Evaluation Server', eval_data)
        encrypted_message = self.encrypt_message(eval_data)
        
        try:
            self.eval_server_socket.sendall(encrypted_message)
        except:
            print('Connection from Ultra96 to Evaluation Server lost! Attempting reconnection...')
            self.setup_connection_to_eval_server()
            time.sleep(5)
            pass

        # Reset the start time map
        for key in self.start_time_map_dancers:
            self.start_time_map_dancers[key] = -1
        # Receive actual previous dancer positions from Evaluation Server
        while True:
            data = self.eval_server_socket.recv(1024)
            if data:
                dancer_positions = data.decode(FORMAT)
                print('Received actual dancer position: ', dancer_positions)
                self.actual_dance_positions = dancer_positions
                break
    

    '''
    Establish connection with database and send data over through 4 ports
    Creates one socket for each connection coming from laptop
    '''
    def setup_connection_to_database(self):
        # Create a TCP/IP socket and bind to port
        self.socket1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket3 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket4 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        address1 = (self.ip_addr, PORT_NUMS[0])
        print('Ultra96 Server starting on %s port %s. Allowing connection from db' % address1)
        self.socket1.bind(address1)
        self.socket1.listen(1)

        address2 = (self.ip_addr, PORT_NUMS[1])
        print('Ultra96 Server starting on %s port %s. Allowing connection from db' % address2)
        self.socket2.bind(address2)
        self.socket2.listen(1)

        address3 = (self.ip_addr, PORT_NUMS[2])
        print('Ultra96 Server starting on %s port %s. Allowing connection from db' % address3)
        self.socket3.bind(address3)
        self.socket3.listen(1)
       
        address4 = (self.ip_addr, PORT_NUMS[3])
        print('Ultra96 Server starting on %s port %s. Allowing connection from db' % address4) 
        self.socket4.bind(address4)
        self.socket4.listen(1)

        while True:
            # Connection to receive general dancer positions
            conn1, db_addr1 = self.socket1.accept()
            db_thread1 = threading.Thread(target=self.send_data_to_database, args=(conn1,db_addr1,0))
            self.db_connections.append(conn1)
            db_thread1.daemon = True
            db_thread1.start()
            print(f'Connection from {db_addr1} has been establised')
            if verbose: 
                print('Number of database connections: ' + str(len(self.db_connections)))
            # Connection to receive dancer 1 packet information
            conn2, db_addr2 = self.socket2.accept()
            db_thread2 = threading.Thread(target=self.send_data_to_database, args=(conn2,db_addr2,1))
            self.db_connections.append(conn2)
            db_thread2.daemon = True
            db_thread2.start()
            print(f'Connection from {db_addr2} has been establised')
            if verbose: 
                print('Number of database connections: ' + str(len(self.db_connections)))
            # Connection to receive dancer 2 packet information
            conn3, db_addr3 = self.socket3.accept()
            db_thread3 = threading.Thread(target=self.send_data_to_database, args=(conn3,db_addr3,2))
            self.db_connections.append(conn3)
            db_thread3.daemon = True
            db_thread3.start()
            print(f'Connection from {db_addr3} has been establised')
            if verbose: 
                print('Number of database connections: ' + str(len(self.db_connections)))
            # Connection to receive dancer 3 packet information
            conn4, db_addr4 = self.socket4.accept()
            db_thread4 = threading.Thread(target=self.send_data_to_database, args=(conn4,db_addr4,3))
            self.db_connections.append(conn4)
            db_thread4.daemon = True
            db_thread4.start()
            print(f'Connection from {db_addr4} has been establised')
            if verbose: 
                print('Number of database connections: ' + str(len(self.db_connections)))

            if len(self.db_connections) == MAX_DB_CONNECTIONS:
                    self.database_connected = True
                    print('The maximum number of db connections has been reached')
                    break

    def send_start_flag_to_laptops(self):
        # Send start flag to all dancers to tell them start sending data
        if self.laptops_connected: #and self.database_connected:
            for conn in self.laptop_connections:
                encrypted_message = self.encrypt_message('#S|')
                conn.sendall(encrypted_message)
            self.start_evaluation = True
            print('Evaluation will begin now! :-)')

    '''
    Run function that will be constantly checking for data and sending over to dashboard server
    '''
    def send_data_to_database(self,conn,addr,dancer_id):
        while not self.shutdown.is_set():
            if self.start_evaluation:
                packet = {}

                true_or_false = [0,1]
                is_send = bool(random.choice(true_or_false))
                if is_send and dancer_id == 0:
                    packet = position_stream_test[random.randint(0,5)]
                    packet.end = "\x7F"
                    packet.epoch_ms = int(time.time() * 1000 + random.randint(0,1000))
                    print('Sending data to db via port: ' + str(addr[1]))
                    conn.sendall(packet.SerializeToString())
                    time.sleep(3)

                # Only send information over to database once new data is ready and processed
                elif self.dancer_1_send_packet and dancer_id == 1:
                    while not self.dancer_1_data.empty():
                        message = self.dancer_1_data.get()
                        packet = packet_pb2.Packet(
                            dance_move = "Dab",
                            accuracy = message,
                            #epoch_ms = int(self.dancer_1_offset)
                        )
                        packet.end = "\x7F"
                        #packet.epoch_ms = int(time.time() * 1000 + random.randint(0,1000))
                        packet.epoch_ms = abs(int(self.start_time_map_dancers[dancer_id] * 1000 + self.dancer_time_offset[dancer_id] * 1000))
                        print('Sending data to db via port: ' + str(addr[1]))
                        conn.sendall(packet.SerializeToString())
                        self.dancer_1_send_packet = False

                elif self.dancer_2_send_packet and dancer_id == 2:
                    while not self.dancer_2_data.empty():
                        message = self.dancer_2_data.get()
                        packet = packet_pb2.Packet(
                            dance_move = "Mermaid",
                            accuracy = message,
                            #epoch_ms = int(self.dancer_2_offset)
                        )
                        packet.end = "\x7F"
                        #packet.epoch_ms = int(time.time() * 1000 + random.randint(0,1000))
                        packet.epoch_ms = abs(int(self.start_time_map_dancers[dancer_id] * 1000 + self.dancer_time_offset[dancer_id] * 1000))
                        print('Sending data to db via port: ' + str(addr[1]))
                        conn.sendall(packet.SerializeToString())
                        self.dancer_2_send_packet = False

                elif self.dancer_3_send_packet and dancer_id == 3:
                    while not self.dancer_3_data.empty():
                        message = self.dancer_3_data.get()
                        packet = packet_pb2.Packet(
                            dance_move = "James Bond",
                            accuracy = message,
                            #epoch_ms = int(self.dancer_3_offset)
                        )
                        packet.end = "\x7F"
                        #packet.epoch_ms = int(time.time() * 1000 + random.randint(0,1000))
                        packet.epoch_ms = abs(int(self.start_time_map_dancers[dancer_id] * 1000 + self.dancer_time_offset[dancer_id] * 1000))
                        print('Sending data to db via port: ' + str(addr[1]))
                        conn.sendall(packet.SerializeToString())
                        self.dancer_3_send_packet = False

                # if self.dancer_1_send_packet and dancer_id == 1:
                #     while not self.dancer_1_data.empty():
                #         message = str(self.dancer_1_data.get())
                #         conn.sendall(message.encode(FORMAT))
                #         self.dancer_1_send_packet = False
                #         print('Sending data to db via port: ' + str(addr[1]))

                # elif self.dancer_2_send_packet and dancer_id == 2:
                #     while not self.dancer_2_data.empty():
                #         message = str(self.dancer_2_data.get())
                #         conn.sendall(message.encode(FORMAT))
                #         self.dancer_2_send_packet = False
                #         print('Sending data to db via port: ' + str(addr[1]))

                # elif self.dancer_3_send_packet and dancer_id == 3:
                #     while not self.dancer_3_data.empty():
                #         message = str(self.dancer_3_data.get())
                #         conn.sendall(message.encode(FORMAT))
                #         self.dancer_3_send_packet = False
                #         print('Sending data to db via port: ' + str(addr[1]))
            
    '''
    Prediction funciton here that will integrate with SW1 (Ren Hao's ) code: Machine Learning 
    '''
    def generate_predictions(self):
        while True:
            if self.is_dancers_predicted[0] and self.is_dancers_predicted[1] and self.is_dancers_predicted[2]:
                # Not sure where to call this but put here for now for testing/ only send when all dancers finish prediction
                if verbose:
                    print(f'======================= Prediction Number {self.num_of_moves_predicted} ==========================')
                self.num_of_moves_predicted = self.num_of_moves_predicted + 1

                with open('test_single_y.txt', 'r') as f:
                    _y = f.readline().strip()
                print(_y)
                _input_data = pd.read_csv("test_single_x.csv", index_col=False).to_numpy()
                _input_data = _input_data.astype('float32')
                print(f"shape of the input we passed in initially is {_input_data.shape}")
                print(f"type of the input we passed in is {_input_data.dtype}")
                self.predicted_move = math_loser.math_loser(_input_data)
                print(self.predicted_move)
                self.send_and_receive_eval_server('Dab')
                self.is_dancers_predicted[0] = False
                self.is_dancers_predicted[1] = False
                self.is_dancers_predicted[2] = False

    '''
    Encryption and Decryption of messages using AES
    '''
    def decrypt_message(self, cipher_text):
        decoded_message = base64.b64decode(cipher_text)
        iv = decoded_message[:16]
        secret_key = bytes(str(self.secret_key), encoding=FORMAT)

        cipher = AES.new(secret_key, AES.MODE_CBC, iv)

        decrypted_message = cipher.decrypt(decoded_message[16:]).strip()
        decrypted_message = decrypted_message.decode(FORMAT)

        decrypted_message = decrypted_message[decrypted_message.find('#'):]
        decrypted_message = bytes(decrypted_message[1:], FORMAT).decode(FORMAT)
        return decrypted_message

    def add_padding(self, message):
        pad = lambda s: s + (BLOCK_SIZE - (len(s) % BLOCK_SIZE)) * PADDING
        padded_message = pad(message)
        return padded_message

    def encrypt_message(self, plain_text):
        padded_message = self.add_padding(plain_text)
        iv = Random.new().read(BLOCK_SIZE)
        aes_key = bytes(str(self.secret_key), encoding=FORMAT)
        cipher = AES.new(aes_key, AES.MODE_CBC, iv)
        encrypted_message = base64.b64encode(iv + cipher.encrypt(bytes(padded_message,FORMAT)))
        return encrypted_message

    def stop(self):
        for conn in self.laptop_connections:
            conn.close()
        for conn in self.db_connections:
            conn.close()
        self.shutdown.set()
        self.socket.close()
        print('Ultra96 Server has shutdown.')

    '''
    ADDITIONAL CONNECTIONS AND CONDITIONS
    '''
    # if CONNECT_TO_EVAL_SERVER:

def main(secret_key):
    global CONNECT_TO_DATABASE
    global CONNECT_TO_EVAL_SERVER
    global DATA_COLLECTION_MODE

    u96_server = Ultra96_Server(IP_ADDR, PORT_NUM, GROUP_ID, secret_key)
    u96_server.start()
    print('Waiting 60s for laptop, eval server & database connections to complete!')
    time.sleep(60)
    u96_server.send_start_flag_to_laptops()

    # Shutdown Ultra96 Server after 10 mins of testing
    time.sleep(600)
    u96_server.stop()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Ultra96 Server set-up for Laptops to connect")
    parser.add_argument('-s', '--secret_key', metavar='', default='cg40024002group2', help='secret key')
    parser.add_argument('-D', '--connect_to_database', default=False, action='store_true', help='connect_to_database')
    parser.add_argument('-E', '--connect_to_eval_server', default=False, action='store_true', help='connect_to_eval_server')
    parser.add_argument('-C', '--data_collection_mode', default=False, action='store_true', help='data_collection_mode')
    parser.add_argument('-V', '--verbose', default=False, action='store_true', help='verbose')

    args = parser.parse_args()

    secret_key = args.secret_key
    CONNECT_TO_DATABASE = args.connect_to_database
    CONNECT_TO_EVAL_SERVER = args.connect_to_eval_server
    DATA_COLLECTION_MDOE = args.data_collection_mode

    verbose = args.verbose

    main(secret_key)
