import io
import math
import hashlib
import uuid
from pathlib import Path
from PIL import Image
from pillow_heif import register_heif_opener

from app.crud import ad as ad_crud
from app.logger import setup_logger

logger = setup_logger(__name__)


async def save_file_in_folder(image, road, resolution):
    Path(f"./files/{road}").mkdir(parents=True, exist_ok=True)
    image.save(f"./files/{road}/{resolution}.webp", format="webp")


async def add_watermark(image, size, step):
    watermark = Image.open("./static/watermark.png")
    watermark = watermark.resize(size)
    image.paste(watermark, (image.size[0] - size[0] - step, image.size[1] - size[1] - step), watermark)
    pass


async def save_image_with_watermark(image, road):
    width, height = image.size
    aspect_ratio = height / width
    if aspect_ratio > 0.75:
        new_height = 960
        new_width = math.ceil(new_height / aspect_ratio)
    elif aspect_ratio < 0.75:
        new_width = 1280
        new_height = math.ceil(new_width * aspect_ratio)
    else:
        new_width = 1280
        new_height = 960
    im1 = image.resize((new_width, new_height))
    # await add_watermark(image=im1, size=(120, 66), step=20)  # with old kvik watermark
    await add_watermark(image=im1, size=(120, 54), step=20)  # with new cleex watermark
    await save_file_in_folder(image=im1, road=road, resolution="1280x960")
    im2 = image.resize((math.ceil(new_width / 2), math.ceil(new_height / 2)))
    # await add_watermark(image=im2, size=(90, 50), step=10)  # with old kvik watermark
    await add_watermark(image=im2, size=(90, 40), step=10)  # with new cleex watermark
    await save_file_in_folder(image=im2, road=road, resolution="640x480")


async def save_image_square_thumbnails(image, road):
    width, height = image.size
    if width > height:
        cropped = (width - height) / 2
        im = image.crop((cropped, 0, width - cropped, height))
        im = im.resize((300, 300))
    elif width < height:
        cropped = (height - width) / 2
        im = image.crop((0, cropped, width, height - cropped))
        im = im.resize((300, 300))
    else:
        im = image.resize((300, 300))
    await save_file_in_folder(image=im, road=road, resolution="300x300")
    im.thumbnail((200, 200))
    await save_file_in_folder(image=im, road=road, resolution="200x200")
    im.thumbnail((100, 100))
    await save_file_in_folder(image=im, road=road, resolution="100x100")


def get_image_orientation(image_content):
    orientation_value = 1  # Default orientation (normal)
    with io.BytesIO(image_content) as f:
        im = Image.open(f)
        if hasattr(im, '_getexif'):
            exif = im._getexif()
            if exif is not None:
                orientation_tag = 274  # EXIF tag for orientation
                orientation_value = exif.get(orientation_tag, 1)
    return orientation_value


async def save_images(images, post_id, status_id, db, old_photos=None):

    order_list = [photo["order"] for photo in old_photos] if old_photos else []

    i = 0
    try:
        for image in images:
            image_content = image.file.read()
            image_hash = hashlib.md5(image_content).hexdigest()

            road = "/" + "/".join([str(image_hash[i] + str(image_hash[i + 1])) for i in range(0, 7, 2)])
            road += f"/{uuid.uuid4()}"

            # Register opener for HEIF/HEIC format
            register_heif_opener()

            orientation_value = get_image_orientation(image_content)
            # print('orientation_value:', orientation_value)

            im = Image.open(io.BytesIO(image_content))
            # Convert to RGB if needed
            im = im.convert("RGB")

            if orientation_value == 3:
                im = im.rotate(180, expand=True)
                # print('rotated.180')
            elif orientation_value == 6:
                # print('try to rotate.-90')
                im = im.rotate(-90, expand=True)
                # print('rotated.-90')
            elif orientation_value == 8:
                im = im.rotate(90, expand=True)
                # print('rotated.90')

            await save_image_with_watermark(image=im, road=road)
            await save_image_square_thumbnails(image=im, road=road)

            while i in order_list:
                i += 1
            # В этой точке переменная i содержит уникальный порядковый номер для текущего image
            order = i
            await ad_crud.write_image_road(db=db, post_id=post_id, image_road=road, order=order)  # Если порядок фото нарушается, то убрать await
            i += 1
    except Exception as e:
        print('error', str(e))
        logger.error(f"utils/image- save_images. Ошибка сохранения изображений: {post_id} => {str(e)}")
        return False

    ad_crud.change_post_status(post_id=post_id, status_id=status_id, db=db)
    logger.info(f"Все фото успешно загружены для объявления:{post_id}")
    return True
