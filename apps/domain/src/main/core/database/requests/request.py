from .. import BaseModel, db


class Request(BaseModel):
    """Request.

    Columns:
        id (Integer, Primary Key): Cycle ID.
        date (TIME): Start time.
        user_id (Integer, Foreign Key): User that created the request.
        object_id (Integer): Target object to change in permisions.
        reason String: Motivation of the request.
        status (String): The status of the request, wich can be 'pending', 'accepted' or 'denied'.
        request_type (String): Wheter the type of the request is 'permissions' or 'budget'.
    """

    __tablename__ = "request"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    date = db.Column(db.DateTime())
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    object_id = db.Column(db.Integer())
    reason = db.Column(db.String(255))
    status = db.Column(db.String(255), default="pending")
    request_type = db.Column(db.String(255))

    def __str__(self):
        return f"< Request id : {self.id}, user: {self.user_id}, Date: {self.date}, Object: {self.object_id}, reason: {self.reason}, status: {self.status}, type: {self.type} >"
