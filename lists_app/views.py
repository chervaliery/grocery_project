from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import GroceryList, Item, Section
from .serializers import GroceryListSerializer, ItemSerializer, SectionSerializer

class GroceryListViewSet(viewsets.ModelViewSet):
    queryset = GroceryList.objects.all()
    serializer_class = GroceryListSerializer

class ItemViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.all()
    serializer_class = ItemSerializer

class SectionViewSet(viewsets.ModelViewSet):
    queryset = Section.objects.all()
    ordering = ['order']
    serializer_class = SectionSerializer

def home(request):
    return render(request, 'index.html')