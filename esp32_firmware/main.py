import serial

port = #algo de windows el puerto

with serial.Serial(port, baudrate=115200, timeout=1) as com:
    count = 0

    while True:
        com.write(f"Hello {count}\n".encode())

        data = com.read(4096)
        print(data.decode(errors="replace"), end="")

        count +=1