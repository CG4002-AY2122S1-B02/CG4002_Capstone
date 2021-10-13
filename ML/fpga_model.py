from pynq import allocate, Overlay, get_rails, DataRecorder
import numpy as np
import time
import pandas as pd

def cnn(input_arr):
    height = len(input_arr)
    width = len(input_arr[0])
    input_arr = np.reshape(input_arr, (height * width, 1))
    print(f"After flattern, the shape of input data is {input_arr.shape}")
    overlay = Overlay('/home/xilinx/fpga/design_1.bit')

    l0 = overlay.conv_layer_1_0 
    l1 = overlay.maxpool_layer_1_0
    l2 = overlay.conv_layer_2_0       
    l3 = overlay.maxpool_layer_2_0  
    l4 = overlay.conv_layer_3_0      
    l5 = overlay.maxpool_layer_3_0 
    l6 = overlay.dense_layer_0_0 
    l7 = overlay.dense_layer_2_0

    # Start IP Blocks
    l0.write(0x0, 1)
    l1.write(0x0, 1)
    l2.write(0x0, 1)
    l3.write(0x0, 1)
    l4.write(0x0, 1)
    l5.write(0x0, 1)
    l6.write(0x0, 1)
    l7.write(0x0, 1)

    dma = overlay.axi_dma_0

    inp_buffer = allocate(shape=(60 * 6,), dtype=np.single)
    out_buffer = allocate(shape=(3,), dtype=np.single)

    # Input layer
    for j in range(60 * 6):
        inp_buffer[j] = input_arr[j]


    dma.sendchannel.transfer(inp_buffer)
    dma.recvchannel.transfer(out_buffer)

    dma.sendchannel.wait()
    dma.recvchannel.wait()

    output = []
    for prob in out_buffer:
        output.append(prob)

    del inp_buffer, out_buffer

    # Stop IP Blocks
    l0.write(0x0, 0)
    l1.write(0x0, 0)
    l2.write(0x0, 0)
    l3.write(0x0, 0)
    l4.write(0x0, 0)
    l5.write(0x0, 0)
    l6.write(0x0, 0)
    l7.write(0x0, 0)

    return output

if __name__ == '__main__':
    print("=======FGPA CNN Model Test========")
    with open('test_single_y.txt', 'r') as f:
        _y = f.readline().strip()
    print(_y)
    _input_data = pd.read_csv("test_single_x.csv", index_col=False).to_numpy()
    _input_data = _input_data.astype('float32')
    print(f"shape of the input we passed in initially is {_input_data.shape}")
    print(f"type of the input we passed in is {_input_data.dtype}")
    # Send input as an array (flatten 60 * 6 to 360 * 1 - I think it is row major order)
    # input_arr = []
    # for i in range(360):
    #     input_arr.append(i)
        
    # Softmax needs to be applied later (I did not add it so that the software trained ML and hardware implementation has the same result, anyway just take argmax)
    print(cnn(_input_data))
