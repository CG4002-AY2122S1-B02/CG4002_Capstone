# Test Script to send data (one-way communication) from Ultra96 FPGA to Database Server
# Implementation using Python Socket API

import sys
import socket
import time

class Client():
    def __init__(self, ip_addr, port_num, group_id):
        super(Client, self).__init__()

        # Create a TCP/IP socket and connect to database server
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_address = (ip_addr, port_num)
        self.group_id = group_id

        print('trying to connect to %s port %s' % server_address)
        self.socket.connect(server_address)
        print("Successfully connected to the database server")

    def send_data(self, raw_message):
        raw_message = raw_message.encode("utf8")
        print(f"Sending data to Evaluation Server", raw_message)
        self.socket.sendall(raw_message)

    def stop(self):
        self.connection.close()
        self.shutdown.set()
        self.timer.cancel()

def main():
    if len(sys.argv) != 4:
        print('Invalid number of arguments')
        print('python eval_client.py [IP address] [Port] [groupID]')
        sys.exit()

    ip_addr = sys.argv[1]
    port_num = int(sys.argv[2])
    group_id = sys.argv[3]

    my_client = Client(ip_addr, port_num, group_id)
    action = ""

    count = 0
    while action != "logout":
        # Send the Database Server the received data from the 3 laptops
        my_client.send_data("# 1 2 3 | dab | 1.00")
        time.sleep(2)
        count += 1
        if (count == 30):
            my_client.stop()

if __name__ == '__main__':
    main()
