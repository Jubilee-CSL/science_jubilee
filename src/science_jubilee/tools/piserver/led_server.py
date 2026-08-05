from flask import Flask

import neopixel
import board

app = Flask(__name__)

pixels = neopixel.NeoPixel(board.D18,8,brightness=0.3,auto_write=True)

@app.route("/off")
def off():
	pixels.fill((0,0,0))
	return "OK"

@app.route("/")
def test():
	return "Serveur LED OK"

@app.route("/led/<int:r>/<int:g>/<int:b>")
def led(r,g,b):
	
	pixels.fill((r,g,b))
	
	return "OK"

@app.route("/pixel/<int:index>/<int:r>/<int:g>/<int:b>")
def pixel(index,r,g,b):

	pixels[index] = (r,g,b)
	pixels.show()

	return "OK"

app.run(host="0.0.0.0",port=5001)
