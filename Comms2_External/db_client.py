# Script to retrieve data (one-way communication) on Laptop from Ultra96 Server
# Implementation using Python Socket API

import sys
import socket
import time
import base64
import threading

from Crypto import Random
from Crypto.Cipher import AES

import paramiko
import sshtunnel
from paramiko import SSHClient

# Initialise SSHTunnel Connection Information
TUNNEL_ONE_SSH_ADDR = "sunfire.comp.nus.edu.sg"
TUNNEL_ONE_SSH_USERNAME = "e0325893"
TUNNEL_ONE_SSH_PASSWORD = "iLoveCapstoneB02"

TUNNEL_TWO_SSH_ADDR = "137.132.86.225"
TUNNEL_TWO_SSH_USERNAME = "xilinx"
TUNNEL_TWO_SSH_PASSWORD = "cg4002b02"

# Initialise Socket Information
IP_ADDR = '127.0.0.1'
PORT_NUMS = [8880,8881,8882,8883]

# Initialise fixed variables
FORMAT = 'utf8'

class Client(threading.Thread):
    def __init__(self, ip_addr, port_num):
        super(Client, self).__init__()

        # Create a TCP/IP socket and connect to Ultra96 Server
        self.port_num = port_num
        self.ip_addr = ip_addr
        self.shutdown = threading.Event()

    def start_ssh_tunnel(self):
        # Create Tunnel One from Laptop into NUS Sunfire Server
        tunnel_one =  sshtunnel.open_tunnel(
           (TUNNEL_ONE_SSH_ADDR,22), # Remote Server IP
            ssh_username=TUNNEL_ONE_SSH_USERNAME,
            ssh_password=TUNNEL_ONE_SSH_PASSWORD,
            remote_bind_address=(TUNNEL_TWO_SSH_ADDR,22), # Private Server IP
        )
        tunnel_one.start()
        print('Connection to tunnel_one (sunfire:22) OK...')

        # Create Tunnel Two from Sunfire Server to Ultra96 Server
        tunnel_two = sshtunnel.open_tunnel(
            ssh_address_or_host=('127.0.0.1',tunnel_one.local_bind_port),
            remote_bind_address=('127.0.0.1',self.port_num), # Local bind port
            ssh_username=TUNNEL_TWO_SSH_USERNAME,
            ssh_password=TUNNEL_TWO_SSH_PASSWORD,
            local_bind_address=('127.0.0.1',self.port_num) # Local bind port
        )
        tunnel_two.start()
        print(f'Connection to tunnel_two (137.132.86.225:{self.port_num}) OK...')

    def run(self):
        #self.start_ssh_tunnel()
        server_address = (self.ip_addr, self.port_num)
        print('Trying to connect to %s port %s' % server_address)    
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect(server_address)
            print("Successfully connected to the Ultra96 server")
        except Exception:
            print('An error has occured when trying to connect to Ultra96 Server.')

        while True:
            message = self.receive_data()
            print('Received data on port: ' + str(self.port_num))
            print('Message Received: ' + message)

    '''
    Function to ensure dashboard server is constantly receiving available data from Ultra96
    '''
    def receive_data(self):
        while not self.shutdown.is_set():
            data = self.socket.recv(1024)
            if data:
                try:
                    message = data.decode(FORMAT)
                    return message
                except Exception as e:
                    return e


    def stop(self):
        self.shutdown.set()
        self.socket.close()

def main():
    '''
    Port 8080 ==> Recieve position Data | Port 8081 ==> Recieve Dancer 1 Data
    Port 8082 ==> Recieve Dancer 2 Data | Port 8083 ==> Recieve Dancer 3 Data
    '''
    if len(sys.argv) != 2:
        print('Invalid number of arguments')
        print('python3 db_client.py [port_num]')
        sys.exit()

    port = int(sys.argv[1])
    db_client = Client(IP_ADDR,port)
    db_client.run()

'''
    db_client1 = Client(IP_ADDR, PORT_NUMS[0])
    db_client1.run()
    db_client2 = Client(IP_ADDR, PORT_NUMS[1])
    db_client2.run()
    db_client3 = Client(IP_ADDR, PORT_NUMS[2])
    db_client3.run()
    db_client4 = Client(IP_ADDR, PORT_NUMS[3])
    db_client4.run()
    time.sleep(10)
'''

if __name__ == '__main__':
    main()
