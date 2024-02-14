from pathlib import Path

from sqlalchemy.orm import Session

from app.db.db_models import UserPhoto, User


# TODO: рефакторинг
def user_photo_create(uploaded_file, user: User, db: Session):
    home = Path(__file__).resolve().parent.parent.parent
    file_location = f"{home}/media/{uploaded_file.filename}"
    with open(file_location, "wb+") as file_object:
        file_object.write(uploaded_file.file.read())

    db_photo = UserPhoto(url=file_location)
    db.add(db_photo)
    db.commit()
    db.refresh(db_photo)

    db_user = db.query(User).filter(User.id == user.id).first()
    db_user.photoId = db_photo.id
    db.add(db_user)
    db.commit()
    return {"info": f"file '{uploaded_file.filename}' saved at '{file_location}'"}
