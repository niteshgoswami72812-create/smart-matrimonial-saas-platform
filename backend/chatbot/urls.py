from django.urls import path
from chatbot.views import ask_chatbot

urlpatterns = [
    path("ask/", ask_chatbot, name="ask_chatbot"),
]
