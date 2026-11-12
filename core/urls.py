from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('solutions/', views.solutions, name='solutions'),
    path('products/', views.products, name='products'),
    path('products/<slug:slug>/', views.product_detail, name='product_detail'),
    path('contact/', views.contact, name='contact'),
    path("services/", views.services, name="services"),
     path("works-done/", views.works_done, name="works_done"),
    

]
