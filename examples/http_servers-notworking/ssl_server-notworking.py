#!/usr/bin/env python3
# https://gist.github.com/zapstar/a7035795483753f7b71a542559afa83f
import uasyncio as asyncio
import ussl as ssl


# @asyncio.coroutine
async def handle_connection(reader, writer):
    addr = writer.get_extra_info('peername')
    print('Connection established with {}'.format(addr))
    while True:
        # Read the marker
        try:
            size_bytes = await reader.readexactly(4)
            if not size_bytes:
                print('Connection terminated with {}'.format(addr))
                break
        except asyncio.IncompleteReadError:
            print('Connection terminated with {}'.format(addr))
            break
        size = int.from_bytes(size_bytes, byteorder='big')
        # Read the data
        try:
            data = await reader.readexactly(size)
            if not size_bytes:
                print('Connection terminated with {}'.format(addr))
                break
        except asyncio.IncompleteReadError:
            print('Connection terminated with {}'.format(addr))
            break
        print('Read {} bytes from  the client: {}'.format(size, addr))
        # Reverse the string
        echo_data = ''.join(reversed(data.decode()))
        # Send the marker
        writer.write(len(echo_data).to_bytes(4, byteorder='big'))
        # Send the data itself
        writer.write(echo_data.encode())
        # Wait for the data to be written back
        await writer.drain()
        print('Finished sending {} bytes to the client: {}'.format(size, addr))


def setup_server():
    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_ctx.options |= ssl.OP_NO_TLSv1
    ssl_ctx.options |= ssl.OP_NO_TLSv1_1
    ssl_ctx.options |= ssl.OP_SINGLE_DH_USE
    ssl_ctx.options |= ssl.OP_SINGLE_ECDH_USE
    ssl_ctx.load_cert_chain('server_cert.pem', keyfile='server_key.pem')
    ssl_ctx.load_verify_locations(cafile='server_ca.pem')
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.VerifyMode.CERT_REQUIRED
    ssl_ctx.set_ciphers('ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384')
    loop = asyncio.get_event_loop()
    coroutine = asyncio.start_server(handle_connection,
                                     '192.168.0.200',
                                     8080,
                                     ssl=ssl_ctx,
                                     loop=loop)
    server = loop.run_until_complete(coroutine)
    print('Serving on {}'.format(server.sockets[0].getsockname()))
    loop.run_forever()


if __name__ == '__main__':
    setup_server()