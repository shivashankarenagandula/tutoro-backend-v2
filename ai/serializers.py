from rest_framework import serializers


class FAQChatSerializer(serializers.Serializer):
    """
    Not a ModelSerializer -- this is a stateless request/response
    shape, there's no FAQChat model to persist a conversation. Each
    call is independent; the frontend widget is expected to hold its
    own short local history if it wants multi-turn context (not sent
    back to the API today -- see FAQChatView docstring for why).
    """

    question = serializers.CharField(max_length=1000, trim_whitespace=True)

    def validate_question(self, value):
        if not value.strip():
            raise serializers.ValidationError("question can't be empty.")
        return value
