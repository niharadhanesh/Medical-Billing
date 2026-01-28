from django.urls import path
from . import views  # import the entire views.py module

urlpatterns = [
    path("", views.landing_page, name="landing"),
    path("login/", views.login_view, name="login"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("user_dashboard/", views.user_dashboard, name="user_dashboard"),
    path("logout/", views.logout_view, name="logout"),
    path('add-medicine/', views.add_medicine, name='add_medicine'),
    path('edit-medicine/<int:pk>/', views.add_medicine, name='edit_medicine'),
    path('medicine-stock/', views.medicine_stock, name='medicine_stock'),
    path('delete-medicine/<int:pk>/', views.delete_medicine, name='delete_medicine'),
    
    
      # Billing URLs
    path('billing/', views.billing_page, name='billing'),
    path('api/search-medicine/', views.search_medicine_ajax, name='search_medicine_ajax'),
    path('api/medicine/<int:medicine_id>/', views.get_medicine_details, name='get_medicine_details'),
    path('api/create-bill/', views.create_bill, name='create_bill'),
    
    # Bill Management
    path('bills/', views.bill_list, name='bill_list'),
    path('bills/<int:bill_id>/', views.bill_detail, name='bill_detail'),
    path('bills/<int:bill_id>/print/', views.print_bill, name='print_bill'),
    path('bills/<int:bill_id>/cancel/', views.cancel_bill, name='cancel_bill'),
    
    # Customer Management
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/<int:customer_id>/', views.customer_detail, name='customer_detail'),
    
    path('add-staff/', views.add_staff, name='add_staff'),
    path('edit-staff/<int:pk>/', views.add_staff, name='edit_staff'),
    path('staff-list/', views.staff_list, name='staff_list'),
    path('delete-staff/<int:pk>/', views.delete_staff, name='delete_staff'),
]
