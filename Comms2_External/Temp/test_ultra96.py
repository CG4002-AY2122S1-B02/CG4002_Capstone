# Script to receive connection on Ultra96 from Dashboard Server to send data over

import argparse
import sys
import socket
import threading
import time
import random
import base64
import packet_pb2

from Crypto import Random
from Crypto.Cipher import AES

# Initialise Variable Sizes
FORMAT = 'utf8'
MAX_CONNECTIONS = 4

# Assign the host and port numbers of our Ultra96 Server
IP_ADDR = '127.0.0.1'
PORT = 8080     # Start Pseudo-Utlra96 server on a random port
PORT_NUMS = [8880,8881,8882,8883]

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

class Server(threading.Thread):
    def __init__(self, ip_addr, port_num):
        super(Server, self).__init__()

        '''
        Create Data Structures to store each of the laptop connections here
        '''
        self.ip_addr = ip_addr
        self.port_num = port_num
        self.shutdown = threading.Event()
        self.db_connections = []

        # Create connections to different sockets on dashboard server
        self.setup_connection()

    '''
    Creates one socket for each connection coming from laptop
    '''
    def setup_connection(self):
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
            conn1, db_addr1 = self.socket1.accept()
            db_thread1 = threading.Thread(target=self.run, args=(conn1,db_addr1, "position"))
            self.db_connections.append(conn1)
            db_thread1.daemon = True
            db_thread1.start()
            print(f'Connection from {db_addr1} has been establised')

            conn2, db_addr2 = self.socket2.accept()
            db_thread2 = threading.Thread(target=self.run, args=(conn2,db_addr2, "packet"))
            self.db_connections.append(conn2)
            db_thread2.daemon = True
            db_thread2.start()
            print(f'Connection from {db_addr2} has been establised')

            conn3, db_addr3 = self.socket3.accept()
            db_thread3 = threading.Thread(target=self.run, args=(conn3,db_addr3, "packet"))
            self.db_connections.append(conn3)
            db_thread3.daemon = True
            db_thread3.start()
            print(f'Connection from {db_addr3} has been establised')

            conn4, db_addr4 = self.socket4.accept()
            db_thread4 = threading.Thread(target=self.run, args=(conn4,db_addr4, "packet"))
            self.db_connections.append(conn4)
            db_thread4.daemon = True
            db_thread4.start()
            print(f'Connection from {db_addr4} has been establised')
            print(len(self.db_connections))

    '''
    Main Run function that will be constantly checking for data and sending over to dashboard server
    '''
    def run(self,conn,addr, packet_type):
        while not self.shutdown.is_set():
            # For testing, simulate choosing a random port connection to send data to
            true_or_false = [0,1]
            is_send = random.choice(true_or_false)
            is_send = True
            #print(is_send)
            #print(len(self.db_connections))
            # Format - # position
            # test_position_msg = '# 1 3 2'
            # Format - # user | dance_move | accuracy

            packet = {}
            if packet_type == "position":
                packet = position_stream_test[random.randint(0,5)]
            else:
                packet = packet_stream_test[random.randint(0,7)]

#             packet = packet_stream_test[0]
            packet.end = "\x7F"
            packet.epoch_ms = int(time.time() * 1000 + random.randint(0,1000))

            if is_send:
                print('Sending data to db via port: ' + str(addr[1]))
                conn.sendall(packet.SerializeToString())

            time.sleep(3)

    def stop(self):
        for conn in self.db_connections:
            conn.close()
        self.shutdown.set()
        print('Ultra96 Server has shutdown.')


def main():
    db_server = Server(IP_ADDR, PORT)
    db_server.start()
    print('Waiting for 60 seconds for db_connections to complete!')
    time.sleep(15) # Give time for the sockets to be up and for db_side to connect

    # Close the test server and all the ports after 10 mins of testing
    time.sleep(600)
    db_server.stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Ultra96 Server set-up for Database to connect")
    parser.add_argument('-v', '--verbose', type=bool, default=False, help='verbose')

    args = parser.parse_args()
    verbose = args.verbose

    main()