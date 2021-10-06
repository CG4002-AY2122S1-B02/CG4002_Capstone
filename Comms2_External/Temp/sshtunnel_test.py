# Test script to try out the sshtunnel package

import paramiko
import sshtunnel
from paramiko import SSHClient

TUNNEL_ONE_SSH_ADDR = "sunfire.comp.nus.edu.sg"
TUNNEL_ONE_SSH_USERNAME = "e0325893"
TUNNEL_ONE_SSH_PASSWORD = "iLoveCapstoneB02"

TUNNEL_TWO_SSH_ADDR = "137.132.86.225"
TUNNEL_TWO_SSH_USERNAME = "xilinx"
TUNNEL_TWO_SSH_PASSWORD = "cg4002b02"

tunnel_one =  sshtunnel.open_tunnel(
    # Port 22 open for SSH
    (TUNNEL_ONE_SSH_ADDR,22), # Remote Server IP
    # ssh_pkey="/var/ssh/rsa_key",
    # ssh_private_key_password="secret",
    ssh_username=TUNNEL_ONE_SSH_USERNAME,
    ssh_password=TUNNEL_ONE_SSH_PASSWORD,
    remote_bind_address=(TUNNEL_TWO_SSH_ADDR,22), # Private Server IP
    # local_bind_address=("0.0.0.0",8001)
)

tunnel_one.start()
print("Connection to tunnel_one (sunfire:22) OK...")

tunnel_two = sshtunnel.open_tunnel(
    ssh_address_or_host=('127.0.0.1',tunnel_one.local_bind_port),
    remote_bind_address=('127.0.0.1',8001),
    ssh_username=TUNNEL_TWO_SSH_USERNAME,
    ssh_password=TUNNEL_TWO_SSH_PASSWORD,
    local_bind_address=('127.0.0.1',8001)
)

tunnel_two.start()
print("Connection to tunnel_two (137.132.86.225:8001) OK...")


