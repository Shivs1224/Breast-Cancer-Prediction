from django.conf import settings
from django.db import models


class UploadedImage(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="uploaded_images",
    )
    file = models.ImageField(upload_to="uploads/%Y/%m/")
    original_name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.original_name} ({self.user_id})"


class Annotation(models.Model):
    image = models.ForeignKey(
        UploadedImage,
        on_delete=models.CASCADE,
        related_name="annotations",
    )
    polygon_index = models.PositiveIntegerField(default=0)
    points_json = models.TextField(help_text="JSON array of [x, y] in image pixels")
    mask_relative = models.CharField(max_length=512, blank=True)
    viz_relative = models.CharField(max_length=512, blank=True)
    coords_relative = models.CharField(max_length=512, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["image", "polygon_index"]

    def __str__(self):
        return f"Annotation img={self.image_id} poly={self.polygon_index}"
