# boot.py
import machine
import gc
import time
import _thread
import ntptime
import time

def load_wifi_credentials():
    try:
        with open("wifi.txt", "r") as f:
            ssid, password = f.read().splitlines()
            wlan.active(True)
            wlan.connect(ssid, password)
            print("Connecting saved WiFi...")
    except: pass
    
def freq_load():
    try:
        with open("freq.txt", "r") as f:
            freq = int(f.read())
            machine.freq(freq)
    except Exception:
        pass

def spinner_loader(turns=3, delay=0.15):
    for _ in range(turns):
        for s in SPINNER:
            print("\r" + s, end="")
            time.sleep(delay)
    print("\r ", end="")
    

def blink(times, delay=0.3):
    for _ in range(times):
        led.value(1)
        time.sleep(delay)
        led.value(0)
        time.sleep(delay)



ntptime.settime()
print("Time synced:", time.localtime())


# Kaydedilmiş WiFi varsa bağlan
load_wifi_credentials()

