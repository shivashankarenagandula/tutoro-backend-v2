"""
profiles.validators
---------------------
Reusable file-upload validation, applied to tutor profile photos and
documents now, and intended for academy logos / other image fields
later (Phase 1 roadmap item 11: "groundwork ... since tutor profile
photos and academy logos will need this soon anyway").

Kept as plain functions (not classes) so they're trivially usable in
both model field `validators=[...]` lists and DRF serializer
`validate_<field>` methods without extra wiring.
"""

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

# Generous but bounded -- big enough for a real phone photo, small
# enough that one bad upload can't fill up storage or slow down list
# pages that render thumbnails.
MAX_IMAGE_SIZE_MB = 5
MAX_DOCUMENT_SIZE_MB = 10

ALLOWED_IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]
ALLOWED_DOCUMENT_EXTENSIONS = ["pdf", "jpg", "jpeg", "png"]


def _validate_file_size(value, max_mb):
    max_bytes = max_mb * 1024 * 1024
    if value.size > max_bytes:
        raise ValidationError(f"File too large. Maximum size is {max_mb}MB.")


def validate_image_size(value):
    """Use on ImageField(validators=[...]) for photos/logos."""
    _validate_file_size(value, MAX_IMAGE_SIZE_MB)


def validate_document_size(value):
    """Use on FileField(validators=[...]) for resumes/certificates."""
    _validate_file_size(value, MAX_DOCUMENT_SIZE_MB)


# Extension checks -- Django's FileExtensionValidator handles the
# "is this a plausible file type" pass. It's not a substitute for
# server-side content sniffing against forged extensions, but it
# blocks the overwhelming majority of accidental/careless bad
# uploads (e.g. someone picking a .exe or .zip by mistake) cheaply.
validate_image_extension = FileExtensionValidator(allowed_extensions=ALLOWED_IMAGE_EXTENSIONS)
validate_document_extension = FileExtensionValidator(allowed_extensions=ALLOWED_DOCUMENT_EXTENSIONS)
