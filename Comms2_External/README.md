# External Comms

## Instruction
- `Ultra96_db_server.py` runs on Ultra96 and will handle connections to Laptop, Eval Server and Dashboard

## Production/Testing Steps
1. Start the Evaluation Server Script
```
e.g. python3 eval_server.py <IP Address> <Port Number> <Group Number> 
```
2. Start the Ultra96_db_server.py Script with the following arguments
- -n <Int> | --num-of-dancers <Int>
- -E | --connect_to_eval_server
- -D | --connect_to_dashboard
- -C | --data_collection_mode
- -V | --verbose
```
e.g. python3 Ultra96_db_server.py -n 1 -E -D -C -V
```
3. Run the connection.py scripts on each of the dancers laptops
```
e.g. python3 connection.py -id 1 --fake-data
python3 connection.py -id 1
python3 connection.py -id 2
python3 connection.py -id 3
```
4. Create connections to database by running binary on remote dashboard laptop
```
./dashboard_server_macos
npm start
```

## Access Ultra96
1. You need to SSH into sunfire
```
ssh <nusnet_id>@sunfire.comp.nus.edu.sg 
```
2. From Sunfire, you can access the board
```
ssh xilinx@<IP address of your group's board>
Board Details: 2 makerslab-fpga-02 137.132.86.225
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