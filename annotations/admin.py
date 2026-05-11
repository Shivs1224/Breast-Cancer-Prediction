from django.contrib import admin

from .models import Annotation, UploadedImage


@admin.register(UploadedImage)
class UploadedImageAdmin(admin.ModelAdmin):
    list_display = ("id", "original_name", "user", "uploaded_at")
    list_filter = ("uploaded_at",)


@admin.register(Annotation)
class AnnotationAdmin(admin.ModelAdmin):
    list_display = ("id", "image", "polygon_index", "created_at")
    list_filter = ("created_at",)
