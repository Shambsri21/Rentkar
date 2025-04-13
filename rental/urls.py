from django.urls import path
from . import views
from django.contrib.auth.decorators import login_required
from .views import CustomLoginView, CustomSignupView

urlpatterns = [
    path('', views.home, name='home'),
    path('vehicles/', views.vehicle_list, name='vehicle_list'),
    path('vehicles/<int:vehicle_id>/', views.vehicle_detail, name='vehicle_detail'),
    path('book/<int:vehicle_id>/', views.book_vehicle, name='book_vehicle'),
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('cancel-booking/<int:booking_id>/', views.cancel_booking, name='cancel_booking'),
    path('manager/dashboard/', login_required(views.manager_dashboard), name='manager_dashboard'),
    path('manager/vehicles/', views.manage_vehicles, name='manage_vehicles'),
    path('manager/vehicles/add/', views.add_vehicle, name='add_vehicle'),
    path('manager/vehicles/<int:vehicle_id>/edit/', views.edit_vehicle, name='edit_vehicle'),
    path('manager/vehicles/<int:vehicle_id>/delete/', views.delete_vehicle, name='delete_vehicle'),
    path('manager/bookings/', views.manage_bookings, name='manage_bookings'),
    path('manager/bookings/<int:booking_id>/approve/', views.approve_booking, name='approve_booking'),
    path('manager/bookings/<int:booking_id>/reject/', views.reject_booking, name='reject_booking'),
    path('manager/bookings/<int:booking_id>/complete/', views.complete_booking, name='complete_booking'),
    path('manager/users/', views.manage_users, name='manage_users'),
    path('manager/users/<int:user_id>/activate/', views.activate_user, name='activate_user'),
    path('manager/users/<int:user_id>/deactivate/', views.deactivate_user, name='deactivate_user'),
    path('manager/users/<int:user_id>/edit/', views.edit_user, name='edit_user'),
    path('manager/users/<int:user_id>/delete/', views.delete_user, name='delete_user'),
    path('profile/', views.profile, name='profile'),
    path('accounts/signup/', CustomSignupView.as_view(), name='account_signup'),
    path('accounts/login/', CustomLoginView.as_view(), name='account_login'),
    path('manager/login/', CustomLoginView.as_view(), name='manager_login'),
] 