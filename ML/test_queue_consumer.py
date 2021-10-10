import globals as globals
import time 

def consumer():
    while not globals.test_queue.empty():
        try:
            temp = globals.test_queue.get()
            print(f"consumer take value {temp}")
            time.sleep(1)
        except:
            raise ValueError("Fetch failed")
        globals.test_queue.task_done()