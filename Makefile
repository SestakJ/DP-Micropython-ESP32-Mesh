# coding=utf-8
# (C) Copyright 2022 Jindřich Šesták (xsesta05)
# Licenced under Apache License.
# Makefile

CMD=ampy
port=0
NAME=xsesta05
file=config.json

# To change value execute "make update port=x file=yyy".
# 	for i in {0..6}; do make port=${i}; done
# for i in {0..6}; do ampy -p /dev/ttyUSB${i} put config.json && echo "DONE $i"; done

install:
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
	$(CMD) -p /dev/ttyUSB$(port) put src/utils/oled_display.py ./src/utils/oled_display.py

install-all:
	for number in 0 1 2 3 4 5 6 ; do \
        make port=$$number & \
    done

update:
	$(CMD) -p /dev/ttyUSB$(port) put $(file) $(file)

update-all:
	for number in 0 1 2 3 4 5 6 ; do \
        $(CMD) -p /dev/ttyUSB$$number put $(file) $(file) && echo "DONE $$number"; \
    done

pack:
	zip $(NAME).zip -r src/ Makefile README.md blinkapp.py boot.py main.py

clean:
	-rm $(NAME).zip
