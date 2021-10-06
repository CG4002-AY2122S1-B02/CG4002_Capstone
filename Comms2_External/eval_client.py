# Evaluation Client script on Ultra96 to send data over to Evaluation Server

import sys
import socket
import base64
import time
import random
import threading

from Crypto.Cipher import AES
from Crypto import Random

BLOCK_SIZE = 16
PADDING = ' '

# Week 13 test: 8 moves, so 33 in total = (8*4) + 1 (logout)
#ACTIONS = ['mermaid', 'jamesbond', 'dab', 'window360', 'cowboy', 'scarecrow', 'pushback', 'snake']
# Week 9 and 11 tests: 3 moves, repeated 4 times each = 12 moves.

class Client(threading.Thread):
    def __init__(self, ip_addr, port_num, group_id, secret_key):
        super(Client, self).__init__()

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_address = (ip_addr, port_num)
        self.secret_key = secret_key
        self.shutdown = threading.Event()

    '''
    Methods for Encryption before sending evaluation server
    '''
    def add_padding(self, plain_text):
        # return plain_text + b"\0" + (AES.BLOCK_SIZE - len(plain_text) % AES.BLOCK_SIZE)
        pad = lambda s: s + (BLOCK_SIZE - (len(s) % BLOCK_SIZE)) * PADDING
        padded_plain_text = pad(plain_text)
        return padded_plain_text

    def encrypt_message(self, position, action, syncdelay):
        plain_text = '#' + position + '|' + action + '|' + syncdelay + '|'
        #print("Encrypting plain_text: ", plain_text)
        padded_plain_text = self.add_padding(plain_text)
        iv = Random.new().read(AES.block_size)
        aes_key = bytes(str(self.secret_key), encoding="utf8")
        cipher = AES.new(aes_key, AES.MODE_CBC, iv)
        encrypted_text = base64.b64encode(iv + cipher.encrypt(bytes(padded_plain_text, "utf8")))
        return encrypted_text

    '''
    Methods to Send and Receive Data to and from evaluation server
    '''
    def send_data(self, position, action, syncdelay):
        encrypted_text = self.encrypt_message(position, action, syncdelay)
        #print("Sending encrypted_text: ", encrypted_text)
        self.socket.sendall(encrypted_text)

    # This function will be on a Thread
    def receive_dancer_position(self):
        while not self.shutdown.is_set():
            dancer_position = self.socket.recv(1024)
            print('<==========New dancer positions==========>')
            dancer_position = dancer_position.decode("utf8")
            print(f"     [Dancer position]     ", dancer_position)
 
    '''
    Main Start and Stop functions
    '''
    def run(self):
        self.socket.connect(self.server_address)
        receive_thread = threading.Thread(target=self.receive_dancer_position)
        receive_thread.daemon = True
        receive_thread.start()
        print("Evaluation client is connected!")
 
    def stop(self):
        self.shutdown.set()
        self.socket.close()
        print('Ultra96 Client socket closed and disconnected.')


def main():
    if len(sys.argv) != 5:
        print('Invalid number of arguments')
        print('python eval_client.py [IP address] [Port] [groupID] [secret key]')
        sys.exit()

    ip_addr = sys.argv[1]
    port_num = int(sys.argv[2])
    group_id = sys.argv[3]
    secret_key = sys.argv[4]

    my_client = Client(ip_addr, port_num, group_id, secret_key)
    my_client.run()
    time.sleep(15)

    ACTIONS = ['mermaid', 'jamesbond', 'dab']
    POSITIONS = ['1 2 3', '3 2 1', '2 3 1', '3 1 2', '1 3 2', '2 1 3']
    SYNC_DELAYS = [1.23, 0.93, 1.33]

    count = 0
    while count < 19:
        # Send Data to Evaluation Server for Testing
        position = random.choice(POSITIONS) 
        action = random.choice(ACTIONS)
        offset = min(SYNC_DELAYS) 
        my_client.send_data(str(position), str(action), str(offset))

        # Receive Next Dancer positions from Evaluation Server
        count += 1
        time.sleep(3)

    my_client.stop()

if __name__ == '__main__':
    main()
