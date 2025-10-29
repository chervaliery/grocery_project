from rest_framework import routers
from django.urls import path, include
from .views import home, GroceryListViewSet, ItemViewSet, SectionViewSet

router = routers.DefaultRouter()
router.register(r'lists', GroceryListViewSet)
router.register(r'items', ItemViewSet)
router.register(r'sections', SectionViewSet)

urlpatterns = [
    path('', home, name='home'),
    path('api/', include(router.urls)),
]
