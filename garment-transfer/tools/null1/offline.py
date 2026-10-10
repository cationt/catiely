"""Guard installed before model imports. No downloads, proxies or external sockets."""
import ipaddress
import os
import sys


def loopback(host):
    if host in ("localhost", None):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def guard(event, args):
    if event in ("socket.connect", "socket.sendto", "socket.bind"):
        address = args[-1]
        if not isinstance(address, tuple) or not loopback(address[0]):
            raise RuntimeError("O_null1 offline guard: external socket blocked")
    if event == "socket.getaddrinfo" and not loopback(args[0]):
        raise RuntimeError("O_null1 offline guard: external DNS blocked")


def install():
    for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY", "DO_NOT_TRACK"):
        os.environ[key] = "1"
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    sys.addaudithook(guard)
