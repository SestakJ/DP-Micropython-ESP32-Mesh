CMD=ampy
port=0
NAME=xsesta05

# port default value is 0.
# To chnage value execute "make port=1".

all: 0

# ampy -p /dev/ttyUSB0 ls src/
0:
	$(CMD) -p /dev/ttyUSB$(port) put src/
	$(CMD) -p /dev/ttyUSB$(port) put boot.py
	$(CMD) -p /dev/ttyUSB$(port) put main.py	

pack:
	zip $(NAME).zip -r src/ Makefile README.md

clean: 
	rm -f kry $(NAME).zip