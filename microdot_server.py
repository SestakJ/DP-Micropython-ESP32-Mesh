try:
    import uasyncio as asyncio
except ImportError:
    import asyncio
from microdot.microdot_asyncio import Microdot, Response
from utils import init_LED, blink


htmldoc = """<!DOCTYPE html>
        <html>
            <head> 
                <title>ESP Web Server</title>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <link rel="icon" href="data:,">
                <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/css/bootstrap.min.css" integrity="sha384-ggOyR0iXCbMQv3Xipma34MD+dH/1fQ784/j6cY/iJTQUOhcWr7x9JvoRxT2MZw1T" crossorigin="anonymous">
    
                <style>html{font-family: Helvetica; display:inline-block; margin: 0px auto; text-align: center;}
                h1{color: #0F3376; padding: 2vh;}p{font-size: 1.5rem;}.button{display: inline-block; background-color: #e7bd3b; border: none; 
                border-radius: 4px; color: white; padding: 16px 40px; text-decoration: none; font-size: 30px; margin: 2px; cursor: pointer;}
                .button2{background-color: #4286f4;}</style>           
                <script>
                    function getCookie(name) {
                        var value = "; " + document.cookie;
                        var parts = value.split("; " + name + "=");
                        //if (parts.length == 2)
                        return parts.pop().split(";").shift();
                    }
                    function showMessage() {
                        document.getElementById('message').innerHTML = getCookie('message');
                    }
                    function onLoad() {
                        showMessage();
                        //var form = getCookie('form');
                        //if (form) {
                        //    form = form.split(',')
                        //    document.getElementById('pin').selectedIndex = parseInt(form[0]);
                        //    document.getElementById(form[1]).checked = true;
                        //}
                    }
                </script>
            </head>
            <body onload="onLoad();"> 
                <h1>ESP Web Server</h1> 
                <p>GPIO state: <strong>""" + """</strong></p>
                <p><a href="/?led=on"><button class="button">ON</button></a></p>
                <p><a href="/?led=off"><button class="button button2">OFF</button></a></p>
                
                <div class="alert alert-primary" role="alert" id="message"></div>
                <p>MESH ESP NOW setup </p>
                <form action="/" method="POST">
                    <input type="text" name="mesh-ssid" placeholder="Mesh SSID"><br> 
                    <input type="password" name="mesh-password" placeholder="Mesh Password"><br>
                    <input type="text" name="wifi-ssid" placeholder="WiFi SSID"><br> 
                    <input type="password" name="wifi-password" placeholder="WiFi Password"><br>
                    <left><button type="submit">Submit</button></left>
                </form>     
                
                <p><a href="/shutdown">Click to shutdown the server</a></p>
            </body>
        </html>
        """



# Create Async Microdot server and serve users request on given address. 
async def server(ipaddr="0.0.0.0"):
    app = Microdot()

    @app.route('/', methods=['GET', 'POST'])
    async def hello(request):
        if request.method == 'POST':
            if request._body:
                # Request body contains forms from HTML, here the form is parsed to dict
                print(request._body)
                form_data = {}
                for k, v in [pair.split('=', 1) for pair in str(request._body).split('&')]:
                        form_data[k] = v
                print(form_data)
        # Arguments are "/?" something = something already parsed
        print(request.args)
        
        # Get value into the HTML response from cookie
        message_cookie = "Hello World Cookie"
        if 'led' in request.args:
            message_cookie = "LED " + request.args['led'] + " Cookie"
        
        response = Response(body=htmldoc, headers={'Content-Type': 'text/html'})
        if message_cookie:
            response.set_cookie('message', message_cookie)
        
        return response


    @app.route('/shutdown')
    async def shutdown(request):
        request.app.shutdown()
        return 'The server is shutting down...'

    app.run(host=ipaddr, port=80,debug=True)


if __name__=='__main__':
    import network
    ssid = "FourMusketers_2.4GHz"
    password = "pass"

    # ssid = "ESP-AP"
    # password = "esp"
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(ssid, password)
        while not wlan.isconnected():
            asyncio.sleep_ms(10)
    print("Connected")
    print(wlan.ifconfig())

    n = init_LED()
    loop = asyncio.get_event_loop()
    loop.create_task(blink())

    try:
        asyncio.run(server(wlan.ifconfig()[0]))
    except (KeyboardInterrupt, Exception) as e:
        print("Exception {}".format(type(e).__name__))
    finally:
        asyncio.new_event_loop()
