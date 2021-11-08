import time
import tflite_runtime.interpreter as tflite
import numpy as np
import pandas as pd
from math import exp
from pickle import load

def math_loser(input_data, model_path, scaler_path):
    interpreter = tflite.Interpreter(model_path= model_path)
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    # check the type of the input tensor
    floating_model = input_details[0]['dtype'] == np.float32
    
    #rescale
    scaler = load(open(scaler_path, 'rb'))
    input_data = scaler.transform(input_data)
    # train_max = np.array([13811.398022174102, 12787.0, 13248.064922600952, 31375.91863600317, 31282.245750364258, 30620.470452529367])
    # train_min = np.array([-19497.0, -13754.671778742177, -13921.091173480494, -31337.872619438287, -31240.316963619214, -31082.2])
    # input_data_std = (input_data - train_min) / (train_max - train_min)
    # #X_scaled = X_std * (max - min) + min
    # input_data = input_data_std * 1
    # input_data = input_data.astype('float32')

    # NxHxWxC, H:1, W:2
    height = input_details[0]['shape'][1]
    width = input_details[0]['shape'][2]
    print(f"shape of the input required by model is {height}, {width}")
    input_data = np.reshape(input_data, (-1, height, width))
    print(f"shape of the input we passed in is {input_data.shape}")

    interpreter.set_tensor(input_details[0]['index'], input_data)

    start_time = time.time()
    interpreter.invoke()
    stop_time = time.time()

    output_data = interpreter.get_tensor(output_details[0]['index'])
    print(f"initial prediction is {output_data}")
    
    results = np.squeeze(output_data)
    print(f"After squeeze it becomes {results}")
    sum_probability = exp(results[0]) + exp(results[1]) + exp(results[2]) + exp(results[3]) + exp(results[4])  + exp(results[5]) + exp(results[6]) + exp(results[7]) + exp(results[8]) 
    p1 = exp(results[0]) / sum_probability
    p2 = exp(results[1]) / sum_probability
    p3 = exp(results[2]) / sum_probability
    p4 = exp(results[3]) / sum_probability
    p5 = exp(results[4]) / sum_probability
    p6 = exp(results[5]) / sum_probability
    p7 = exp(results[6]) / sum_probability
    p8 = exp(results[7]) / sum_probability
    p9 = exp(results[8]) / sum_probability
    prob_list = [p1,p2,p3,p4,p5,p6,p7,p8,p9]
    
    pred = np.argmax(results)
    print(f"After argmax it becomes {pred}")

    print('time used: {:.3f}ms'.format((stop_time - start_time) * 1000))
    return pred, prob_list

if __name__ == '__main__':
    with open('test_single_y.txt', 'r') as f:
        _y = f.readline().strip()
    print(_y)
    _input_data = pd.read_csv("test_single_x.csv", index_col=False).to_numpy()
    _input_data = _input_data.astype('float32')
    print(f"shape of the input we passed in initially is {_input_data.shape}")
    print(f"type of the input we passed in is {_input_data.dtype}")
    pred = math_loser(_input_data, 'boing_cnn_tflite_80.tflite')
