
from django.urls import path
from . import views, ai_views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('solutions/', views.solutions, name='solutions'),
    path('products/', views.products, name='products'),
    path('products/<slug:slug>/', views.product_detail, name='product_detail'),
    path('contact/', views.contact, name='contact'),
    path('services/', views.services, name='services'),
    path('works-done/', views.works_done, name='works_done'),
    path('api/product-search/', views.product_search, name='product_search'),
    # AI engineer assistant
    path(
        'api/engineer-chat/',
        ai_views.engineer_chat,
        name='engineer_chat'
    ),
    path("faq/", views.faq, name="faq"),
    path('search/', views.search_results, name='search_results'),
    #path('search/', views.search_results, name='search_results'),
    path('news/', views.blog_list, name='blog_list'),
path('news/<slug:slug>/', views.blog_detail, name='blog_detail'),
]
