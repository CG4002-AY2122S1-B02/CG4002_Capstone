import argparse
import sys
import socket
import threading
import time
import base64
import random
from multiprocessing import Process,Queue,Pipe
from queue import Queue
import globals as globals
import test_queue_consumer as consumer

class Ultra96_Server(threading.Thread):
    def __init__(self):
        super(Ultra96_Server, self).__init__()
        # Data Structures to store raw data from dancers

if __name__ == '__main__':
    test_server = Ultra96_Server()
    globals.initialize()
    threading.Thread(target=consumer.consumer(), daemon=True).start()
    count = 0
    while not globals.test_queue.full():
        globals.test_queue.put(count)
        print(f"producer put in {count}")
        count += 1
        time.sleep(1)
    print("已经加完啦")
    globals.test_queue.join()
    print("所有工作都完成啦")
