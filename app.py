import os
import time
import socket
import psutil
import requests
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

LAT = os.getenv("LAT")
LON = os.getenv("LON")
TIMEZONE = os.getenv("TZ", "UTC")

state = {"last_down": 0, "last_up": 0, "last_time": time.time()}

def get_io():
    net = psutil.net_io_counters(pernic=True)
    for iface in ("eth0", "wlan0", "en0", "enp0s3", "eth1"):
        if iface in net:
            return net[iface]
    return psutil.net_io_counters()

@app.get("/")
async def index():
    with open("index.html") as f:
        return HTMLResponse(f.read())

@app.get("/api/weather")
async def weather():
    global LAT, LON
    try:
        if not LAT or not LON:
            geo = requests.get("https://ipapi.co/json/", timeout=5).json()
            LAT, LON = geo["latitude"], geo["longitude"]

        loc = requests.get(
            f"https://nominatim.openstreetmap.org/reverse?format=json&lat={LAT}&lon={LON}",
            headers={"User-Agent": "Ether"},
            timeout=5,
        ).json()["address"]

        city = loc.get("city") or loc.get("town") or loc.get("village") or "Unknown"
        country = loc.get("country", "")

        weather = requests.get(
            f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&current_weather=true&timezone={TIMEZONE}",
            timeout=5,
        ).json()["current_weather"]

        return {
            "temp": weather["temperature"],
            "code": weather["weathercode"],
            "location": f"{city}, {country}",
        }
    except:
        return {"temp": 0, "code": 0, "location": "Location Error"}

@app.get("/api/stats")
async def stats():
    disk_path = "/host" if os.path.exists("/host") else "/"
    uptime = time.time() - psutil.boot_time()
    h, r = divmod(uptime, 3600)
    return {
        "cpu": psutil.cpu_percent(),
        "ram": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage(disk_path).percent,
        "uptime": f"{int(h)}h {int(r//60)}m",
        "total_down": get_io().bytes_recv,
        "total_up": get_io().bytes_sent,
    }

@app.get("/api/speed")
async def speed():
    net = get_io()
    now = time.time()
    elapsed = now - state["last_time"]

    down = (net.bytes_recv - state["last_down"]) / elapsed
    up = (net.bytes_sent - state["last_up"]) / elapsed

    state.update({"last_down": net.bytes_recv, "last_up": net.bytes_sent, "last_time": now})

    try:
        start = time.time()
        socket.create_connection(("8.8.8.8", 53), timeout=1)
        ping = int((time.time() - start) * 1000)
    except:
        ping = "--"

    return {"down": max(0, down), "up": max(0, up), "ping": ping}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)
