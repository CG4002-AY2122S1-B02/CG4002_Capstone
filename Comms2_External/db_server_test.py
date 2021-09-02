# Test Script to receive data (one-way communication) on Database Server from Ultra96 Server
# Implementation using Python Socket API

import sys
import socket
import threading

#ACTIONS = ['mermaid', 'jamesbond', 'dab', 'window360', 'cowboy', 'scarecrow', 'pushback', 'snake']
MESSAGE_SIZE = 3 # position, 1 action, sync 

class Server(threading.Thread):
    def __init__(self, ip_addr, port_num, group_id):
        super(Server, self).__init__()

        # Create a TCP/IP socket and bind to port
        self.shutdown = threading.Event()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_address = (ip_addr, port_num)

        print('starting up on %s port %s' % server_address)
        self.socket.bind(server_address)

        # Listen for incoming connections
        self.socket.listen(1)
        self.client_address, self.secret_key = self.setup_connection() 

    def setup_connection(self):

        # Immediately allow a connection
        # Wait for a connection
        print('waiting for a connection')
        self.connection, client_address = self.socket.accept()

        print('connection from', client_address)
        return client_address

    def run(self):
        while not self.shutdown.is_set():
            data = self.connection.recv(1024)

            if data:
                try:
                    message = data.decode("utf8")
                    print(f"Received {message} from client!")            

                except Exception as e:
                    print(e)
            else:
                print('no more data from', self.client_address)
                self.stop()

    def stop(self):
        self.connection.close()
        self.shutdown.set()
        self.timer.cancel()

def main():
    if len(sys.argv) != 4:
        print('Invalid number of arguments')
        print('python eval_server.py [IP address] [Port] [groupID]')
        sys.exit()

    ip_addr = sys.argv[1]
    port_num = int(sys.argv[2])
    group_id = sys.argv[3]

    my_server = Server(ip_addr, port_num, group_id)
    my_server.start()

if __name__ == '__main__':
    main()

