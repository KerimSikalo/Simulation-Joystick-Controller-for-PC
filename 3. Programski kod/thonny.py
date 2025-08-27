import network
import time
from machine import Pin, ADC
from umqtt.simple import MQTTClient

# WiFi i MQTT postavke
SSID = "Zhunky"
PASSWORD = "emre12345"
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
CLIENT_ID = "joystick-client"

# MQTT teme
MQTT_TOPIC_X = b"tema/x"
MQTT_TOPIC_Y = b"tema/y"
MQTT_TOPIC_LIJEVO = b"tema/lijevo"
MQTT_TOPIC_DESNO = b"tema/desno"
MQTT_TOPIC_SIRENA = b"tema/sirena"
MQTT_TOPIC_BRISAC = b"tema/brisac"

# Inicijalizacija analognih pinova za joystick
x_axis = ADC(Pin(28))
y_axis = ADC(Pin(27))

# Inicijalizacija digitalnih pinova za tastere (pull-up otpor)
button_lijevo = Pin(0, Pin.IN, Pin.PULL_UP)    # GP0 - zmigavac lijevo
button_desno = Pin(1, Pin.IN, Pin.PULL_UP)     # GP1 - zmigavac desno
button_sirena = Pin(2, Pin.IN, Pin.PULL_UP)    # GP2 - sirena
button_brisac = Pin(3, Pin.IN, Pin.PULL_UP)    # GP3 - brisač

# Varijable za praćenje stanja tastera
last_button_state = {
    "lijevo": 1,    # 1 = nije pritisnut (pull-up)
    "desno": 1,
    "sirena": 1,
    "brisac": 1
}

# Varijable za toggle stanje (uključeno/isključeno)
toggle_state = {
    "lijevo": False,
    "desno": False,
    "sirena": False,
    "brisac": False
}

def do_connect():
    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        print("Povezivanje na WiFi mrežu...")
        sta_if.active(True)
        sta_if.connect(SSID, PASSWORD)
        while not sta_if.isconnected():
            time.sleep(0.5)
    print("Uspješno povezan:", sta_if.ifconfig())

def check_button_press(button, button_name, topic, client):
    """Provjeri je li taster pritisnut i pošalji MQTT poruku"""
    current_state = button.value()
    
    # Detektuj pritisak tastera (promjena sa 1 na 0 zbog pull-up)
    if last_button_state[button_name] == 1 and current_state == 0:
        # Taster je pritisnut - promijeni toggle stanje
        toggle_state[button_name] = not toggle_state[button_name]
        
        # Pošalji MQTT poruku
        message = "1" if toggle_state[button_name] else "0"
        client.publish(topic, message)
        
        status = "UKLJUČENO" if toggle_state[button_name] else "ISKLJUČENO"
        print(f"{button_name.upper()}: {status}")
        
        # Kratka pauza da se izbjegne bounce
        time.sleep(0.05)
    
    # Ažuriraj poslednje stanje
    last_button_state[button_name] = current_state

def main():
    do_connect()
    
    client = MQTTClient(CLIENT_ID, MQTT_BROKER, port=MQTT_PORT)
    client.connect()
    print("MQTT klijent povezan.")
    print("Joystick i tasteri aktivni...")
    
    while True:
        # Čitaj joystick osi
        x_val = x_axis.read_u16()
        y_val = y_axis.read_u16()
        
        # Pošalji joystick podatke
        client.publish(MQTT_TOPIC_X, str(x_val))
        client.publish(MQTT_TOPIC_Y, str(y_val))
        
        # Provjeri tastere
        check_button_press(button_lijevo, "lijevo", MQTT_TOPIC_LIJEVO, client)
        check_button_press(button_desno, "desno", MQTT_TOPIC_DESNO, client)
        check_button_press(button_sirena, "sirena", MQTT_TOPIC_SIRENA, client)
        check_button_press(button_brisac, "brisac", MQTT_TOPIC_BRISAC, client)
        
        print("Joystick - X:", x_val, "Y:", y_val)
        
        time.sleep(0.2)  # optimalno za MQTT i broker

if __name__ == "__main__":
    main()