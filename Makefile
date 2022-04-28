CMD=ampy
port=0
NAME=xsesta05

# port default value is 0.
# To chnage value execute "make port=1".

all: 0

0:
	-$(CMD) -p /dev/ttyUSB$(port) rmdir src
	-$(CMD) -p /dev/ttyUSB$(port) mkdir src
	-$(CMD) -p /dev/ttyUSB$(port) mkdir src/utils
	$(CMD) -p /dev/ttyUSB$(port) put boot.py
	$(CMD) -p /dev/ttyUSB$(port) put main.py
	$(CMD) -p /dev/ttyUSB$(port) put config.json
	$(CMD) -p /dev/ttyUSB$(port) put blinkapp.py blinkapp.py
	$(CMD) -p /dev/ttyUSB$(port) put src/espnowcore.py ./src/espnowcore.py
	$(CMD) -p /dev/ttyUSB$(port) put src/wificore.py ./src/wificore.py
	$(CMD) -p /dev/ttyUSB$(port) put src/utils/tree.py ./src/utils/tree.py
	$(CMD) -p /dev/ttyUSB$(port) put src/utils/messages.py ./src/utils/messages.py
	$(CMD) -p /dev/ttyUSB$(port) put src/utils/pins.py ./src/utils/pins.py
	$(CMD) -p /dev/ttyUSB$(port) put src/utils/net.py ./src/utils/net.py
	$(CMD) -p /dev/ttyUSB$(port) put src/utils/hmac.py ./src/utils/hmac.py


ap:
	$(CMD) -p /dev/ttyUSB$(port) put testing/ap/boot.py
	$(CMD) -p /dev/ttyUSB$(port) put testing/ap/main.py

sta:
	$(CMD) -p /dev/ttyUSB$(port) put testing/sta/boot.py
	$(CMD) -p /dev/ttyUSB$(port) put testing/sta/main.py

pack:
	zip $(NAME).zip -r src/ Makefile README.md blinkapp.py boot.py main.py

clean: 
	-rm $(NAME).zip
	-@$(CMD) -p /dev/ttyUSB$(port) rmdir src
