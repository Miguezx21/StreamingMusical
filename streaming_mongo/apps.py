from django.apps import AppConfig

class StreamingMongoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'streaming_mongo'
    verbose_name = 'Streaming Musical (MongoDB)'
