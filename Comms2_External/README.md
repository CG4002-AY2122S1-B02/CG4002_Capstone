# External Comms

## Instruction
- `eval_client.py` runs on Ultra96 and sends data to evaluation server

## Access Ultra96
1. You need to SSH into sunfire
```
ssh -l <nusnet_id>@sunfire.comp.nus.edu.sg 
```
2. From Sunfire, you can access the board
```
ssh -l xilinx <IP address of your group's board>
2 makerslab-fpga-02 137.132.86.225
```

### Examples
- Access Ultra96 via SSH
```
ssh e0325893@sunfire.comp.nus.edu.sg
ssh -l xilinx@137.132.86.225
```
- Transfer files to Ultra96 via SSH
```
scp eval_server.py xilinx@137.132.86.225:~/
scp eval_server.py e0325893@sunfire.comp.nus.edu.sg:~/
```
- Running Jupyter Notebook environment on local (SSH Double Hop Port Forwarding)
1. On the Ultra96:
```
jupyter notebook --no-browser --port=XXXX
```
2. In sunfire:
```
ssh -N -f -L YYYY:localhost:XXXX xilinx@137.132.86.225
```
3. In localhost:
```
ssh -N -f -L ZZZZ:localhost:YYYY <user_id>@sunfire.comp.nus.edu.sg
```
- You can see the link for jupyter notebook opened in port XXXX on your Ultra96, copy and paste that link on your local machine browser and replace the port with ZZZZ (XXXX,YYYY,ZZZZ can be any port number)