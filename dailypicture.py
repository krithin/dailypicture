#!/usr/bin/env python

import asyncio
import datetime
import io
import json
from nio import AsyncClient, UploadResponse
from PIL import Image
from typing import NamedTuple

import smb_picture_picker as spp

MAX_IMAGE_DIMENSION = 1440  # Either width or height, with the other side scaled as needed.

class SMBConfig(NamedTuple):
    server_name: str
    server_ip: str
    share_name: str
    username: str
    password: str

class MatrixConfig(NamedTuple):
    mxid: str
    access_token: str
    device_id: str
    homeserver_url: str
    target_room: str

def read_smb_config():
    with open('smb_config.json') as f:
        c = json.load(f)
        return SMBConfig(
            server_name = c['server_name'],
            server_ip = c['server_ip'] if 'server_ip' in c else c['server_name'],
            share_name = c['share_name'],
            username = c['username'],
            password = c['password']
        )

def read_matrix_config():
    with open('matrix_config.json') as f:
        c = json.load(f)
        return MatrixConfig(
            mxid = c['mxid'],
            access_token = c['access_token'],
            device_id = c['device_id'],
            homeserver_url = c['homeserver_url'],
            target_room = c['target_room']
        )

def get_random_picture(smb_config: SMBConfig) -> Image:
    picker = spp.SMBPicturePicker(
        smb_config.username,
        smb_config.password,
        smb_config.server_name,
        smb_config.server_ip,
        smb_config.share_name
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

async def post_picture_to_room(matrix_config: MatrixConfig, image: Image) -> None:
    client = AsyncClient(matrix_config.homeserver_url)
    client.access_token = matrix_config.access_token
    client.user_id = matrix_config.mxid
    client.device_id = matrix_config.device_id

    room_id = matrix_config.target_room

    f = io.BytesIO()

    image.save(f, format="JPEG", optimize=True, progressive=True)

    # Get the (post-resize) file size
    f.seek(0, io.SEEK_END)
    image_file_size = f.tell()
    print(f"Image resized down to {image_file_size} bytes")
    f.seek(0)  # rewind to the start

    # First upload the image and get an MXC URI in response
    resp, _maybe_keys = await client.upload(
        lambda _got_429, _got_timeouts: f,  # No need to really use aiofiles when we have a BytesIO
        content_type="image/jpeg",
        filesize=image_file_size
    )

    if not isinstance(resp, UploadResponse):
        raise RuntimeError(f"Failed to send image: {resp}")

    # Then send a (image) message to the room pointing to the uploaded image's MXC URI.
    today_str = str(datetime.date.today())
    content = {
        "body": f"Image of the day {today_str}",
        "info": {
            "size": image_file_size,
            "mimetype": "image/jpeg",
            "w": image.width,
            "h": image.height,
            "thumbnail_info": None,
            "thumbnail_url": None,
        },
        "msgtype": "m.image",
        "url": resp.content_uri,
    }

    await client.room_send(
        room_id,
        message_type="m.room.message",
        content=content
    )

    f.close()
    await client.close()

if __name__ == '__main__':
    image = get_random_picture(read_smb_config())
    asyncio.run(post_picture_to_room(read_matrix_config(), image))
