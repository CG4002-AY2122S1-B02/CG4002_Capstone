# Script to send data (two-way communication) from Laptop to Ultra96 Server
# Implementation using Python Socket API

import ntplib
import sys
import socket
import time
import base64
import random
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

# For actual production
PORT_NUMS = [8001,8002,8003,8004]
GROUP_ID = 2
SECRET_KEY = 'cg40024002group2'

# Initialise Global Variables
BLOCK_SIZE = 16
PADDING = ' '
FORMAT = "utf8"

# Allow the client socket to run on its own Thread
class Client(threading.Thread):
    def __init__(self, dancer_id, ip_addr, port_num, group_id, secret_key):
        super(Client, self).__init__()

        # Create a TCP/IP socket and connect to Ultra96 Server
        self.dancer_id = dancer_id
        self.port_num = port_num
        self.ip_addr = ip_addr
        self.group_id = group_id
        self.secret_key = secret_key

        self.send_start_flag = True
        self.counter = 0

        self.start_time_sync = True
        self.start_evaluation = False
        self.lock = threading.Lock()

    '''
    Create a "Double-Hop" SSH Tunnel for Dancer's Laptops to Reach Ultra96 Server

    | LOCAL CLIENT | <====Firewall====> | REMOTE SERVER | <==local==> | PRIVATE SERVER |
    |    LAPTOP    | <==SSH==Port 22==> |  NUS Sunfire  | <===SSH===> |    Ultra 96    |
    '''

    def start_ssh_tunnel(self, tunnel_two_port):
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
            remote_bind_address=('127.0.0.1', tunnel_two_port), # Local bind port for Sunfire (8000)
            ssh_username=TUNNEL_TWO_SSH_USERNAME,
            ssh_password=TUNNEL_TWO_SSH_PASSWORD,
            local_bind_address=('127.0.0.1',self.port_num) # Local bind port on Laptop [8001,8002,8003]
        )
        tunnel_two.start()
        print('Connection to tunnel_two (137.132.86.225:8000) OK...')

    '''
    Body methods to ensure proper synchronization and procedure
    '''
    def wait_for_start(self):
        # Wait for start command to be sent from Ultra96 Server
        while not self.start_evaluation:
            try:
                data = self.socket.recv(1024)
                start_flag = self.decrypt_message(data)
                if 'S' in start_flag:
                    print('Start flag received!')
                    self.start_evaluation = True
            except socket.timeout:
                print('Still waiting for one of the dancers T.T !!!')

    def run(self, tunnel_two_port):
        self.start_ssh_tunnel(tunnel_two_port)
        server_address = (self.ip_addr, self.port_num) # Start on local socket [8001,8002,8003]
        print('Trying to connect to %s port %s' % server_address)
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect(server_address)
            print("Successfully connected to the Ultra96 server")

        except Exception:
            print('An error has occured when trying to connect to Ultra96 Server.')

        self.start_ssh_tunnel(self.port_num + 4)
        alert_address = (self.ip_addr, self.port_num + 4) # Start on local socket [8005,8006,8007]
        print('Trying to connect to %s port %s' % alert_address)
        try:
            self.alert_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.alert_socket.connect(alert_address)
            print(f'Successfully connected alert channel on port {self.port_num + 4}')
        except Exception:
            print('An error has occured when trying to connect to Ultra96 Server.')

        # Create a seperate thread to handle this socket for alerts
        self.alerts_thread = threading.Thread(target=self.receive_alerts)
        self.alerts_thread.daemon = True
        self.alerts_thread.start()

    '''
    Function that listens constantly to eval server to receive alerts
    '''
    def receive_alerts(self):
        while True:
            try:
                data = self.alert_socket.recv(1024)
                if data:    
                    #alert_msg = data.decode(FORMAT)
                    print(' ')
                    print(' ____   _____   ___   ____    ____      _     _   _   ____  ___  _   _   ____   _ ')
                    print('/ ___| |_   _| / _ \ |  _ \  |  _ \    / \   | \ | | / ___||_ _|| \ | | / ___| | |')
                    print('\___ \   | |  | | | || |_) | | | | |  / _ \  |  \| || |     | | |  \| || |  _  | |')
                    print(' ___) |  | |  | |_| ||  __/  | |_| | / ___ \ | |\  || |___  | | | |\  || |_| | |_|')
                    print('|____/   |_|   \___/ |_|     |____/ /_/   \_\|_| \_| \____||___||_| \_| \____| (_)')
                    print(' ')
            except socket.timeout or BlockingIOError:
                pass

    '''
    Methods for Encryption and Decryption
    '''
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
        encrypted_message = encrypted_message.ljust(256, b' ')
        return encrypted_message

    def decrypt_message(self, cipher_text):
        decoded_message = base64.b64decode(cipher_text)
        iv = decoded_message[:16]
        secret_key = bytes(str(self.secret_key), encoding=FORMAT)

        cipher = AES.new(secret_key, AES.MODE_CBC, iv)

        decrypted_message = cipher.decrypt(decoded_message[16:]).strip()
        decrypted_message = decrypted_message.decode(FORMAT)

        decrypted_message = decrypted_message[decrypted_message.find('#'):]
        decrypted_message = bytes(decrypted_message[1:], 'utf8').decode('utf8')

        return decrypted_message

    '''
    Retrieve message from Bluno and Send to Ultra96 Server
    '''
    def manage_bluno_data(self):
        # Don't send anything until all dancer ready flag is set
        while self.start_evaluation:

            # Simluate Sending T packet to initialize Time Sync Protocol
            if self.start_time_sync:
                self.sync_clock()
                self.start_time_sync = False
                time.sleep(3)
                print('Waiting 3s for all dancers to run Time Sync Protocol!')

            # Simulate retrieve and send data to Ultra96 Server
            timestamp = time.time()
            random_data = ['|7639|-2580|-9132|206|4429|-205|',
            '|7553|-2567|-9092|216|4532|-237|',
            '|7643|-2534|-9042|234|4302|-192|',
            '|7549|-2530|-9112|240|4443|-222|',
            '|7639|-2582|-9042|224|4345|-212|']
            print(f'Data Packet Number : {self.counter}')

            emg_data1 = '#E|1|777|777'
            emg_data2 = '#E|1|888|888'

            if self.send_start_flag:
                print(f'Sending Start of dance flag for Dancer {self.dancer_id}')
                raw_data = '#' + 'D' + '|' + str(self.dancer_id).strip() + random.choice(random_data) + 'S|' + str(timestamp)
            else:
                raw_data = '#' + 'D' + '|' + str(self.dancer_id).strip() + random.choice(random_data) + 'N|' + str(timestamp)

            if self.counter % 20 == 0:
                self.send_data(emg_data1)
            elif self.counter % 30 == 0:
                self.send_data(emg_data2)

            self.send_data(raw_data)
            if self.counter % 100 == 0 and self.counter != 0:
                time.sleep(30)
                self.send_start_flag = True

            else:
                self.send_start_flag = False
            self.counter = self.counter + 1
            print(f'Sending Raw Data to Ultra96 Server : {raw_data}')
            time.sleep(0.1)

    def send_data(self, data):
        encrypted_message = self.encrypt_message(data)
        self.socket.sendall(encrypted_message)

    '''
    Functions to call to initiate Time Sync Protocol that calculates RRT and Offset
    '''
    def sync_clock(self):
        self.RTT = 0.0
        self.offset = 0.0
        timestamp_data = '#T|' + str(self.dancer_id).strip() + '|'
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
        timestamp_data = '#O|' + str(self.dancer_id).strip() + '|' + str(self.offset).strip() + '|'
        self.send_data(timestamp_data)

    def receive_timestamp(self):
        data = self.socket.recv(1024)
        if data:
            try:
                timestamp = self.decrypt_message(data)
                return timestamp
            except Exception:
                print('Did not receive return timestamp packet from Ultra96 Server!')

    '''
    Get time from NTP Server and calculate offset with system(laptop) clock

    def ntp_time_sync(self):
        try:
            ntp_client = ntplib.NTPClient()
            response = ntp_client.request('pool.ntp.org')
            print(responsed.tx_time)
        except Exception as e:
            return None
    '''

    def stop(self):
        self.socket.close()

def main(dancer_id, tunnel_two_port):
    # if len(sys.argv) != 2:
    #     print('Invalid number of arguments')
    #     print('python Laptop_client.py [dancer_id]')
    #     sys.exit()

    dancer_id = int(dancer_id)
    ip_addr = '127.0.0.1'
    port_num = PORT_NUMS[dancer_id-1]
    group_id = GROUP_ID
    secret_key = SECRET_KEY

    my_client = Client(dancer_id, ip_addr, port_num, group_id, secret_key)
    my_client.run(tunnel_two_port)

    my_client.wait_for_start()
    #my_client.manage_bluno_data()

    return my_client
