from rest_framework import serializers
from .models import GroceryList, Item, Section


class SectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = ['id', 'name']

class ItemSerializer(serializers.ModelSerializer):
    section = SectionSerializer()
    class Meta:
        model = Item
        fields = ['id', 'name', 'checked', 'section']

class GroceryListSerializer(serializers.ModelSerializer):
    items = ItemSerializer(many=True, read_only=True)
    class Meta:
        model = GroceryList
        fields = ['id', 'name','created_at','items']