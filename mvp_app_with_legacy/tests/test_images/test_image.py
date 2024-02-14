# import io
# import uuid
# import os
#
# from app.crud.image import get_image_by_uuid
# from app.db.db_models import AdPhotos
# from app.schemas.ad import PostImageResolutions
#
#
# def test_get_image(test_client, test_db):
#     """
#     Мы создаем тестовый объект изображения и добавляем его в тестовую базу данных.
#     Отправляем запрос на получение изображения с помощью test_client.get().
#     Проверяем, что ответ имеет статус 200 и что тип содержимого - файл.
#     Если необходимо, можно также проверить содержимое файла (например, его формат).
#     Мы сравниваем полученные данные с ожидаемыми данными, считанными из файла.
#     :param test_client:
#     :param test_db:
#     :return:
#     """
#
#
#
#
#
#     resolutions = [
#         PostImageResolutions.small_square,
#         PostImageResolutions.medium_square,
#         PostImageResolutions.large_square,
#         PostImageResolutions.medium,
#         PostImageResolutions.large
#     ]
#
#
#
#     image_id = uuid.uuid4()
#     test_image = AdPhotos(id=image_id, ad_id=1, url=f"/test/{image_id}")
#
#     with test_db() as db:
#         db.add(test_image)
#         db.commit()
#
#     for resolution in resolutions:
#         response = test_client.get(f"/{resolution.value}/{test_image.id}")
#
#         assert response.status_code == 200
#         assert response.headers['content-type'] == 'application/octet-stream'
#
#         # Проверяем, что файл действительно сохранен в файловой системе
#         with test_db() as db:
#             db_image = get_image_by_uuid(db=db, image_uuid=test_image.id)
#             image_path = f"./files{db_image.url}/{resolution.value}/{test_image.id}.webp"
#             assert os.path.isfile(image_path)
#
#             # Удаляем файл после проверки
#             os.remove(image_path)
#
#         # with test_db() as db:
#         #     db_image = get_image_by_uuid(db=db, image_uuid=test_image.id)
#         #     image_path = f"./files{db_image.url}/{resolution.value}/{test_image.id}.webp"
#         #     with open(image_path, 'rb') as file:
#         #         expected_image_data = file.read()
#         #         assert response.content == expected_image_data
#
#     # Если необходимо, можно также проверить содержимое файла
#     # Например, если вы ожидаете, что изображение будет в определенном формате, можно сделать так:
#     # assert response.headers['content-type'] == 'image/jpeg'