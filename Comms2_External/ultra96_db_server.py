# Test Script to receive connection on Ultra96 from Laptops 

import os
import argparse
import sys
import socket
import threading
import time
import base64
import random
from multiprocessing import Process,Queue,Pipe
from collections import deque
from queue import Queue

import packet_pb2
#import math_loser
import pandas as pd

from Crypto import Random
from Crypto.Cipher import AES

# Initialise Variable Sizes
MAX_DB_CONNECTIONS = 4
BLUNO_PER_LAPTOP = 1
NUM_OF_DANCERS = 3
WEEK = 9
ACTIONS = ['mermaid', 'jamesbond', 'dab']
POSITIONS = ['1 2 3', '3 2 1', '2 3 1', '3 1 2', '1 3 2', '2 1 3']

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

# By default set to False. Specify '-D' while running script to connect to dashboard server.
CONNECT_TO_DASHBOARD = False

# By default set to False. Specify '-E' while running script to connect to eval server.
CONNECT_TO_EVAL_SERVER = False

# By default set to False. Specify '-C' while running script for data collection mode.
DATA_COLLECTION_MODE = False
LOG_DIR = os.path.join(os.path.dirname(__file__), 'test_run_logs')

# For Week 9
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

PREDICTION_MAP = {
    0 : "mermaid",
    1 : "jamesbond",
    2 : "dab",
    3 : "window360",
    4 : "cowboy",
    5 : "scarecrow",
    6 : "pushback",
    7 : "snake"
}

PREDICTION_MAP_DASHBOARD = {
    0 : "Mermaid",
    1 : "James Bond",
    2 : "Dab",
    3 : "Window360",
    4 : "Cowboy",
    5 : "Scarecrow",
    6 : "Push Back",
    7 : "Snake"
}

# Different Packet Types
HELLO = 'H'
ACK = 'A'
RESET = 'R'
DATA = 'D'
EMG = 'E'
START_DANCE = 'S'
NORMAL_DANCE = 'N'
TIMESTAMP = 'T'

class Ultra96_Server(threading.Thread):
    def __init__(self, ip_addr, port_num, group_id, secret_key):
        super(Ultra96_Server, self).__init__()

        '''
        Create Data Structures to store each of the laptop connections here
        '''
        self.ip_addr = ip_addr
        self.port_num = port_num
        self.group_id = group_id
        self.secret_key = secret_key
        self.shutdown = threading.Event()

        # For the purpose of testing
        self.num_of_moves_predicted = 0
        self.predicted_move = None

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
        
        self.dancer_data_map = {}
        self.dancer_data_map[0] = Queue()
        self.dancer_data_map[1] = Queue()
        self.dancer_data_map[2] = Queue()

        # Data Structures to store positional data from dancers
        self.current_positions = '1 2 3'
        self.actual_dance_positions = '1 2 3'
        self.dancer_1_position_data = Queue()
        self.dancer_2_position_data = Queue()
        self.dancer_3_position_data = Queue()

        self.dancer_prediction_map = {} # Used to send data to dashboard
        self.dancer_prediction_map[0] = Queue() 
        self.dancer_prediction_map[1] = Queue()  
        self.dancer_prediction_map[2] = Queue()          

        # Data Structures and Variables to ensure proper synchronization
        self.laptop_connections = []
        self.laptops_connected = False
        self.db_connections = []
        self.dashboard_connected = False
        self.start_evaluation = False

        self.dancer_1_send_position = False # Used to send data to dashboard
        self.dancer_2_send_position = False
        self.dancer_3_send_position = False

        self.is_send_dashboard = { # Used to send data to dashboard
            1 : False,
            2 : False,
            3 : False
        }

        self.is_dancers_predicted = [False,False,False] # Used for predictions

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

        # Sequence 4: Create connections to dashboard
        if CONNECT_TO_DASHBOARD:
            self.setup_connection_to_dashboard()

        # Set up data collection logger
        if DATA_COLLECTION_MODE:
            self.log_filename = 'group{}_log.csv'.format(self.group_id)
            if not os.path.exists(LOG_DIR):
                os.makedirs(LOG_DIR)
            self.log_filepath = os.path.join(LOG_DIR, self.log_filename)
            self.columns = ['timestamp','packet_type','dancer_id','Ax','Ay','Az','Rx','Ry','Rz','start_flag']
            self.df = pd.DataFrame(columns=self.columns)
            self.df = self.df.set_index('timestamp')

    '''
    Allow and keep track of connections from each of the dancers laptops
    Each connection will be run on an individual thread
    '''
    def setup_connection_to_laptops(self):
        # Create a TCP/IP socket and bind to port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_address = (self.ip_addr, self.port_num)
        print(f'Ultra96 Server starting on %s port %s. Allowing connection from {NUM_OF_DANCERS} dancers laptops' % server_address)
        self.socket.bind(server_address)
        # Listen for incoming connections
        self.socket.listen(NUM_OF_DANCERS+1)
        
        connection_counter = 0
        while True:
            connection, client_address = self.socket.accept()
            print(f'Connection from {client_address} has been establised')
            connection_counter += 1
            if connection_counter <= NUM_OF_DANCERS:
                client_thread = threading.Thread(target=self.receive_and_send_data_laptop, args=(connection_counter,connection,client_address))
                self.laptop_connections.append(connection)
                client_thread.daemon=True
                client_thread.start()
                if connection_counter == NUM_OF_DANCERS:
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
                            Ax = messages[2]
                            Ay = messages[3]
                            Az = messages[4]
                            Rx = messages[5]
                            Ry = messages[6]
                            Rz = messages[7]
                            start_flag = messages[8] # S | N
                            timestamp = str(float(messages[9])/1000) # Millis format -> But expecting it in seconds

                            self.write_move_to_logger(packet_type,str(dancer_id),Ax,Ay,Az,Rx,Ry,Rz,start_flag,timestamp)

                            # Do Data processing here
                            if start_flag == 'S':
                                if dancer_id in self.start_time_map_dancers:
                                    if self.start_time_map_dancers[dancer_id] == -1:
                                        # Store the start timestamp of the dance move
                                        self.start_time_map_dancers[dancer_id] = float(timestamp)
                                        self.is_dancers_predicted[dancer_id-1] = bool(True)
                                        if verbose:
                                            print(f'Start of move detected from dancer {dancer_id}!')
                                    else:
                                        # Store the start timestamp of the dance move as well (Just-In-Case)
                                        self.start_time_map_dancers[dancer_id] = float(timestamp)
                                        if verbose:
                                            print(f'Start of move detected from dancer {dancer_id}!')  

                            # TO-DO: Store data in Global Queue for each dancer
                            # When there is a certain amount of data collected, call ML function for prediction
                                # 1. Put data into queue
                                # 2. Check for queue size
                                # 3. If queue size == 80 (Means at 20hz, min of 4 seconds have passed, and 80 samples have been collected)
                                # 4. Call ML function and clear the queue
                                # 5. Set dancer predicted to true (self.is_dancers_predicted[dancer_id-1] = True)
                            
                            data_row = [Ax,Ay,Az,Rx,Ry,Rz]
                            self.dancer_data_map[dancer_id-1].put(data_row)

                            if dancer_id == 1:
                                if self.dancer_data_map[dancer_id-1].qsize() == 5: # Wait for 80 samples before calling
                                    prediction_list  = []
                                    for i in range(5):
                                        data_row = self.dancer_data_map[dancer_id-1].get()
                                        prediction_list.append(data_row)
                                    prediction_df = pd.DataFrame(prediction_list)
                                    print(prediction_df)
                                    # prediction = Call ML Function here (prediction_df)
                                    self.is_send_dashboard[dancer_id] = True
                                    self.dancer_prediction_map[dancer_id-1].put(float(1)) # Eventually need to store a tuple (predicted move + accuracy)
                            elif dancer_id == 2:
                                if self.dancer_data_map[dancer_id-1].qsize() == 80: # Wait for 80 samples before calling
                                    prediction_list  = []
                                    for i in range(80):
                                        data_row = self.dancer_data_map[dancer_id-1].get()
                                        prediction_list.append(data_row)
                                    prediction_df = pd.DataFrame(prediction_list)
                                    # prediction = Call ML Function here (prediction_df)
                                    self.is_send_dashboard[dancer_id] = True
                                    self.dancer_prediction_map[dancer_id-1].put(float(1)) # Eventually need to store a tuple (predicted move + accuracy)
                            elif dancer_id == 3:
                                if self.dancer_data_map[dancer_id-1].qsize() == 80: # Wait for 80 samples before calling
                                    prediction_list  = []
                                    for i in range(80):
                                        data_row = self.dancer_data_map[dancer_id-1].get()
                                        prediction_list.append(data_row)
                                    prediction_df = pd.DataFrame(prediction_list)
                                    # prediction = Call ML Function here (prediction_df)
                                    self.is_send_dashboard[dancer_id] = True
                                    self.dancer_prediction_map[dancer_id-1].put(float(1)) # Eventually need to store a tuple (predicted move + accuracy)

                    except Exception as e:
                        print(e)
                else:
                    print('no more data from', client_address)
                    # Only stop on Keyboard Interrupt or Number of Predictions = Certain Amount
                    self.stop()

    def send_timestamp(self, t2, connection):
        t3 = time.time()
        timestamp = '#' + str(t2) + '|' + str(t3)

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
                if NUM_OF_DANCERS == 1:
                    pass
                else:
                    print(f'The start timing for dancer {key} has not been updated!')
                    break
        self.dancer_sync_delay = (max(timings_list) - min(timings_list)) * 1000
        self.current_positions = random.choice(POSITIONS) # For Week 9 fake random positions
        if WEEK == 9:
            eval_data = '#' + self.current_positions + '|' + action + '|' + str(0) # No Sync Delay
        else:
            eval_data = '#' + self.current_positions + '|' + action + '|' + str(self.dancer_sync_delay)
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
                self.actual_dance_positions = data.decode(FORMAT)
                print('Received actual dancer position: ', self.actual_dance_positions)
                break

    '''
    Establish connection with dashboard and send data over through 4 ports
    Creates one socket for each connection coming from laptop
    '''
    def setup_connection_to_dashboard(self):
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
            db_thread1 = threading.Thread(target=self.send_data_to_dashboard, args=(conn1,db_addr1,0))
            self.db_connections.append(conn1)
            db_thread1.daemon = True
            db_thread1.start()
            print(f'Connection from {db_addr1} has been establised')
            if verbose: 
                print('Number of dashboard connections: ' + str(len(self.db_connections)))
            # Connection to receive dancer 1 packet information
            conn2, db_addr2 = self.socket2.accept()
            db_thread2 = threading.Thread(target=self.send_data_to_dashboard, args=(conn2,db_addr2,1))
            self.db_connections.append(conn2)
            db_thread2.daemon = True
            db_thread2.start()
            print(f'Connection from {db_addr2} has been establised')
            if verbose: 
                print('Number of dashboard connections: ' + str(len(self.db_connections)))
            # Connection to receive dancer 2 packet information
            conn3, db_addr3 = self.socket3.accept()
            db_thread3 = threading.Thread(target=self.send_data_to_dashboard, args=(conn3,db_addr3,2))
            self.db_connections.append(conn3)
            db_thread3.daemon = True
            db_thread3.start()
            print(f'Connection from {db_addr3} has been establised')
            if verbose: 
                print('Number of dashboard connections: ' + str(len(self.db_connections)))
            # Connection to receive dancer 3 packet information
            conn4, db_addr4 = self.socket4.accept()
            db_thread4 = threading.Thread(target=self.send_data_to_dashboard, args=(conn4,db_addr4,3))
            self.db_connections.append(conn4)
            db_thread4.daemon = True
            db_thread4.start()
            print(f'Connection from {db_addr4} has been establised')
            if verbose: 
                print('Number of dashboard connections: ' + str(len(self.db_connections)))

            if len(self.db_connections) == MAX_DB_CONNECTIONS:
                    self.dashboard_connected = True
                    print('The maximum number of db connections has been reached')
                    break

    def send_start_flag_to_laptops(self):
        # Send start flag to all dancers to tell them start sending data
        if self.laptops_connected:
            if CONNECT_TO_DASHBOARD:
                if self.dashboard_connected:
                    # Wait for all laptops to connect and dashboard to establish connection
                    for conn in self.laptop_connections:
                        encrypted_message = self.encrypt_message('#S|')
                        conn.sendall(encrypted_message)
                    self.start_evaluation = True
                    print('Evaluation will begin now! :-)')
            else:
                # If dashboard is not connected, just wait for all laptops to establish connection
                for conn in self.laptop_connections:
                    encrypted_message = self.encrypt_message('#S|')
                    conn.sendall(encrypted_message)
                self.start_evaluation = True
                print('Evaluation will begin now! :-)')

    '''
    Run function that will be constantly checking for data and sending over to dashboard server
    '''
    def send_data_to_dashboard(self,conn,addr,dancer_id):
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
                    time.sleep(5)

                # Only send information over to dashboard once new data is ready and processed
                elif self.is_send_dashboard[dancer_id] and dancer_id == 1:
                    while not self.dancer_prediction_map[dancer_id-1].empty():
                        message = self.dancer_prediction_map[dancer_id-1].get() # message here can be a tuple {"dance_move":"dab","accuracy":"0.69"}
                        packet = packet_pb2.Packet(
                            dance_move = "Dab",
                            accuracy = message,
                        )
                        packet.end = "\x7F"
                        packet.epoch_ms = abs(int(self.start_time_map_dancers[dancer_id] * 1000 + self.dancer_time_offset[dancer_id] * 1000))
                        print('Sending data to db via port: ' + str(addr[1]))
                        conn.sendall(packet.SerializeToString())
                        self.is_send_dashboard[dancer_id] = False

                elif self.is_send_dashboard[dancer_id] and dancer_id == 2:
                    while not self.dancer_prediction_map[dancer_id-1].empty():
                        message = self.dancer_prediction_map[dancer_id-1].get() # message here can be a tuple {"dance_move":"dab","accuracy":"0.69"}
                        packet = packet_pb2.Packet(
                            dance_move = "Mermaid",
                            accuracy = message,
                        )
                        packet.end = "\x7F"
                        packet.epoch_ms = abs(int(self.start_time_map_dancers[dancer_id] * 1000 + self.dancer_time_offset[dancer_id] * 1000))
                        print('Sending data to db via port: ' + str(addr[1]))
                        conn.sendall(packet.SerializeToString())
                        self.is_send_dashboard[dancer_id] = False

                elif self.is_send_dashboard[dancer_id] and dancer_id == 3:
                    while not self.dancer_prediction_map[dancer_id-1].empty():
                        message = self.dancer_prediction_map[dancer_id-1].get() # message here can be a tuple {"dance_move":"dab","accuracy":"0.69"}
                        packet = packet_pb2.Packet(
                            dance_move = "James Bond",
                            accuracy = message,
                        )
                        packet.end = "\x7F"
                        packet.epoch_ms = abs(int(self.start_time_map_dancers[dancer_id] * 1000 + self.dancer_time_offset[dancer_id] * 1000))
                        print('Sending data to db via port: ' + str(addr[1]))
                        conn.sendall(packet.SerializeToString())
                        self.is_send_dashboard[dancer_id] = False
            
    '''
    Prediction funciton here that will integrate with SW1 (Ren Hao's) code: Machine Learning 
    '''
    def generate_predictions(self):
        while True: # Remove later such that it only runs once when called
            if NUM_OF_DANCERS == 3:
                if self.is_dancers_predicted[0] and self.is_dancers_predicted[1] and self.is_dancers_predicted[2]:
                    # Not sure where to call this but put here for now for testing/ only send when all dancers finish prediction
                    self.num_of_moves_predicted = self.num_of_moves_predicted + 1
                    if verbose:
                        print(' ')
                        print(f'======================= Prediction Number {self.num_of_moves_predicted} ==========================')
                        print(' ')
                    self.send_and_receive_eval_server('Dab')
                    self.is_dancers_predicted[0] = False
                    self.is_dancers_predicted[1] = False
                    self.is_dancers_predicted[2] = False
                    #prediction = ren_hao_function()
                    #return prediction
            elif NUM_OF_DANCERS == 2:
                if self.is_dancers_predicted[0] and self.is_dancers_predicted[1]:
                    # Not sure where to call this but put here for now for testing/ only send when all dancers finish prediction
                    self.num_of_moves_predicted = self.num_of_moves_predicted + 1
                    if verbose:
                        print(' ')
                        print(f'======================= Prediction Number {self.num_of_moves_predicted} ==========================')
                        print(' ')
                    self.send_and_receive_eval_server('Dab')
                    self.is_dancers_predicted[0] = False
                    self.is_dancers_predicted[1] = False
            elif NUM_OF_DANCERS == 1:
                if self.is_dancers_predicted[0]:
                    # Not sure where to call this but put here for now for testing/ only send when all dancers finish prediction
                    self.num_of_moves_predicted = self.num_of_moves_predicted + 1
                    if verbose:
                        print(' ')
                        print(f'======================= Prediction Number {self.num_of_moves_predicted} ==========================')
                        print(' ')
                    self.send_and_receive_eval_server('Dab')
                    self.is_dancers_predicted[0] = False

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

    '''
    Write data to logger for data collection
    '''
    def write_move_to_logger(self,packet_type,dancer_id,Ax,Ay,Az,Rx,Ry,Rz,start_flag,timestamp):
        log_filepath = self.log_filepath
        #pos_string = self.dancer_positions
        if not os.path.exists(log_filepath): # first write
            with open(log_filepath, 'w') as f:
                self.df.to_csv(f, line_terminator = "\r")

        with open(log_filepath, 'a') as f:
            data = dict()
            data['timestamp'] = timestamp
            data['packet_type'] = packet_type
            data['dancer_id'] = dancer_id
            data['Ax'] = Ax
            data['Ay'] = Ay
            data['Az'] = Az
            data['Rx'] = Rx
            data['Ry'] = Ry
            data['Rz'] = Rz
            data['start_flag'] = start_flag
            
            self.df = pd.DataFrame(data, index=[0])[self.columns].set_index('timestamp')
            self.df.to_csv(f, header=False, mode='a', line_terminator = "\r")

    def stop(self):
        for conn in self.laptop_connections:
            conn.close()
        for conn in self.db_connections:
            conn.close()
        self.shutdown.set()
        self.socket.close()
        print('Ultra96 Server has shutdown.')


def main(secret_key):
    global CONNECT_TO_DASHBOARD
    global CONNECT_TO_EVAL_SERVER
    global NUM_OF_DANCERS
    global DATA_COLLECTION_MODE

    u96_server = Ultra96_Server(IP_ADDR, PORT_NUM, GROUP_ID, secret_key)
    u96_server.start()
    print('Waiting 60s for laptop, eval server & dashboard connections to complete!')
    time.sleep(60)
    u96_server.send_start_flag_to_laptops()

    # Shutdown Ultra96 Server after 10 mins of testing
    time.sleep(600)
    u96_server.stop()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Ultra96 Server set-up for Laptops to connect")
    parser.add_argument('-s', '--secret_key', metavar='', default='cg40024002group2', help='secret key')
    parser.add_argument('-n', '--num_of_dancers', type=int, required=True, help='num_of_dancers')
    parser.add_argument('-D', '--connect_to_dashboard', default=False, action='store_true', help='connect_to_dashboard')
    parser.add_argument('-E', '--connect_to_eval_server', default=False, action='store_true', help='connect_to_eval_server')
    parser.add_argument('-C', '--data_collection_mode', default=False, action='store_true', help='data_collection_mode')
    parser.add_argument('-V', '--verbose', default=False, action='store_true', help='verbose')

    args = parser.parse_args()

    secret_key = args.secret_key
    NUM_OF_DANCERS = args.num_of_dancers
    print(f'Starting dance session with {NUM_OF_DANCERS} dancers! :-D')
    CONNECT_TO_DASHBOARD = args.connect_to_dashboard
    CONNECT_TO_EVAL_SERVER = args.connect_to_eval_server
    DATA_COLLECTION_MODE = args.data_collection_mode

    verbose = args.verbose

    main(secret_key)
