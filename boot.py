import network

AP_SSID = "ps4css"
AP_PASS = "12345678"

ap = network.WLAN(network.AP_IF)
ap.active(True)

# PS4 必须：WPA2
ap.config(
    essid=AP_SSID,
    password=AP_PASS,
    authmode=network.AUTH_WPA_WPA2_PSK
)

# (IP, 子网, 网关, DNS)
# 网关和DNS都填ESP32自己，骗过PS4的联网检测
ap.ifconfig(("10.0.0.10", "255.255.255.0", "10.0.0.1", "10.0.0.1"))

print("AP ready:", ap.ifconfig())