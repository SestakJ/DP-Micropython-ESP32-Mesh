CMD=ampy
port=0
NAME=xsesta05

# port default value is 0.
# To chnage value execute "make port=1".

all: 0

0:
	$(CMD) -p /dev/ttyUSB$(port) put boot.py
	$(CMD) -p /dev/ttyUSB$(port) put main.py
	$(CMD) -p /dev/ttyUSB$(port) mkdir src	
	$(CMD) -p /dev/ttyUSB$(port) put src/core.py ./src/core.py
	$(CMD) -p /dev/ttyUSB$(port) put src/wificore.py ./src/wificore.py
	$(CMD) -p /dev/ttyUSB$(port) put src/tree.py ./src/tree.py
	$(CMD) -p /dev/ttyUSB$(port) put src/espmsg.py ./src/espmsg.py
	$(CMD) -p /dev/ttyUSB$(port) put src/utils.py ./src/utils.py
	$(CMD) -p /dev/ttyUSB$(port) put src/net.py ./src/net.py
	$(CMD) -p /dev/ttyUSB$(port) mkdir src/ucrypto
	$(CMD) -p /dev/ttyUSB$(port) put src/ucrypto/hmac.py ./src/ucrypto/hmac.py
	$(CMD) -p /dev/ttyUSB$(port) put config.json 
	

pack:
	zip $(NAME).zip -r src/ Makefile README.md

clean: 
	rm -f kry $(NAME).zip