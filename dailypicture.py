#!/usr/bin/env python

import json
from PIL import Image
from typing import NamedTuple

import smb_picture_picker as spp

MAX_IMAGE_DIMENSION = 1440  # Either width or height, with the other side scaled as needed.

class Credentials(NamedTuple):
    server_name: str
    server_ip: str
    share_name: str
    username: str
    password: str

def read_credentials():
    with open('smb_config.json') as f:
        c = json.load(f)
        return Credentials(
            server_name = c['server_name'],
            server_ip = c['server_ip'] if 'server_ip' in c else c['server_name'],
            share_name = c['share_name'],
            username = c['username'],
            password = c['password']
        )

def get_random_picture(smb_credentials: Credentials) -> Image:
    picker = spp.SMBPicturePicker(
        smb_credentials.username,
        smb_credentials.password,
        smb_credentials.server_name,
        smb_credentials.server_ip,
        smb_credentials.share_name
    )
    picture_fp = picker.pick()
    im = Image.open(picture_fp, mode='r')

    # Resize the image if necessary
    w, h = im.width, im.height
    if w > h and w > MAX_IMAGE_DIMENSION:
        w, h = MAX_IMAGE_DIMENSION, int(MAX_IMAGE_DIMENSION * h / w)
        im = im.resize((w, h))
    elif h > MAX_IMAGE_DIMENSION:
        w, h = int(MAX_IMAGE_DIMENSION * w / h), MAX_IMAGE_DIMENSION
        im = im.resize((w, h))

    return im

if __name__ == '__main__':
    get_random_picture(read_credentials())