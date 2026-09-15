from rest_framework import serializers

from .embed import get_embed_url
from .models import Video


class VideoSerializer(serializers.ModelSerializer):
    # Calculated from the url; React uses it to show the video inside the page.
    embed_url = serializers.SerializerMethodField()

    class Meta:
        model = Video
        fields = ['id', 'topic', 'title', 'url', 'embed_url', 'description', 'order', 'created_at', 'updated_at']
        read_only_fields = ['topic', 'created_at', 'updated_at']

    def get_embed_url(self, video):
        return get_embed_url(video.url)
