
from pyzbar.pyzbar import decode
from PIL import Image
import pandas as pd
import numpy as np

def read_qr(camera=bpm_sp3,  show_image=False):
    camera.stage(0.02, 0)
    camera.trigger()
    camera.unstage()
    image = camera.image.read()[f'{camera.name}_image_array_data']['value'].reshape((960, 1280))

    df = pd.DataFrame(image)
    mean_adjust = df.mean().mean() * 2
    df[df > mean_adjust] = int(df.mean().mean())
    df[df >= (df.mean().max() + df.mean().min()) / 6] = 255
    df[df < (df.mean().max() + df.mean().min()) / 6] = 0

    image_qr = Image.fromarray(np.array(df), 'L')
    if show_image:
        image_qr.show()

    d = decode(image_qr)

    return d[0].data.decode()