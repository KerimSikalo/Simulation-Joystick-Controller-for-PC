import json
import threading
import time

import paho.mqtt.client as mqtt
import pyvjoy

# ----- Postavke za MQTT -----
MQTT_BROKER = "broker.hivemq.com"   # Broker
MQTT_PORT = 1883                    # 8883 je za TLS, ali obično 1883
MQTT_TOPIC_X = "tema/x"             # Tema za X osu
MQTT_TOPIC_Y = "tema/y"             # Tema za Y osu
MQTT_TOPIC_LIJEVO = "tema/lijevo"   # Tema za lijevi žmigavac
MQTT_TOPIC_DESNO = "tema/desno"     # Tema za desni žmigavac
MQTT_TOPIC_SIRENA = "tema/sirena"   # Tema za sirenu
MQTT_TOPIC_BRISAC = "tema/brisac"   # Tema za brisač

# ----- Inicijalizacija vJoy uređaja -----
vj = pyvjoy.VJoyDevice(1)

MAX_AXIS_VALUE = 0x8000  # 32768 decimalno
CENTER_AXIS_VALUE = MAX_AXIS_VALUE // 2  # 16384 - srednja vrijednost

# Deadzone postavke (10% oko srednje vrijednosti)
DEADZONE_PERCENT = 0.10
INPUT_MIN = 0
INPUT_MAX = 65535
INPUT_CENTER = INPUT_MAX // 2  # 32767.5 -> 32767


# ----- Funkcija za skaliranje podataka (0..65535) u vJoy raspon (0..32768) sa deadzone -----
def scale_input_to_vjoy_axis(input_value: int, input_min: int = 0, input_max: int = 65535) -> int:
    """
    Pretvori int vrijednost iz raspona [0..65535] u int raspon [0..32768].
    Uključuje deadzone od 10% oko srednje vrijednosti.
    
    Args:
        input_value: Vrijednost od 0 do 65535
        input_min: Minimalna ulazna vrijednost (0)
        input_max: Maksimalna ulazna vrijednost (65535)
    
    Returns:
        Skalirana vrijednost za vJoy (0-32768) ili None ako je u deadzone
    """
    # Ograniči ulaznu vrijednost na valjan raspon
    if input_value < input_min:
        input_value = input_min
    if input_value > input_max:
        input_value = input_max
    
    # Izračunaj deadzone granice
    deadzone_range = (input_max - input_min) * DEADZONE_PERCENT / 2
    deadzone_min = INPUT_CENTER - deadzone_range
    deadzone_max = INPUT_CENTER + deadzone_range
    
    # Provjeri je li vrijednost u deadzone
    if deadzone_min <= input_value <= deadzone_max:
        return CENTER_AXIS_VALUE  # Vrati srednju vrijednost za vJoy
    
    # Skaliraj vrijednost izvan deadzone
    if input_value < deadzone_min:
        # Donji dio - skaliraj od 0 do CENTER_AXIS_VALUE
        span_input = deadzone_min - input_min
        span_output = CENTER_AXIS_VALUE
        normalized = (input_value - input_min) / span_input
        result = int(normalized * span_output)
    else:  # input_value > deadzone_max
        # Gornji dio - skaliraj od CENTER_AXIS_VALUE do MAX_AXIS_VALUE
        span_input = input_max - deadzone_max
        span_output = MAX_AXIS_VALUE - CENTER_AXIS_VALUE
        normalized = (input_value - deadzone_max) / span_input
        result = int(CENTER_AXIS_VALUE + (normalized * span_output))
    
    return result


# ----- Callback za primljenu MQTT poruku -----
def on_message(client, userdata, msg):
    """
    Ovaj callback se poziva kad stigne nova poruka na bilo koju temu.
    msg.payload je vrijednost (osi: 0-65535, tasteri: 0 ili 1).
    """
    try:
        payload_str = msg.payload.decode('utf-8')
        
        # Obradi poruke za osi (X i Y)
        if msg.topic in [MQTT_TOPIC_X, MQTT_TOPIC_Y]:
            axis_value = int(payload_str)
            vjoy_value = scale_input_to_vjoy_axis(axis_value)
            
            if msg.topic == MQTT_TOPIC_X:
                vj.set_axis(pyvjoy.HID_USAGE_X, vjoy_value)
                print(f"X os: {axis_value} -> {vjoy_value}")
            elif msg.topic == MQTT_TOPIC_Y:
                vj.set_axis(pyvjoy.HID_USAGE_Y, vjoy_value)
                print(f"Y os: {axis_value} -> {vjoy_value}")
        
        # Obradi poruke za tastere (tastovi 1-4)
        elif msg.topic in [MQTT_TOPIC_LIJEVO, MQTT_TOPIC_DESNO, MQTT_TOPIC_SIRENA, MQTT_TOPIC_BRISAC]:
            button_value = int(payload_str)
            button_pressed = (button_value == 1)
            
            if msg.topic == MQTT_TOPIC_LIJEVO:
                vj.set_button(1, button_pressed)
                print(f"Lijevi zmigavac (button 1): {'UKLJUČEN' if button_pressed else 'ISKLJUČEN'}")
            elif msg.topic == MQTT_TOPIC_DESNO:
                vj.set_button(2, button_pressed)
                print(f"Desni zmigavac (button 2): {'UKLJUČEN' if button_pressed else 'ISKLJUČEN'}")
            elif msg.topic == MQTT_TOPIC_SIRENA:
                vj.set_button(3, button_pressed)
                print(f"Sirena (button 3): {'UKLJUČENA' if button_pressed else 'ISKLJUČENA'}")
            elif msg.topic == MQTT_TOPIC_BRISAC:
                vj.set_button(4, button_pressed)
                print(f"Brisač (button 4): {'UKLJUČEN' if button_pressed else 'ISKLJUČEN'}")

    except Exception as e:
        print(f"Greška pri parsiranju/podacima: {e}")


# ----- Callback kad se povežeš na MQTT broker -----
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Spojen na MQTT broker.")
        print(f"Pretplata na teme: {MQTT_TOPIC_X}, {MQTT_TOPIC_Y}")
        print(f"Pretplata na teme za tastere: {MQTT_TOPIC_LIJEVO}, {MQTT_TOPIC_DESNO}, {MQTT_TOPIC_SIRENA}, {MQTT_TOPIC_BRISAC}")
        
        # Pretplati se na sve teme
        client.subscribe(MQTT_TOPIC_X)
        client.subscribe(MQTT_TOPIC_Y)
        client.subscribe(MQTT_TOPIC_LIJEVO)
        client.subscribe(MQTT_TOPIC_DESNO)
        client.subscribe(MQTT_TOPIC_SIRENA)
        client.subscribe(MQTT_TOPIC_BRISAC)
        
        # Postavi početne vrijednosti na sredinu za osi
        vj.set_axis(pyvjoy.HID_USAGE_X, CENTER_AXIS_VALUE)
        vj.set_axis(pyvjoy.HID_USAGE_Y, CENTER_AXIS_VALUE)
        print(f"vJoy osi postavljene na srednju vrijednost ({CENTER_AXIS_VALUE})")
        
        # Postavi sve tastove kao otpuštene
        for i in range(1, 5):
            vj.set_button(i, False)
        print("vJoy tastovi 1-4 postavljeni na otpušteno stanje")
        
    else:
        print(f"Neuspješno spajanje, kod greške: {rc}")


def main():
    # 1. Inicijaliziraj MQTT klijenta
    client = mqtt.Client()

    # (Ako broker traži autentifikaciju, uvedi client.username_pw_set("username", "password"))
    # client.username_pw_set("username", "lozinka")

    client.on_connect = on_connect
    client.on_message = on_message

    # 2. Spoji se na broker
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)

    # 3. Pokreni loop koji će u pozadini slušati poruke
    client.loop_start()

    try:
        print("MQTT klijent pokrenut. Čeka se na poruke...")
        print(f"Deadzone: {DEADZONE_PERCENT*100}% oko srednje vrijednosti ({INPUT_CENTER})")
        print("Mapiranje tastera:")
        print("  tema/lijevo -> vJoy button 1 (lijevi zmigavac)")
        print("  tema/desno -> vJoy button 2 (desni zmigavac)")
        print("  tema/sirena -> vJoy button 3 (sirena)")
        print("  tema/brisac -> vJoy button 4 (brisač)")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Prekid rada skripte. Zatvaram konekciju i izlazim...")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()