# Script to send data (two-way communication) from Laptop to Ultra96 Server
# Implementation using Python Socket API

import ntplib
import sys
import socket
import time
import base64

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
PORT_NUM = 3000
GROUP_ID = 2
SECRET_KEY = 'cg40024002group2'

# Initialise Global Variables
BLOCK_SIZE = 16
PADDING = ' '
FORMAT = 'utf8'

class Client():
    def __init__(self, dancer_id, ip_addr, port_num, group_id, secret_key):
        super(Client, self).__init__()

        # Create a TCP/IP socket and connect to Ultra96 Server
        self.dancer_id = dancer_id
        self.port_num = port_num
        self.ip_addr = ip_addr
        self.group_id = group_id
        self.secret_key = secret_key

    '''
    Create a "Double-Hop" SSH Tunnel for Dancer's Laptops to Reach Ultra96 Server

    | LOCAL CLIENT | <====Firewall====> | REMOTE SERVER | <==local==> | PRIVATE SERVER |
    |    LAPTOP    | <==SSH==Port 22==> |  NUS Sunfire  | <===SSH===> |    Ultra 96    |
    '''

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
        print('Connection to tunnel_two (137.132.86.225:3000) OK...')

    def run(self):
        #self.start_ssh_tunnel()
        server_address = (self.ip_addr, self.port_num)
        print('Trying to connect to %s port %s' % server_address)    
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect(server_address)
            print("Successfully connected to the Ultra96 server")
        except Exception as e:
            print('An error has occured when trying to connect to Ultra96 Server.')

    '''
    Methods for Encryption and Decryption
    '''
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

    '''
    Retrieve message from Bluno and Send to Ultra96 Server
    '''
    def manage_bluno_data(self):
        # Don't send anything until all dancer ready flag is set

        # Simulate retrieve and send data to Ultra96 Server
        raw_data = '#D|Ax|Ay|Az|Rx|Ry|Rz'
        emg_data = '#E|emg'

        # Simluate Sending T packet to initialize Time Sync Protocol
        self.sync_clock()
        
    def send_data(self, data):
        encrypted_message = self.encrypt_message(data)
        self.socket.sendall(encrypted_message)

    '''
    Functions to call to initiate Time Sync Protocol that calculates RRT and Offset
    '''
    def sync_clock(self):
        self.RTT = 0.0
        self.offset = 0.0
        timestamp_data = '#T'
        # Timestamp t1: When laptop receives a packet from Bluno Beetle
        t1 = time.time()
        print('<==========Starting Time Sync Protocol==========>')
        print('Sending Time Sync Packet. Timestamp t1: ', str(t1))
        self.send_data(timestamp_data)

        timestamp = self.receive_timestamp()
        # Timestamp t4: When laptop receives time sync response from Ultra96
        t4 = time.time()
        t2 = float(timestamp.split('|')[0])
        print('Ultra96 received Packet.  Timestamp t2: ', str(t2))
        t3 = float(timestamp.split('|')[1])
        print('Ultra96 sent response.    Timestamp t3: ', str(t3))
        print('Received Timestamp.       Timestamp t4: ', str(t4))
        
        self.RTT = (t2 - t1) - (t3 - t4)
        print('Round Trip Time: ', str(self.RTT))

        self.offset = (t2 - t1) - self.RTT/2
        print('Clock Offset: ', str(self.offset))
        print('<===============================================>')
        timestamp_data = '#O' + '|' + str(self.offset)
        self.send_data(timestamp_data)

    def receive_timestamp(self):
        message = self.socket.recv(1024)
        timestamp = message.decode(FORMAT)
        return timestamp

    '''
    Get time from NTP Server and calculate offset with system(laptop) clock
    '''
    def ntp_time_sync(self):
        try:
            ntp_client = ntplib.NTPClient()
            response = ntp_client.request('pool.ntp.org')
            print(responsed.tx_time)
        except Exception as e:
            return None

    def stop(self):
        self.socket.close()

def main():
    if len(sys.argv) != 2:
        print('Invalid number of arguments')
        print('python Laptop_client.py [dancer_id]')
        sys.exit()

    dancer_id = int(sys.argv[1])
    ip_addr = '127.0.0.1'
    port_num = 3000
    group_id = GROUP_ID
    secret_key = SECRET_KEY

    my_client = Client(dancer_id, ip_addr, port_num, group_id, secret_key)
    my_client.run()
    my_client.ntp_time_sync()
    time.sleep(10)

    # Simulate sending data from Bluno for Testing
    count = 0
    while count < 4:
        my_client.manage_bluno_data()
        time.sleep(5)
        count += 1

    my_client.stop()


if __name__ == '__main__':
    main()
