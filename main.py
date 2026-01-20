# main.py
from micropython import const
from machine import Pin
import network
import os
import machine
import gc
import time
import _thread
import urequests
import ntptime

# ================= CONFIG =================
SHELL_VARS = {}
OPEN_WEATHER_MAP_API = ""
SPINNER = ["-", "/", "|", "\\"]
PLUGINS = {}



led = Pin(2, Pin.OUT)
led.value(0)
wlan = network.WLAN(network.STA_IF)
boot_time = time.ticks_ms()




# ================= MicroPython =====================

def cmd_run(args):
    if len(args) < 2:
        print("Usage: run <script.py>")
        return

    filename = args[1]
    try:
        with open(filename, "r") as f:
            code = f.read()
        print(f"Running {filename}...\n")
        exec(code, globals(), globals())
        print(f"\nFinished {filename}")
    except Exception as e:
        print("Error:", e)



# ================= Plugins / PKG ===================

PKG_REPO = "https://raw.githubusercontent.com/Gubir34/esp-os-packages/main/"

PLUGINS = {}
INSTALLING = set()

def parse_dependencies(code):
    deps = []
    for line in code.splitlines()[:5]:
        line = line.strip()
        if line.startswith("# depends:"):
            deps = line.replace("# depends:", "").strip().split()
            break
    return deps


def pkg_exists(name):
    try:
        return name + ".espos" in os.listdir("pkg")
    except:
        return False


def resolve_dependencies(code):
    deps = parse_dependencies(code)
    for dep in deps:
        if not pkg_exists(dep):
            print("[pkg] installing dependency:", dep)
            pkg_install_from_repo(dep)


def pkg_install_from_repo(name):
    url = PKG_REPO + name + ".py"
    print("[pkg] downloading:", url)

    try:
        r = urequests.get(url)

        if r.status_code != 200:
            print("[pkg] download failed:", r.status_code)
            r.close()
            return

        code = r.text
        r.close()

        with open("pkg/" + name + ".py", "w") as f:
            f.write(code)

        print("[pkg] installed:", name)
        load_plugins()

    except Exception as e:
        print("[pkg] install error:", e)



def load_plugins():
    PLUGINS.clear()
    try:
        for f in os.listdir("pkg"):
            if f.endswith(".espos"):
                name = f[:-6]
                with open("pkg/" + f, "r") as fp:
                    PLUGINS[name] = fp.read()
                print("[pkg] loaded:", name)
    except Exception as e:
        print("[pkg] load error:", e)


def run_plugin(name, args, printer=print):
    if name not in PLUGINS:
        printer("No such plugin:", name)
        return

    try:
        env = {}

        # tüm pluginleri aynı namespace'e yükle
        for p in PLUGINS:
            exec(PLUGINS[p], {}, env)

        if "main" in env:
            env["main"](args, printer)
        else:
            printer("Plugin has no main(args, printer)")

    except Exception as e:
        printer("Plugin error:", e)


# ---------- shell entegrasyonu ----------
def shell_pkg_command(c, a):
    if c == "pkg" and a:
        if a[0] == "install" and len(a) > 1:
            pkg_install_from_repo(a[1])
            return True

        elif a[0] == "list":
            for f in os.listdir("pkg"):
                if f.endswith(".espos"):
                    print("-", f[:-6])
            return True

        elif a[0] == "remove" and len(a) > 1:
            try:
                os.remove("pkg/" + a[1] + ".espos")
                print("[pkg] removed:", a[1])
                load_plugins()
            except Exception as e:
                print("[pkg] remove error:", e)
            return True

    return False

# ================= Utilities =================

def autorun_shell():
    try:
        import os
        if "autorun.shell" in os.listdir():
            print("[autorun] autorun.shell running...")
            run_shell_script("autorun.shell")
    except:
        pass


def run_shell_script(filename, printer=print):
    import time

    try:
        with open(filename, "r") as f:
            lines = [line.rstrip() for line in f.readlines()]
    except Exception as e:
        printer("Shell open error:", e)
        return

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if not line or line.startswith("#"):
            i += 1
            continue

        # ---------- sleep ----------
        if line.startswith("sleep"):
            try:
                time.sleep(float(line.split()[1]))
            except:
                printer("sleep syntax error")
            i += 1
            continue

        # ---------- variable ----------
        if "=" in line and not line.startswith(("if", "elif", "while")):
            var, val = [x.strip() for x in line.split("=", 1)]
            try:
                val = int(val)
            except:
                pass
            SHELL_VARS[var] = val
            i += 1
            continue

        # ---------- WHILE ----------
        if line.startswith("while"):
            cond = line.replace("while", "").strip()
            var, val = [x.strip() for x in cond.split("==")]
            try:
                val = int(val)
            except:
                pass

            block = []
            i += 1
            while lines[i] != "}":
                block.append(lines[i].strip())
                i += 1

            while SHELL_VARS.get(var) == val:
                for cmd in block:
                    shell_exec(cmd, printer)

            i += 1
            continue

        # ---------- IF / ELIF / ELSE ----------
        if line.startswith("if"):
            executed = False

            while True:
                if line.startswith(("if", "elif")):
                    cond = line.split(None, 1)[1]
                    var, val = [x.strip() for x in cond.split("==")]
                    try:
                        val = int(val)
                    except:
                        pass
                    ok = SHELL_VARS.get(var) == val
                else:
                    ok = True  # else

                block = []
                i += 1
                while lines[i] != "}":
                    block.append(lines[i].strip())
                    i += 1

                if ok and not executed:
                    for cmd in block:
                        shell_exec(cmd, printer)
                    executed = True

                i += 1
                if i >= len(lines) or not lines[i].startswith(("elif", "else")):
                    break
                line = lines[i].strip()

            continue

        # ---------- NORMAL ----------
        shell_exec(line, printer)
        i += 1


def gpio(pin, val):
    try:
        p = Pin(int(pin), Pin.OUT)
        p.value(int(val))
        print(f"GPIO {pin} = {val}")
    except Exception as e:
        print("GPIO error:", e)



def pwm(pin, freq, duty):
    try:
        p = Pin(int(pin), Pin.OUT)
        pwm_obj = machine.PWM(p)
        pwm_obj.freq(int(freq))
        pwm_obj.duty_u16(int(duty))
        print(f"PWM on pin {pin} freq={freq}Hz duty={duty}")
    except Exception as e:
        print("PWM error:", e)


def spinner_loader(turns=3, delay=0.15):
    for _ in range(turns):
        for s in SPINNER:
            print("\r" + s, end="")
            time.sleep(delay)
    print("\r ", end="")

def clean_ram():
    gc.collect()
    


def reboot():
    machine.reset()

def blink(times, delay=0.3):
    for _ in range(times):
        led.value(1)
        time.sleep(delay)
        led.value(0)
        time.sleep(delay)

# ================= CPU Frequency =================
def freq_save(freq):
    with open("freq.txt", "w") as f:
        f.write(str(freq))

def freq_load():
    try:
        with open("freq.txt", "r") as f:
            freq = int(f.read())
            machine.freq(freq)
    except Exception:
        pass

def freq_change(mhz):
    table = {80: 80_000_000, 160: 160_000_000, 240: 240_000_000}
    if mhz in table:
        machine.freq(table[mhz])
        freq_save(table[mhz])
        print("CPU set to", mhz, "MHz")
    else:
        print("Use: 80 / 160 / 240")

# ================= File Operations =================

def mv(src, dest):
    try:
        os.rename(src, dest)
        print(f"{src} moved to {dest}")
    except Exception as e:
        print("Move error:", e)
        
def cp(src, dest):
    try:
        with open(src, "r") as fsrc, open(dest, "w") as fdest:
            fdest.write(fsrc.read())
        print(f"{src} copied to {dest}")
    except Exception as e:
        print("Copy error:", e)


def mkdir(path):
    try:
        os.mkdir(path)
        print(f"Directory '{path}' created")
    except Exception as e:
        print("mkdir error:", e)

def rmdir(path):
    try:
        os.rmdir(path)
        print(f"Directory '{path}' removed")
    except Exception as e:
        print("rmdir error:", e)


def create_file(filename):
    try:
        with open(filename, "w", encoding="utf-8") as f: f.write("")
        print(f"File '{filename}' created")
    except Exception as e: print("Error:", e)

def write_file(filename, content):
    try:
        with open(filename, "w", encoding="utf-8") as f: f.write(content)
        print(f"Written to '{filename}': {content}")
    except Exception as e: print("Error:", e)

def append_file(filename, content):
    try:
        with open(filename, "a", encoding="utf-8") as f: f.write(content)
        print(f"Appended to '{filename}': {content}")
    except Exception as e: print("Error:", e)

def read_file(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f: print(f.read())
    except Exception as e: print("Error:", e)

def delete_file(filename):
    try:
        os.remove(filename)
        print(f"File '{filename}' deleted")
    except Exception as e: print("Error:", e)

def flash_info():
    stats = os.statvfs("/")
    block_size = stats[0]
    total_blocks = stats[2]
    free_blocks = stats[3]
    print("Total flash:", block_size*total_blocks, "bytes")
    print("Free flash:", block_size*free_blocks, "bytes")

# ================= File System =================
def ls(): print(os.listdir())
def pwd(): print(os.getcwd())
def cd(path): os.chdir(path)

# ================= WiFi =================
def wifi_on(): wlan.active(True)
def wifi_off(): wlan.active(False)

import usocket as socket

def ping(host):
    try:
        addr = socket.getaddrinfo(host, 80)[0][-1][0]
        print(f"Pinging {host} [{addr}] ...")
        s = socket.socket()
        s.connect((addr, 80))
        print("Ping success")
        s.close()
    except Exception as e:
        print("Ping error:", e)

def ip():
    if wlan.isconnected():
        print("IP:", wlan.ifconfig()[0])
    else:
        print("WiFi not connected")

def download(url, filename):
    try:
        r = urequests.get(url)
        with open(filename, "w") as f:
            f.write(r.text)
        r.close()
        print(f"Downloaded {url} -> {filename}")
    except Exception as e:
        print("Download error:", e)


def wifi_connect(ssid, password):
    wlan.active(True)
    wlan.connect(ssid, password)

    for _ in range(10):
        if wlan.isconnected():
            print("\nConnected:", wlan.ifconfig())
            save_wifi_credentials(ssid, password)
            return
        print(".", end="")
        time.sleep(1)

    print("\nConnection failed")


def save_wifi_credentials(ssid, password):
    try:
        with open("wifi.txt", "w") as f: f.write(f"{ssid}\n{password}")
    except: pass


def wifi_autoconnect(printer=print, timeout=10):
    import time

    try:
        with open("wifi.txt", "r") as f:
            ssid, password = f.read().splitlines()
    except:
        printer("[wifi] no saved wifi")
        return False

    wlan.active(True)
    wlan.connect(ssid, password)

    printer("[wifi] connecting to", ssid)

    for _ in range(timeout):
        if wlan.isconnected():
            printer("[wifi] connected:", wlan.ifconfig())
            return True
        time.sleep(1)

    printer("[wifi] autoconnect failed")
    return False


def load_wifi_credentials():
    try:
        with open("wifi.txt", "r") as f:
            ssid, password = f.read().splitlines()
            wlan.active(True)
            wlan.connect(ssid, password)
            print("Connecting saved WiFi...")
    except: pass
    
def http_time_sync(printer=print):
    import urequests
    import machine

    URL = "http://worldtimeapi.org/api/timezone/Europe/Istanbul.txt"

    try:
        r = urequests.get(URL)
        txt = r.text
        r.close()

        for line in txt.split("\n"):
            if line.startswith("datetime:"):
                dt = line.split(" ", 1)[1]
                date, time_ = dt.split("T")

                y, m, d = map(int, date.split("-"))
                h, mi, s = map(int, time_.split(":")[0:3])

                rtc = machine.RTC()
                rtc.datetime((y, m, d, 0, h, mi, s, 0))

                printer("[time] HTTP time sync OK")
                return True

        printer("[time] datetime not found")
        return False

    except Exception as e:
        printer("[time] HTTP sync error:", e)
        return False


# ================= Games ===================

import urandom

def number_game():
    target = urandom.getrandbits(7) % 100 + 1
    print("Guess the number between 1 and 100")
    while True:
        guess = input("Your guess: ")
        try:
            g = int(guess)
            if g < target:
                print("Higher")
            elif g > target:
                print("Lower")
            else:
                print("Correct! You guessed it!")
                break
        except:
            print("Enter a number")


# ================= Weather =================
def get_weather(city):
    if not wlan.isconnected():
        print("WiFi not connected")
        return
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city},TR&appid={OPEN_WEATHER_MAP_API}&units=metric&lang=en"
    try:
        r = urequests.get(url)
        data = r.json()
        r.close()
        if "main" not in data: print("Weather API error"); return
        print(f"City: {city}\nTemp: {data['main']['temp']} °C\nWeather: {data['weather'][0]['description']}\nHumidity: {data['main']['humidity']}%")
    except Exception as e: print("Weather error:", e)

# ================= Shell =================
def shell_exec(cmd, printer=print):
    parts = cmd.split()
    if not parts: return
    c, args = parts[0], parts[1:]
    try:     
        if shell_pkg_command(c, args):
            return
        
        elif c == "help":
            printer("""
        Commands:
        freq                   - show CPU frequency
        freq set 80|160|240    - set CPU frequency
        wifi on                - enable WiFi
        wifi off               - disable WiFi
        wifi connect <ssid> <pass>  - connect to WiFi
        weather <city>         - get weather
        blink <n> [delay]      - blink LED n times, optional delay
        ram                    - show free RAM
        reboot                 - reboot ESP32
        exit                   - exit shell
        flash                  - show total/free flash
        uptime                 - show how long ESP32 has been running
        ip                     - show WiFi IP
        ping <host>            - ping host/domain
        download <url> <file>  - download file from URL
        number_game            - play number guessing game

        GPIO & PWM:
        gpio <pin> <0|1>       - set GPIO pin output
        pwm <pin> <freq> <duty> - PWM on pin
        
        Packages:
        pkg list       - list installed packages
        pkg available  - list available packages
        pkg install X  - install package X
        pkg remove X   - remove package X
        pkg reload     - reload packages without reboot


        File commands:
        create <filename>      - create empty file
        write <filename> <content>    - overwrite file
        append <filename> <content>   - append content
        read <filename>        - read file
        delete <filename>      - delete file
        mv <src> <dest>        - move file
        cp <src> <dest>        - copy file
        ls                     - list files
        cd <dir>               - change directory
        pwd                    - show current directory
        mkdir <dir>            - make directory
        rmdir <dir>            - remove directory
        
        time                 - show RTC time
        time-sync            - sync time over HTTP

        """)
        
        elif c == "ls": ls()
        
        elif c == "cd" and args: cd(args[0])
        
        elif c == "pwd": pwd()
        
        elif c == "freq":
            if not args: printer(machine.freq(), "Hz")
            elif args[0] == "set" and len(args)>1: freq_change(int(args[1]))
        
        
        elif c == "gpio" and len(args)==2: gpio(args[0], args[1])
        
        elif c == "run": cmd_run([c] + args)

        
        elif c == "pwm" and len(args)==3: pwm(args[0], args[1], args[2])
        
        elif c == "mv" and len(args)==2: mv(args[0], args[1])
        
        elif c == "cp" and len(args)==2: cp(args[0], args[1])
        
        elif c == "mkdir" and args: mkdir(args[0])
        
        elif c == "rmdir" and args: rmdir(args[0])
        
        elif c == "ping" and args: ping(args[0])
        
        elif c == "ip": ip()
        
        elif c == "download" and len(args)==2: download(args[0], args[1])
        
        elif c == "number_game": number_game()
        
        elif c == "time":
            rtc = machine.RTC()
            printer("RTC:", rtc.datetime())

        elif c == "time-sync":
            http_time_sync(printer)

        
        elif c == "uptime":
            uptime_seconds = time.ticks_ms() // 1000  # başlatıldığı andan beri geçen saniye
            hours = uptime_seconds // 3600
            minutes = (uptime_seconds % 3600) // 60
            seconds = uptime_seconds % 60
            printer("Uptime: {}h {}m {}s".format(hours, minutes, seconds))

        elif c == "wifi":
            if args[0]=="on": wifi_on()
            elif args[0]=="off": wifi_off()
            elif args[0]=="connect" and len(args)>=2: wifi_connect(args[1], args[2])
        
        elif c == "weather" and args: get_weather(args[0])
        
        elif c == "blink":
            if len(args)==2: blink(int(args[0]), float(args[1]))
            elif len(args)==1: blink(int(args[0]))
        
        elif c == "ram": clean_ram(); printer("Free RAM:", gc.mem_free())
        
        elif c == "create" and args: create_file(args[0])
        
        elif c == "write" and len(args)>=2: write_file(args[0], " ".join(args[1:]))
        
        elif c == "append" and len(args)>=2: append_file(args[0], " ".join(args[1:]))
        
        elif c == "read" and args: read_file(args[0])
        
        elif c == "delete" and args: delete_file(args[0])
        
        elif c == "reboot": reboot()
        
        elif c == "flash": flash_info()
        
        elif c == "exit": printer("Bye 👋"); return "exit"
        
        elif c in PLUGINS:
            run_plugin(c, args, printer)
            
        elif c.startswith("./") and c.endswith(".shell"):
            run_shell_script(c[2:], printer)
        
        else: printer("Unknown command")
        
    except Exception as e: printer("Error:", e)



def shell():
    print("ESP32 Shell ready. Type 'help'")
    while True:
        cmd = input("esp@esp32 > ").strip()
        if not cmd: continue
        result = shell_exec(cmd)
        if result=="exit": break

# ================= Boot main =================

if "pkg" not in os.listdir():
    os.mkdir("pkg")
    
    
freq_load()
load_plugins()
wifi_autoconnect()

print("Init Successful")
print("CPU frequency:", machine.freq(), "Hz")

_thread.start_new_thread(spinner_loader, ())
blink(3,0.4)
print()

shell()
autorun_shell()


