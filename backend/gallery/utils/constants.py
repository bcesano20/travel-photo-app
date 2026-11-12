MEDIA_TYPE_PHOTO = "photo"
MEDIA_TYPE_VIDEO = "video"
MEDIA_TYPE_CHOICES = [
    (MEDIA_TYPE_PHOTO, "Photo"),
    (MEDIA_TYPE_VIDEO, "Video"),
]

MEDIA_STATUS_PENDING = "pending"
MEDIA_STATUS_READY = "ready"
MEDIA_STATUS_ERROR = "error"
MEDIA_STATUS_CHOICES = [
    (MEDIA_STATUS_PENDING, "Pending"),
    (MEDIA_STATUS_READY, "Ready"),
    (MEDIA_STATUS_ERROR, "Error"),
]

# ERROR MESSAGES
SHARE_LINK_NOT_FOUND_MESSAGE = "This link doesn't exist or is no longer available."
