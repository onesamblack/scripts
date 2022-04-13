import string
import time
import numpy as np


characters = []
characters.extend(string.ascii_lowercase)
characters.extend(string.ascii_uppercase)
characters.extend(['?','#','&','!'])
characters.extend([str(i) for i in range(0,9)])

def gen_random(length):
    return "".join(a for a in np.random.choice(characters, length))

def generate():
    while True:
        time.sleep(0.2) 
        print(gen_random(30))


if __name__ == "__main__":
    generate()
