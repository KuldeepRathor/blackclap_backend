import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models.base import BaseModel


class Post(BaseModel):
    __tablename__ = "posts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    caption: Mapped[str | None] = mapped_column(String(2200), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    media_type: Mapped[str] = mapped_column(String(10), nullable=False, default="text")

    media: Mapped[list["PostMedia"]] = relationship(
        "PostMedia",
        back_populates="post",
        order_by="PostMedia.order",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Post id={self.id} user_id={self.user_id} media_type={self.media_type}>"


class PostMedia(BaseModel):
    __tablename__ = "post_media"

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    media_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    media_type: Mapped[str] = mapped_column(String(10), nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    post: Mapped["Post"] = relationship("Post", back_populates="media")

    def __repr__(self) -> str:
        return f"<PostMedia id={self.id} post_id={self.post_id} order={self.order}>"
